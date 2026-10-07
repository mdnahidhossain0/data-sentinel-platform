import time
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Organization
from mfs.connectors import discover_schema
from mfs.models import DataSource, ReviewDecision
from mfs.services import ingest_transaction, record_review_decision
from mfs.streaming import event_envelope, publish


class Command(BaseCommand):
    help = "Run database discovery (optional) and the real Kafka transaction → risk → alert → review demo."

    def add_arguments(self, parser):
        parser.add_argument("--organization", type=int, required=True)
        parser.add_argument("--reviewer", type=int, required=True)
        parser.add_argument("--source", type=int)
        parser.add_argument("--decision", choices=["APPROVE", "REJECT", "ESCALATE"], default="REJECT")
        parser.add_argument("--timeout", type=int, default=45)

    def handle(self, *args, **options):
        try:
            org = Organization.objects.get(pk=options["organization"])
            reviewer = get_user_model().objects.get(pk=options["reviewer"], organization=org)
        except (Organization.DoesNotExist, get_user_model().DoesNotExist) as error:
            raise CommandError("Organization or tenant reviewer not found") from error
        if options["source"]:
            source = DataSource.objects.get(pk=options["source"], organization=org)
            version, changed = discover_schema(source)
            self.stdout.write(f"1-3. Schema discovery registered v{version.version}; changed={changed}")
        if not org.modelversion_set.filter(status="ACTIVE").exists():
            call_command("train_risk_model", organization=org.pk, rows=4000)
        unique = timezone.now().strftime("%Y%m%d%H%M%S")
        payload = {
            "event_id": str(uuid.uuid4()), "transaction_id": f"DEMO-{unique}", "customer_id": "DEMO-CUSTOMER",
            "amount": 125000, "historical_average_amount": 3500, "occurred_at": timezone.now().isoformat(),
            "status": "SUCCESS", "source": "demo-script", "device_changed": True, "location_changed": True,
            "transactions_last_10_min": 19, "new_beneficiaries": 6,
        }
        tx, event, _ = ingest_transaction(org, payload)
        publish(settings.KAFKA_TOPIC_TRANSACTIONS, event_envelope(event))
        event.status = event.STATUS_PUBLISHED; event.save(update_fields=["status", "updated_at"])
        self.stdout.write(f"4-6. Published {event.event_id} to {settings.KAFKA_TOPIC_TRANSACTIONS}")
        deadline = time.monotonic() + options["timeout"]
        while time.monotonic() < deadline:
            assessment = tx.risk_assessments.first()
            if assessment: break
            time.sleep(1); tx.refresh_from_db()
        else:
            raise CommandError("Timed out waiting for risk worker; confirm consume_mfs_events is running")
        self.stdout.write(f"7-12. Risk {assessment.score}/100 {assessment.level}; alert/review={hasattr(assessment, 'alert')}")
        if not hasattr(assessment, "alert"):
            raise CommandError("Demo event did not exceed the high-risk threshold")
        decision = record_review_decision(assessment.alert.review_case, reviewer, options["decision"], "End-to-end demo decision")
        self.stdout.write(self.style.SUCCESS(f"13-16. Review {decision.decision} recorded, audited, labeled, and queued for publication. Transaction={tx.external_id}"))
