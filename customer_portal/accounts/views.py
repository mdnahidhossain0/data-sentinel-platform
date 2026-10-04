import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.contrib.sessions.models import Session
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import OrganizationForm, ProfileForm
from .models import Organization
from .ratelimit import is_rate_limited

CustomerUser = get_user_model()


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class EmailAuthenticationForm(AuthenticationForm):
    username = AuthenticationForm.base_fields["username"]
    username.label = "Email"


class RateLimitedLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm

    def post(self, request, *args, **kwargs):
        if is_rate_limited(f"login:{_client_ip(request)}", settings.LOGIN_RATE_LIMIT_PER_MINUTE):
            return HttpResponse("Too many login attempts. Please wait a minute and try again.", status=429)
        return super().post(request, *args, **kwargs)


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def organization_settings(request):
    organization = request.user.organization
    if request.method == "POST":
        form = OrganizationForm(request.POST, instance=organization)
        if form.is_valid():
            form.save()
            messages.success(request, "Organization updated.")
            return redirect("accounts:organization_settings")
    else:
        form = OrganizationForm(instance=organization)
    return render(request, "accounts/organization_settings.html", {"form": form, "organization": organization})


@login_required
def security(request):
    active_sessions = 0
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        data = session.get_decoded()
        if str(data.get("_auth_user_id")) == str(request.user.pk):
            active_sessions += 1

    return render(request, "accounts/security.html", {"active_sessions": active_sessions})


@login_required
def logout_other_sessions(request):
    if request.method == "POST":
        current_key = request.session.session_key
        for session in Session.objects.all():
            data = session.get_decoded()
            if str(data.get("_auth_user_id")) == str(request.user.pk) and session.session_key != current_key:
                session.delete()
        messages.success(request, "Signed out of all other sessions.")
    return redirect("accounts:security")


def _authorize_provisioning_request(request):
    provided = request.headers.get("X-Vendor-Provisioning-Key", "")
    return bool(settings.VENDOR_PROVISIONING_KEY) and provided == settings.VENDOR_PROVISIONING_KEY


@csrf_exempt
@require_POST
def provision_account(request):
    """Inbound, server-to-server only. Called by the Vendor Portal whenever it
    creates a customer, rotates a secret, or changes account status. Never
    reachable by a customer's browser session - authenticated purely by the
    shared VENDOR_PROVISIONING_KEY header, not by any user session.
    """
    if not _authorize_provisioning_request(request):
        return JsonResponse({"error": "unauthorized"}, status=401)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    external_id = payload.get("external_id")
    if not external_id:
        return JsonResponse({"error": "external_id is required"}, status=400)

    organization = Organization.objects.filter(external_id=external_id).first()
    is_new_organization = organization is None

    if is_new_organization:
        email = payload.get("email")
        password = payload.get("password")
        if not email or not password:
            return JsonResponse({"error": "email and password are required to provision a new account"}, status=400)

        organization = Organization.objects.create(
            name=payload.get("organization_name", email),
            external_id=external_id,
            api_secret=payload.get("api_secret", ""),
        )
    else:
        if payload.get("organization_name"):
            organization.name = payload["organization_name"]
        if payload.get("api_secret"):
            organization.api_secret = payload["api_secret"]
        organization.save(update_fields=["name", "api_secret", "updated_at"])

    status = payload.get("status", "ACTIVE")
    is_active = status == "ACTIVE"

    if is_new_organization:
        user = CustomerUser.objects.create_user(
            username=payload["email"],
            email=payload["email"],
            password=payload["password"],
            organization=organization,
            is_org_owner=True,
            is_active=is_active,
        )
    else:
        user = CustomerUser.objects.filter(organization=organization).first()
        if user is None:
            email = payload.get("email")
            password = payload.get("password")
            if not email or not password:
                return JsonResponse(
                    {"error": "organization exists with no login yet - email and password are required"}, status=400
                )
            user = CustomerUser.objects.create_user(
                username=email, email=email, password=password, organization=organization, is_org_owner=True
            )
        else:
            if payload.get("email"):
                user.username = payload["email"]
                user.email = payload["email"]
            if payload.get("password"):
                user.set_password(payload["password"])
        user.is_active = is_active
        user.save()

    return JsonResponse({"status": "ok", "external_id": str(organization.external_id)})
