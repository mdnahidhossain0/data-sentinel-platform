import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Organization
from mfs.models import MfsCustomer
from mfs.risk import assess_transaction
from mfs.services import ingest_transaction


class Command(BaseCommand):
    help = "Load clearly labeled synthetic MFS transactions and score them for the demo."

    def add_arguments(self, parser):
        parser.add_argument("--organization", type=int, required=True)
        parser.add_argument("--count", type=int, default=250)
        parser.add_argument("--seed", type=int, default=17)

    def handle(self, *args, **options):
        try: organization = Organization.objects.get(pk=options["organization"])
        except Organization.DoesNotExist as error: raise CommandError("Organization not found") from error
        rng = random.Random(options["seed"])
        for index in range(options["count"]):
            risky = index % 11 == 0
            payload = {
                "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"demo-{organization.pk}-{options['seed']}-{index}")),
                "transaction_id": f"SYN-{options['seed']}-{index:06d}", "customer_id": f"CUS-{index % 50:04d}",
                "amount": round(rng.uniform(50000, 160000) if risky else rng.uniform(50, 12000), 2),
                "historical_average_amount": round(rng.uniform(300, 5000), 2), "currency": "BDT",
                "occurred_at": (timezone.now() - timedelta(minutes=index * 3)).isoformat(),
                "status": "SUCCESS" if rng.random() > .08 else "FAILED", "source": "synthetic-demo",
                "device_changed": risky, "location_changed": risky and index % 2 == 0,
                "transactions_last_10_min": rng.randint(12, 25) if risky else rng.randint(0, 5),
                "new_beneficiaries": rng.randint(3, 8) if risky else rng.randint(0, 1),
            }
            tx, _, created = ingest_transaction(organization, payload)
            if created: assess_transaction(tx)
        self.stdout.write(self.style.SUCCESS(f"Synthetic demo ready for {organization.name}"))
