from django.urls import path

from . import views

app_name = "installations"

urlpatterns = [
    path("", views.installation_list, name="list"),
]
