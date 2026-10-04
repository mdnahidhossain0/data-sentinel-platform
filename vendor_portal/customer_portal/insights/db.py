import sqlite3

from django.conf import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT NOT NULL
)
"""


def get_connection():
    engine = settings.INSIGHTS_DB_ENGINE

    if engine == "postgresql":
        import psycopg2

        conn = psycopg2.connect(
            host=settings.INSIGHTS_DB_HOST,
            port=settings.INSIGHTS_DB_PORT,
            dbname=settings.INSIGHTS_DB_NAME,
            user=settings.INSIGHTS_DB_USER,
            password=settings.INSIGHTS_DB_PASSWORD,
        )
    else:
        conn = sqlite3.connect(settings.INSIGHTS_DB_PATH)

    with conn:
        cursor = conn.cursor()
        cursor.execute(SCHEMA.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY") if engine == "postgresql" else SCHEMA)
        cursor.close()

    return conn


def fetch_orders(conn, days):
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT created_at, amount, status FROM orders
        WHERE created_at >= datetime('now', '-{int(days)} days')
        ORDER BY created_at
        """
        if settings.INSIGHTS_DB_ENGINE != "postgresql"
        else f"""
        SELECT created_at, amount, status FROM orders
        WHERE created_at >= NOW() - INTERVAL '{int(days)} days'
        ORDER BY created_at
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows
