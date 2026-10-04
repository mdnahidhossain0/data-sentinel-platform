from django.contrib import admin

from .models import InsightsReport


@admin.register(InsightsReport)
class InsightsReportAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "status", "window_days", "created_at")
    list_filter = ("status",)
    readonly_fields = ("summary", "trend", "anomalies", "insight_text", "created_at")

    def has_add_permission(self, request):
        return False
