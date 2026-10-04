from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from audit.services import log_action, log_system_action


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    log_action(request, "login", target=user)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        log_action(request, "logout", target=user)


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    log_system_action("login_failed", metadata={"username": credentials.get("username", "")})
