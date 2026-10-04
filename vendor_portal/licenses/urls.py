from django.urls import path

from . import views

app_name = "licenses"

urlpatterns = [
    path("", views.license_list, name="list"),
    path("export/", views.license_export, name="export"),
    path("generate/", views.license_generate, name="generate"),
    path("<int:pk>/", views.license_detail, name="detail"),
    path("<int:pk>/revoke/", views.license_revoke, name="revoke"),
    path("<int:pk>/suspend/", views.license_suspend, name="suspend"),
    path("<int:pk>/reactivate/", views.license_reactivate, name="reactivate"),
    path("<int:pk>/extend/", views.license_extend, name="extend"),
    path("<int:pk>/change-plan/", views.license_change_plan, name="change_plan"),
    path("<int:pk>/regenerate/", views.license_regenerate, name="regenerate"),
    path("<int:pk>/download/", views.license_download, name="download"),
]
