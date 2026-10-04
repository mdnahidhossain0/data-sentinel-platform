from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from audit.services import log_action


def license_manager_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.can_manage_licenses:
            log_action(request, "permission_denied", metadata={"required": "license_manager", "view": view.__name__})
            messages.error(request, "You don't have permission to perform that action.")
            return redirect("dashboard:home")
        return view(request, *args, **kwargs)

    return wrapped


def super_admin_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.can_manage_admins:
            log_action(request, "permission_denied", metadata={"required": "super_admin", "view": view.__name__})
            messages.error(request, "You don't have permission to perform that action.")
            return redirect("dashboard:home")
        return view(request, *args, **kwargs)

    return wrapped
