import os
import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Organization
from mfs.ml import train_model
from mfs.models import BusinessKPISnapshot, IngestionAPIKey, ModelVersion, Transaction


class Command(BaseCommand):
    help = "Create an isolated local load-test tenant, admin, API key, and active model."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-data", action="store_true",
            help="Delete prior transaction/KPI evidence for only the isolated load-test tenant before running.",
        )

    def handle(self, *args, **options):
        password = os.environ.get("LOADTEST_ADMIN_PASSWORD", "")
        if len(password) < 12:
            raise CommandError("LOADTEST_ADMIN_PASSWORD must be set and contain at least 12 characters")
        organization, _ = Organization.objects.get_or_create(
            name="Scalability Verification Tenant",
            defaults={"external_id": uuid.uuid5(uuid.NAMESPACE_DNS, "loadtest.data-sentinel.local")},
        )
        if not organization.external_id:
            organization.external_id = uuid.uuid5(uuid.NAMESPACE_DNS, "loadtest.data-sentinel.local")
            organization.save(update_fields=["external_id", "updated_at"])
        user_model = get_user_model()
        user, _ = user_model.objects.get_or_create(
            username="loadtest@example.com",
            defaults={"email": "loadtest@example.com", "organization": organization,
                      "is_org_owner": True, "role": user_model.ROLE_ORG_ADMIN},
        )
        user.organization = organization
        user.role = user_model.ROLE_ORG_ADMIN
        user.is_org_owner = True
        user.set_password(password)
        user.save()
        if options["reset_data"]:
            Transaction.objects.filter(organization=organization).delete()
            BusinessKPISnapshot.objects.filter(organization=organization).delete()
        if not ModelVersion.objects.filter(organization=organization, status=ModelVersion.STATUS_ACTIVE).exists():
            train_model(organization, rows=4000, seed=42)
        IngestionAPIKey.objects.filter(organization=organization, name="locust-load-test").update(is_active=False)
        _, raw = IngestionAPIKey.issue(organization, "locust-load-test")
        self.stdout.write(f"ORGANIZATION_ID={organization.pk}")
        self.stdout.write("LOGIN_EMAIL=loadtest@example.com")
        self.stdout.write(f"MFS_API_KEY={raw}")
