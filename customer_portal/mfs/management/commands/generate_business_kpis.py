from django.core.management.base import BaseCommand, CommandError

from accounts.models import Organization
from mfs.kpis import create_business_kpi_snapshot


class Command(BaseCommand):
    help = "Calculate and persist measured tenant business KPI snapshots."

    def add_arguments(self, parser):
        parser.add_argument("--organization", type=int)
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **options):
        organizations = Organization.objects.filter(pk=options["organization"]) if options["organization"] else Organization.objects.all()
        if not organizations.exists():
            raise CommandError("No matching organization exists")
        for organization in organizations:
            snapshot = create_business_kpi_snapshot(organization, days=min(max(options["days"], 1), 365), generated_by="COMMAND")
            self.stdout.write(self.style.SUCCESS(f"{organization.name}: {snapshot.metrics}"))
