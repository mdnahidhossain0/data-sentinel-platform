from django.urls import path

from . import views

app_name = "insights"

urlpatterns = [
    path("", views.report_list, name="list"),
    path("run/", views.run_report, name="run"),
    path("seed-demo/", views.seed_demo, name="seed_demo"),
    path("<int:pk>/", views.report_detail, name="detail"),
]
