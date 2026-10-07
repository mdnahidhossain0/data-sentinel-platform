import hashlib
import json
import logging
import sqlite3
import uuid
from contextlib import closing

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .audit import audit
from .models import DataSource, SchemaColumn, SchemaTable, SchemaVersion


PII_NAMES = {"phone", "mobile", "email", "national_id", "nid", "passport", "name", "address"}
logger = logging.getLogger(__name__)


def _fernet():
    if not settings.DATA_SOURCE_ENCRYPTION_KEY:
        raise RuntimeError("DATA_SOURCE_ENCRYPTION_KEY is required before storing connector credentials")
    return Fernet(settings.DATA_SOURCE_ENCRYPTION_KEY.encode())


def encrypt_password(raw):
    return _fernet().encrypt(raw.encode()).decode() if raw else ""


def decrypt_password(value):
    try:
        return _fernet().decrypt(value.encode()).decode() if value else ""
    except InvalidToken as error:
        raise RuntimeError("Data-source credential cannot be decrypted with the configured key") from error


def _sqlite_metadata(path):
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)) as connection:
        tables = []
        for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            columns = [{"name": row[1], "type": row[2], "nullable": not bool(row[3]), "position": row[0] + 1}
                       for row in connection.execute(f'PRAGMA table_info("{name}")')]
            pk = [row[1] for row in connection.execute(f'PRAGMA table_info("{name}")') if row[5]]
            fks = [{"column": row[3], "target_table": row[2], "target_column": row[4]}
                   for row in connection.execute(f'PRAGMA foreign_key_list("{name}")')]
            indexes = [row[1] for row in connection.execute(f'PRAGMA index_list("{name}")')]
            count = connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            tables.append({"schema": "main", "name": name, "columns": columns, "primary_key": pk,
                           "foreign_keys": fks, "indexes": indexes, "row_estimate": count})
    return tables


