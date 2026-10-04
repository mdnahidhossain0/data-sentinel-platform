from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz/", health, name="health"),
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("accounts/", include("accounts.urls")),
    path("customers/", include("customers.urls")),
    path("plans/", include("plans.urls")),
    path("licenses/", include("licenses.urls")),
    path("installations/", include("installations.urls")),
    path("audit/", include("audit.urls")),
    path("api/v1/", include("cloudapi.urls")),
]
