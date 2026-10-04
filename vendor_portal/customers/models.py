import secrets
import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class Customer(models.Model):
    STATUS_ACTIVE = "ACTIVE"
    STATUS_SUSPENDED = "SUSPENDED"
    STATUS_ARCHIVED = "ARCHIVED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    external_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    company_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    organization_type = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    notes = models.TextField(blank=True, default="")

    api_secret_hash = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_name"]

    def __str__(self):
        return self.company_name

    def set_api_secret(self):
        raw_secret = secrets.token_urlsafe(32)
        self.api_secret_hash = make_password(raw_secret)
        return raw_secret

    def check_api_secret(self, raw_secret):
        if not self.api_secret_hash:
            return False
        return check_password(raw_secret, self.api_secret_hash)

    @property
    def current_license(self):
        ordered = self.licenses.order_by("-expires_at")
        return ordered.exclude(status="REVOKED").first() or ordered.first()
