from django.core.management.base import BaseCommand, CommandError

from accounts.models import Organization
from mfs.models import IngestionAPIKey


class Command(BaseCommand):
    help = "Issue a tenant-scoped MFS ingestion API key; the secret is shown once."

    def add_arguments(self, parser):
        parser.add_argument("--organization", type=int, required=True)
        parser.add_argument("--name", default="default-ingestion")

    def handle(self, *args, **options):
        try:
            organization = Organization.objects.get(pk=options["organization"])
        except Organization.DoesNotExist as error:
            raise CommandError("Organization not found") from error
        key, raw = IngestionAPIKey.issue(organization, options["name"])
        self.stdout.write(self.style.SUCCESS(f"Created API key {key.pk}. Store this value now; it cannot be retrieved again:\n{raw}"))
