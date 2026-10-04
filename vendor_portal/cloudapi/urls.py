from django.urls import path

from . import views

app_name = "cloudapi"

urlpatterns = [
    path("check-in/", views.check_in, name="check_in"),
    path("partner/status/", views.partner_status, name="partner_status"),
]
