from django.urls import path

from . import views

app_name = "mfs"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("business-kpis/", views.business_kpis, name="business_kpis"),
    path("transactions/", views.transaction_list, name="transactions"),
    path("transactions/<int:pk>/", views.transaction_detail, name="transaction_detail"),
    path("alerts/", views.alert_list, name="alerts"),
    path("reviews/", views.review_queue, name="reviews"),
    path("reviews/<int:pk>/", views.review_detail, name="review_detail"),
    path("data-sources/", views.data_sources, name="data_sources"),
    path("data-sources/new/", views.data_source_create, name="data_source_create"),
    path("data-sources/<int:pk>/discover/", views.discover_data_source, name="discover_data_source"),
    path("data-sources/<int:pk>/schema/", views.schema_detail, name="schema_detail"),
    path("models/", views.model_monitor, name="model_monitor"),
    path("api-keys/", views.api_keys, name="api_keys"),
    path("api-keys/<int:pk>/revoke/", views.api_key_revoke, name="api_key_revoke"),
    path("assistant/", views.assistant, name="assistant"),
]
