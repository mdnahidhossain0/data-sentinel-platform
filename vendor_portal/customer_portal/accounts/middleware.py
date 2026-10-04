from django.contrib import messages
from django.contrib.auth import SESSION_KEY, get_user_model
from django.shortcuts import redirect

EXEMPT_PATH_PREFIXES = (
    "/accounts/login/",
    "/accounts/password-reset",
    "/accounts/reset/",
    "/internal/",
    "/healthz/",
    "/static/",
    "/admin/",
)


class InactiveCustomerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_anonymous and not request.path.startswith(EXEMPT_PATH_PREFIXES):
            user_id = request.session.get(SESSION_KEY)
            if user_id is not None:
                CustomerUser = get_user_model()
                stale_user = CustomerUser.objects.filter(pk=user_id, is_active=False).first()
                if stale_user is not None:
                    request.session.flush()
                    messages.error(request, "Your account has been suspended. Contact your vendor for access.")
                    return redirect("accounts:login")

        return self.get_response(request)
