from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from accounts.views import provision_account


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz/", health, name="health"),
    path("internal/provision/", provision_account, name="provision_account"),
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("accounts/", include("accounts.urls")),
    path("license/", include("licenses.urls")),
    path("installations/", include("installations.urls")),
    path("support/", include("support.urls")),
    path("insights/", include("insights.urls")),
    path("mfs/", include("mfs.urls")),
    path("api/v1/", include("mfs.api_urls")),
]
