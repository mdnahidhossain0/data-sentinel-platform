from django.contrib.auth.models import AbstractUser
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True, default="")
    timezone = models.CharField(max_length=100, blank=True, default="UTC")

    # Always set by the Vendor Portal's provisioning call (accounts.views.provision_account) -
    # a customer never sets or edits these themselves.
    external_id = models.UUIDField(null=True, blank=True, unique=True)
    api_secret = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def is_linked(self):
        return bool(self.external_id and self.api_secret)


class CustomerUser(AbstractUser):
    organization = models.ForeignKey(
        Organization, null=True, blank=True, on_delete=models.CASCADE, related_name="members"
    )
    is_org_owner = models.BooleanField(default=False)
    phone = models.CharField(max_length=50, blank=True, default="")
