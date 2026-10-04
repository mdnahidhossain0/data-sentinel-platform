from django.contrib.auth.models import AbstractUser
from django.db import models


class StaffUser(AbstractUser):
    ROLE_SUPER_ADMIN = "SUPER_ADMIN"
    ROLE_LICENSE_MANAGER = "LICENSE_MANAGER"
    ROLE_SUPPORT_AGENT = "SUPPORT_AGENT"
    ROLE_VIEWER = "VIEWER"
    ROLE_CHOICES = [
        (ROLE_SUPER_ADMIN, "Super Admin"),
        (ROLE_LICENSE_MANAGER, "License Manager"),
        (ROLE_SUPPORT_AGENT, "Support Agent"),
        (ROLE_VIEWER, "Viewer"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_VIEWER)
    two_factor_enabled = models.BooleanField(default=False)

    @property
    def can_manage_licenses(self):
        return self.role in (self.ROLE_SUPER_ADMIN, self.ROLE_LICENSE_MANAGER) or self.is_superuser

    @property
    def can_manage_admins(self):
        return self.role == self.ROLE_SUPER_ADMIN or self.is_superuser
