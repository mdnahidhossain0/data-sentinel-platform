from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from api_client.client import SentinelCloudUnauthorized, SentinelCloudUnavailable, get_client_for_organization


@login_required
def installation_list(request):
    organization = request.user.organization
    context = {"installations": [], "error": None}

    if not organization or not organization.is_linked:
        context["error"] = "not_linked"
        return render(request, "installations/installation_list.html", context)

    client = get_client_for_organization(organization)
    try:
        status = client.get_partner_status()
    except SentinelCloudUnauthorized:
        context["error"] = "unauthorized"
    except SentinelCloudUnavailable:
        context["error"] = "unavailable"
    else:
        context["installations"] = status.get("installations", [])

    return render(request, "installations/installation_list.html", context)
