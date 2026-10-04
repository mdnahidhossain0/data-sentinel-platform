from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from api_client.client import SentinelCloudUnauthorized, SentinelCloudUnavailable, get_client_for_organization


@login_required
def home(request):
    organization = request.user.organization
    context = {"organization": organization, "license": None, "installations": [], "error": None, "days_remaining": None}

    if not organization or not organization.is_linked:
        context["error"] = "not_linked"
        return render(request, "dashboard/home.html", context)

    client = get_client_for_organization(organization)
    try:
        status = client.get_partner_status()
    except SentinelCloudUnauthorized:
        context["error"] = "unauthorized"
    except SentinelCloudUnavailable:
        context["error"] = "unavailable"
    else:
        license_data = status.get("license")
        installations = status.get("installations", [])
        context["license"] = license_data
        context["installations"] = installations
        context["online_count"] = len([i for i in installations if i.get("status") == "ONLINE"])

        if license_data and license_data.get("expires_at"):
            expires_at = datetime.fromisoformat(license_data["expires_at"])
            context["days_remaining"] = max((expires_at - timezone.now()).days, 0)

    return render(request, "dashboard/home.html", context)
