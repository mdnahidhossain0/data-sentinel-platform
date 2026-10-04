from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from api_client.client import SentinelCloudUnauthorized, SentinelCloudUnavailable, get_client_for_organization


def _fetch_status(organization):
    client = get_client_for_organization(organization)
    return client.get_partner_status()


@login_required
def license_detail(request):
    organization = request.user.organization
    context = {"organization": organization, "license": None, "error": None}

    if not organization or not organization.is_linked:
        context["error"] = "not_linked"
        return render(request, "licenses/license_detail.html", context)

    try:
        status = _fetch_status(organization)
    except SentinelCloudUnauthorized:
        context["error"] = "unauthorized"
    except SentinelCloudUnavailable:
        context["error"] = "unavailable"
    else:
        license_data = status.get("license")
        if license_data:
            license_data = {k: v for k, v in license_data.items() if k != "license_key"}
        context["license"] = license_data
        context["customer"] = status.get("customer")

    return render(request, "licenses/license_detail.html", context)


@require_POST
@login_required
def license_reveal(request):
    organization = request.user.organization
    if not organization or not organization.is_linked:
        return JsonResponse({"error": "not_linked"}, status=400)

    try:
        status = _fetch_status(organization)
    except SentinelCloudUnauthorized:
        return JsonResponse({"error": "unauthorized"}, status=401)
    except SentinelCloudUnavailable:
        return JsonResponse({"error": "unavailable"}, status=503)

    license_data = status.get("license")
    if not license_data:
        return JsonResponse({"error": "no_license"}, status=404)

    return JsonResponse({"license_key": license_data["license_key"]})
