from django.conf import settings
from django.db import models
from django.utils import timezone


class License(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_SUSPENDED = "SUSPENDED"
    STATUS_REVOKED = "REVOKED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_REVOKED, "Revoked"),
    ]

    REASON_PAYMENT_DEFAULT = "PAYMENT_DEFAULT"
    REASON_CHARGEBACK = "CHARGEBACK"
    REASON_FRAUD = "FRAUD"
    REASON_CANCELLED = "SUBSCRIPTION_CANCELLED"
    REASON_ADMIN = "ADMINISTRATIVE_ACTION"
    REVOCATION_REASON_CHOICES = [
        (REASON_PAYMENT_DEFAULT, "Payment default"),
        (REASON_CHARGEBACK, "Chargeback"),
        (REASON_FRAUD, "Fraud"),
        (REASON_CANCELLED, "Subscription cancelled"),
        (REASON_ADMIN, "Administrative action"),
    ]

    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="licenses")
    plan = models.ForeignKey("plans.Plan", on_delete=models.PROTECT, related_name="licenses")

    license_key = models.TextField(unique=True)

    issue_date = models.DateTimeField(default=timezone.now)
    start_date = models.DateTimeField()
    expires_at = models.DateTimeField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="licenses_created"
    )
    revocation_reason = models.CharField(max_length=255, blank=True, default="", choices=REVOCATION_REASON_CHOICES)
    notes = models.TextField(blank=True, default="")

    superseded_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="supersedes"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer.company_name} — {self.plan.name} ({self.status})"

    @property
    def is_expired(self):
        return self.expires_at < timezone.now()

    @property
    def effective_status(self):
        if self.status in (self.STATUS_REVOKED, self.STATUS_SUSPENDED):
            return self.status
        if self.is_expired:
            return self.STATUS_EXPIRED
        return self.status

    @property
    def primary_installation(self):
        return self.installations.order_by("-last_check_in").first()

    @property
    def last_check_in(self):
        installation = self.primary_installation
        return installation.last_check_in if installation else None

    @property
    def agent_version(self):
        installation = self.primary_installation
        return installation.agent_version if installation else ""
