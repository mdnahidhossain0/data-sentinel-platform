from django.urls import path

from . import views

app_name = "licenses"

urlpatterns = [
    path("", views.license_detail, name="detail"),
    path("reveal/", views.license_reveal, name="reveal"),
]
