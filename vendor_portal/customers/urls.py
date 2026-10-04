from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("new/", views.customer_create, name="create"),
    path("<int:pk>/", views.customer_detail, name="detail"),
    path("<int:pk>/edit/", views.customer_edit, name="edit"),
    path("<int:pk>/suspend/", views.customer_suspend, name="suspend"),
    path("<int:pk>/reactivate/", views.customer_reactivate, name="reactivate"),
    path("<int:pk>/archive/", views.customer_archive, name="archive"),
    path("<int:pk>/api-secret/", views.customer_regenerate_api_secret, name="api_secret"),
    path("<int:pk>/retry-portal-sync/", views.customer_retry_portal_sync, name="retry_portal_sync"),
    path("<int:pk>/reset-portal-password/", views.customer_reset_portal_password, name="reset_portal_password"),
]
