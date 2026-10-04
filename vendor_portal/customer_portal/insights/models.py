from django.conf import settings
from django.db import models


class InsightsReport(models.Model):
    STATUS_OK = "OK"
    STATUS_NO_DATA = "NO_DATA"
    STATUS_ERROR = "ERROR"
    STATUS_CHOICES = [(STATUS_OK, "OK"), (STATUS_NO_DATA, "No data"), (STATUS_ERROR, "Error")]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="insights_reports")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    window_days = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OK)
    error_message = models.CharField(max_length=500, blank=True, default="")

    summary = models.JSONField(default=dict, blank=True)
    trend = models.JSONField(default=dict, blank=True, null=True)
    anomalies = models.JSONField(default=list, blank=True)
    insight_text = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Insights report #{self.pk} ({self.status})"
