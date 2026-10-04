from .models import AuditEvent


def _client_ip(request):
    if request is None:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(request, action, target=None, metadata=None):
    actor = getattr(request, "user", None)
    if actor is not None and not actor.is_authenticated:
        actor = None

    AuditEvent.objects.create(
        actor=actor,
        action=action,
        target_type=type(target).__name__ if target is not None else "",
        target_id=str(getattr(target, "pk", "")) if target is not None else "",
        ip_address=_client_ip(request),
        metadata=metadata or {},
    )


def log_system_action(action, target=None, metadata=None):
    AuditEvent.objects.create(
        actor=None,
        action=action,
        target_type=type(target).__name__ if target is not None else "",
        target_id=str(getattr(target, "pk", "")) if target is not None else "",
        ip_address=None,
        metadata=metadata or {},
    )
