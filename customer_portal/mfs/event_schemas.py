import uuid
from datetime import datetime


COMMON_FIELDS = {"event_id", "event_type", "tenant_id", "source", "timestamp", "correlation_id", "schema_version"}
SUPPORTED_VERSIONS = {"1.0"}


class EventSchemaError(ValueError):
    pass


def validate_event(payload, required=()):
    missing = (COMMON_FIELDS | set(required)) - payload.keys()
    if missing:
        raise EventSchemaError(f"event is missing fields: {', '.join(sorted(missing))}")
    if payload["schema_version"] not in SUPPORTED_VERSIONS:
        raise EventSchemaError("unsupported schema_version")
    try:
        uuid.UUID(str(payload["event_id"])); uuid.UUID(str(payload["correlation_id"]))
        datetime.fromisoformat(str(payload["timestamp"]).replace("Z", "+00:00"))
    except ValueError as error:
        raise EventSchemaError("invalid event identifier or timestamp") from error
    return payload