def _postgres_metadata(source):
    try:
        import psycopg2
    except ImportError as error:
        raise RuntimeError("psycopg2-binary is required for PostgreSQL discovery") from error
    connection = psycopg2.connect(
        host=source.host, port=source.port or 5432, dbname=source.database_name,
        user=source.username, password=decrypt_password(source.encrypted_password),
        connect_timeout=5, sslmode="require" if source.ssl_required else "prefer",
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT c.table_schema, c.table_name, c.column_name, c.data_type, c.is_nullable, c.ordinal_position
                FROM information_schema.columns c
                JOIN information_schema.tables t ON t.table_schema=c.table_schema AND t.table_name=c.table_name
                WHERE t.table_type='BASE TABLE' AND c.table_schema NOT IN ('pg_catalog','information_schema')
                ORDER BY c.table_schema,c.table_name,c.ordinal_position
            """)
            grouped = {}
            for schema, table, column, data_type, nullable, position in cursor.fetchall():
                grouped.setdefault((schema, table), []).append({"name": column, "type": data_type, "nullable": nullable == "YES", "position": position})
            cursor.execute("""
                SELECT schemaname, relname, n_live_tup FROM pg_stat_user_tables
            """)
            estimates = {(schema, table): rows for schema, table, rows in cursor.fetchall()}
            tables = [{"schema": schema, "name": table, "columns": columns, "primary_key": [], "foreign_keys": [],
                       "indexes": [], "row_estimate": estimates.get((schema, table))}
                      for (schema, table), columns in grouped.items()]
            cursor.execute("""
                SELECT tc.table_schema,tc.table_name,kcu.column_name
                FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
                WHERE tc.constraint_type='PRIMARY KEY'
            """)
            lookup = {(item["schema"], item["name"]): item for item in tables}
            for schema, table, column in cursor.fetchall():
                if (schema, table) in lookup: lookup[(schema, table)]["primary_key"].append(column)
            cursor.execute("""
                SELECT tc.table_schema,tc.table_name,kcu.column_name,ccu.table_schema,ccu.table_name,ccu.column_name
                FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name=tc.constraint_name
                WHERE tc.constraint_type='FOREIGN KEY'
            """)
            for schema, table, column, target_schema, target_table, target_column in cursor.fetchall():
                if (schema, table) in lookup:
                    lookup[(schema, table)]["foreign_keys"].append({"column": column, "target_schema": target_schema,
                                                                    "target_table": target_table, "target_column": target_column})
            cursor.execute("SELECT schemaname,tablename,indexname FROM pg_indexes WHERE schemaname NOT IN ('pg_catalog','information_schema')")
            for schema, table, index in cursor.fetchall():
                if (schema, table) in lookup: lookup[(schema, table)]["indexes"].append(index)
            return tables
    finally:
        connection.close()


def _canonical(tables):
    return json.dumps(tables, sort_keys=True, separators=(",", ":"))


def _diff(previous, current):
    old = {f"{t.schema_name}.{t.table_name}": {c.name: c.data_type for c in t.columns.all()} for t in previous.tables.prefetch_related("columns")} if previous else {}
    new = {f"{t['schema']}.{t['name']}": {c['name']: c['type'] for c in t["columns"]} for t in current}
    changes = {"tables_added": sorted(new.keys() - old.keys()), "tables_removed": sorted(old.keys() - new.keys()),
               "columns_added": [], "columns_removed": [], "types_changed": []}
    for table in sorted(new.keys() & old.keys()):
        changes["columns_added"] += [f"{table}.{name}" for name in sorted(new[table].keys() - old[table].keys())]
        changes["columns_removed"] += [f"{table}.{name}" for name in sorted(old[table].keys() - new[table].keys())]
        changes["types_changed"] += [{"column": f"{table}.{name}", "from": old[table][name], "to": new[table][name]}
                                     for name in sorted(new[table].keys() & old[table].keys()) if old[table][name] != new[table][name]]
    return changes


@transaction.atomic
def discover_schema(source):
    tables = _sqlite_metadata(source.database_name) if source.engine == DataSource.ENGINE_SQLITE else _postgres_metadata(source)
    fingerprint = hashlib.sha256(_canonical(tables).encode()).hexdigest()
    previous = source.schema_versions.prefetch_related("tables__columns").first()
    if previous and previous.fingerprint == fingerprint:
        source.status, source.last_discovered_at = "ACTIVE", timezone.now()
        source.save(update_fields=["status", "last_discovered_at", "updated_at"])
        return previous, False
    version = SchemaVersion.objects.create(data_source=source, version=(previous.version + 1 if previous else 1),
                                           fingerprint=fingerprint, changes=_diff(previous, tables))
    for item in tables:
        table = SchemaTable.objects.create(schema_version=version, schema_name=item["schema"], table_name=item["name"],
                                           row_estimate=item["row_estimate"], primary_key=item["primary_key"],
                                           foreign_keys=item["foreign_keys"], indexes=item["indexes"])
        SchemaColumn.objects.bulk_create([SchemaColumn(
            table=table, name=column["name"], data_type=column["type"], nullable=column["nullable"],
            ordinal_position=column["position"], is_pii=column["name"].lower() in PII_NAMES,
        ) for column in item["columns"]])
    source.status, source.last_discovered_at = "ACTIVE", timezone.now()
    source.save(update_fields=["status", "last_discovered_at", "updated_at"])
    audit("schema.discovered", organization=source.organization, target=source,
          metadata={"version": version.version, "fingerprint": fingerprint, "changes": version.changes})

    def publish_schema_event():
        if not source.organization.external_id:
            return
        try:
            from django.conf import settings
            from .streaming import publish
            publish(settings.KAFKA_TOPIC_SCHEMA, {
                "event_id": str(uuid.uuid4()), "event_type": "schema.changed",
                "tenant_id": str(source.organization.external_id), "source": "schema-discovery",
                "timestamp": timezone.now().isoformat(), "correlation_id": str(uuid.uuid4()),
                "schema_version": "1.0", "data_source_id": source.pk,
                "catalog_version": version.version, "changes": version.changes,
            })
        except Exception as error:
            logger.warning("Schema event publish failed source_id=%s error=%s", source.pk, error.__class__.__name__)
    transaction.on_commit(publish_schema_event)
    return version, True
