import uuid

from .models import MfsAuditEvent


SENSITIVE_KEYS = {"password", "secret", "token", "license_key", "api_key", "credentials", "payload"}


def _safe_metadata(metadata):
    return {key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else value for key, value in (metadata or {}).items()}


def audit(action, *, organization=None, organization_id=None, actor=None, target=None, correlation_id=None, metadata=None):
    values = dict(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=target.__class__.__name__ if target else "",
        target_id=str(getattr(target, "pk", "")) if target else "",
        correlation_id=correlation_id or uuid.uuid4(),
        metadata=_safe_metadata(metadata),
    )
    values["organization_id"] = organization_id or getattr(organization, "pk", None)
    return MfsAuditEvent.objects.create(**values)
