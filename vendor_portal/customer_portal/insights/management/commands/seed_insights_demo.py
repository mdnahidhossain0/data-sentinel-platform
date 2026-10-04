from django.core.management.base import BaseCommand

from insights.seed import seed_demo_orders


class Command(BaseCommand):
    help = "Populates the bundled demo SQLite database with ~120 days of order data, including a deliberate recent dip."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=120)

    def handle(self, *args, **options):
        count = seed_demo_orders(days=options["days"])
        self.stdout.write(self.style.SUCCESS(f"Seeded {count} demo orders."))
