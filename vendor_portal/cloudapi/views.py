import json

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from audit.services import log_system_action
from installations.models import Installation
from licenses.crypto import InvalidLicenseKey, verify_license_key
from licenses.models import License

from .auth import authenticate_partner
from .ratelimit import is_rate_limited

from django.conf import settings
from django.http import JsonResponse


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@csrf_exempt
@require_POST
def check_in(request):
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    required_fields = {"license_key", "installation_id", "agent_version", "plan"}
    if not required_fields.issubset(body):
        return JsonResponse({"error": "missing required fields"}, status=400)

    client_ip = _client_ip(request)
    if is_rate_limited(f"checkin:{client_ip}", settings.RATE_LIMIT_CHECKIN_PER_MINUTE):
        return JsonResponse({"error": "rate limit exceeded"}, status=429)

    license_key = body["license_key"]

    try:
        verify_license_key(license_key)
    except InvalidLicenseKey:
        return JsonResponse({
            "license_status": "INVALID",
            "revoked": True,
            "server_time": timezone.now().isoformat(),
        })

    try:
        license_obj = License.objects.select_related("customer").get(license_key=license_key)
    except License.DoesNotExist:
        return JsonResponse({
            "license_status": "UNKNOWN",
            "revoked": True,
            "server_time": timezone.now().isoformat(),
        })

    installation, _ = Installation.objects.get_or_create(
        installation_id=body["installation_id"],
        defaults={"customer": license_obj.customer},
    )
    installation.customer = license_obj.customer
    installation.license = license_obj
    installation.agent_version = body["agent_version"]
    installation.ip_address = client_ip
    installation.last_check_in = timezone.now()
    installation.save()

    log_system_action(
        "cloud_check_in",
        target=installation,
        metadata={"license_id": license_obj.pk, "agent_version": body["agent_version"]},
    )

    effective_status = license_obj.effective_status
    next_check_in = settings.CHECK_IN_INTERVAL_SECONDS

    return JsonResponse({
        "license_status": effective_status,
        "expiry": license_obj.expires_at.isoformat(),
        "revoked": effective_status == License.STATUS_REVOKED,
        "server_time": timezone.now().isoformat(),
        "next_check_in": next_check_in,
    })


@require_GET
def partner_status(request):
    customer = authenticate_partner(request)
    if customer is None:
        log_system_action("partner_api_auth_failed", metadata={"ip": _client_ip(request)})
        return JsonResponse({"error": "unauthorized"}, status=401)

    if is_rate_limited(f"partner:{customer.pk}", settings.RATE_LIMIT_CHECKIN_PER_MINUTE):
        return JsonResponse({"error": "rate limit exceeded"}, status=429)

    log_system_action("partner_api_access", target=customer, metadata={"ip": _client_ip(request)})

    license_obj = customer.current_license
    license_payload = None
    if license_obj is not None:
        license_payload = {
            "license_key": license_obj.license_key,
            "status": license_obj.effective_status,
            "plan": license_obj.plan.code,
            "plan_name": license_obj.plan.name,
            "price_usd": str(license_obj.plan.price_usd),
            "billing_interval": license_obj.plan.billing_interval,
            "issue_date": license_obj.issue_date.isoformat(),
            "start_date": license_obj.start_date.isoformat(),
            "expires_at": license_obj.expires_at.isoformat(),
            "max_installations": license_obj.plan.max_installations,
        }

    installations_payload = [
        {
            "installation_id": str(installation.installation_id),
            "agent_version": installation.agent_version,
            "operating_system": installation.operating_system,
            "last_check_in": installation.last_check_in.isoformat() if installation.last_check_in else None,
            "status": installation.status,
        }
        for installation in customer.installations.all()
    ]

    return JsonResponse({
        "customer": {"company_name": customer.company_name, "status": customer.status},
        "license": license_payload,
        "installations": installations_payload,
        "server_time": timezone.now().isoformat(),
    })
