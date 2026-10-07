from django.urls import path

from . import api_views

urlpatterns = [
    path("mfs/transactions/ingest/", api_views.ingest, name="mfs_ingest"),
    path("risk/predict/", api_views.predict, name="risk_predict"),
]
