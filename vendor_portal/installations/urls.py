from django.urls import path

from . import views

app_name = "installations"

urlpatterns = [
    path("", views.installation_list, name="list"),
    path("<int:pk>/", views.installation_detail, name="detail"),
]
