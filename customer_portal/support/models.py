from django.conf import settings
from django.db import models


class SupportTicket(models.Model):
    PRIORITY_LOW = "LOW"
    PRIORITY_NORMAL = "NORMAL"
    PRIORITY_HIGH = "HIGH"
    PRIORITY_CHOICES = [(PRIORITY_LOW, "Low"), (PRIORITY_NORMAL, "Normal"), (PRIORITY_HIGH, "High")]

    STATUS_OPEN = "OPEN"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_RESOLVED = "RESOLVED"
    STATUS_CLOSED = "CLOSED"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_CLOSED, "Closed"),
    ]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="tickets")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets")

    subject = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject
