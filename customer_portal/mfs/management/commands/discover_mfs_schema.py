from django.core.management.base import BaseCommand, CommandError

from mfs.connectors import discover_schema
from mfs.models import DataSource


class Command(BaseCommand):
    help = "Discover schemas for one or all configured MFS data sources."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=int)

    def handle(self, *args, **options):
        sources = DataSource.objects.filter(pk=options["source"]) if options["source"] else DataSource.objects.all()
        if not sources.exists(): raise CommandError("No matching data source exists")
        for source in sources:
            try:
                version, changed = discover_schema(source)
                self.stdout.write(self.style.SUCCESS(f"{source.name}: schema v{version.version} ({'changed' if changed else 'unchanged'})"))
            except Exception as error:
                source.status = "ERROR"
                source.save(update_fields=["status", "updated_at"])
                self.stderr.write(f"{source.name}: {error}")
