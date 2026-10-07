from django.core.management.base import BaseCommand, CommandError

from accounts.models import Organization
from mfs.ml import train_model


class Command(BaseCommand):
    help = "Train and activate the explainable hybrid risk model on a labeled synthetic prototype dataset."

    def add_arguments(self, parser):
        parser.add_argument("--organization", type=int)
        parser.add_argument("--rows", type=int, default=8000)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **options):
        organizations = Organization.objects.filter(pk=options["organization"]) if options["organization"] else Organization.objects.all()
        if not organizations.exists(): raise CommandError("No matching organization exists")
        for organization in organizations:
            model = train_model(organization, rows=options["rows"], seed=options["seed"])
            self.stdout.write(self.style.SUCCESS(f"{organization.name}: {model.version} {model.metrics}"))
