import hashlib

from django.utils import timezone

from .models import IngestionAPIKey


ROLE_ADMIN = "ORG_ADMIN"
ROLE_ANALYST = "RISK_ANALYST"
ROLE_REVIEWER = "REVIEWER"
ROLE_VIEWER = "VIEWER"


def require_roles(*roles):
    def decorator(view):
        from functools import wraps
        from django.http import HttpResponseForbidden

        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            if request.user.is_superuser or request.user.role in roles:
                return view(request, *args, **kwargs)
            return HttpResponseForbidden("You do not have permission to perform this action.")
        return wrapped
    return decorator


def authenticate_api_key(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    raw = header[7:].strip()
    if len(raw) < 16:
        return None
    prefix = raw[:12]
    digest = hashlib.sha256(raw.encode()).hexdigest()
    key = IngestionAPIKey.objects.select_related("organization").filter(prefix=prefix, secret_hash=digest, is_active=True).first()
    if key:
        key.last_used_at = timezone.now()
        key.save(update_fields=["last_used_at", "updated_at"])
    return key
