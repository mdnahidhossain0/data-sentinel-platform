import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Installation(models.Model):
    STATUS_ONLINE = "ONLINE"
    STATUS_OFFLINE = "OFFLINE"
    STATUS_REVOKED = "REVOKED"
    STATUS_EXPIRED = "EXPIRED"

    installation_id = models.UUIDField(default=uuid.uuid4, unique=True)
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="installations")
    license = models.ForeignKey(
        "licenses.License", null=True, blank=True, on_delete=models.SET_NULL, related_name="installations"
    )

    agent_version = models.CharField(max_length=50, blank=True, default="")
    operating_system = models.CharField(max_length=100, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    first_seen = models.DateTimeField(auto_now_add=True)
    last_check_in = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_check_in"]

    def __str__(self):
        return f"{self.customer.company_name} — {self.installation_id}"

    @property
    def status(self):
        if self.license is None:
            return self.STATUS_OFFLINE
        if self.license.effective_status == "REVOKED":
            return self.STATUS_REVOKED
        if self.license.effective_status == "EXPIRED":
            return self.STATUS_EXPIRED
        if not self.last_check_in:
            return self.STATUS_OFFLINE
        offline_after = timezone.timedelta(minutes=settings.INSTALLATION_OFFLINE_AFTER_MINUTES)
        if timezone.now() - self.last_check_in > offline_after:
            return self.STATUS_OFFLINE
        return self.STATUS_ONLINE
