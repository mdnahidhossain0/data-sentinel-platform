import logging
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Organization
from mfs.models import Transaction, TransactionEvent
from mfs.event_schemas import validate_event
from mfs.risk import assess_transaction
from mfs.streaming import consumer, publish

logger = logging.getLogger(__name__)


def _valid_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


class Command(BaseCommand):
    help = "Consume Kafka transaction events and emit risk/alert events."

    def add_arguments(self, parser):
        parser.add_argument("--max-messages", type=int, default=0)

    def handle(self, *args, **options):
        client = consumer()
        handled = 0
        try:
            for message in client:
                payload = message.value
                event = None
                try:
                    validate_event(payload, required=("transaction_id",))
                    organization = Organization.objects.get(external_id=payload["tenant_id"])
                    event = TransactionEvent.objects.select_related("transaction").get(organization=organization, event_id=payload["event_id"])
                    if event.status == event.STATUS_PROCESSED:
                        client.commit(); continue
                    assessment = event.transaction.risk_assessments.first() or assess_transaction(event.transaction)
                    risk_payload = {**payload, "event_id": str(uuid.uuid4()), "event_type": "risk.assessed",
                                    "timestamp": timezone.now().isoformat(), "source": "risk-worker",
                                    "risk_score": assessment.score, "risk_level": assessment.level,
                                    "decision": assessment.decision, "model_version": assessment.model_version.version}
                    publish(settings.KAFKA_TOPIC_RISK, risk_payload)
                    if assessment.level == "HIGH":
                        publish(settings.KAFKA_TOPIC_ALERTS, {**risk_payload, "event_id": str(uuid.uuid4()),
                                "event_type": "alert.created", "alert_id": assessment.alert.pk, "status": "NEW"})
                    event.status, event.error_code = event.STATUS_PROCESSED, ""
                    event.save(update_fields=["status", "error_code", "updated_at"])
                    client.commit()
                    handled += 1
                except Exception as error:
                    logger.exception("Failed to process Kafka event_id=%s", payload.get("event_id"))
                    if event:
                        event.status, event.error_code, event.retry_count = event.STATUS_FAILED, error.__class__.__name__[:64], event.retry_count + 1
                        event.save(update_fields=["status", "error_code", "retry_count", "updated_at"])
                    try:
                        publish(settings.KAFKA_TOPIC_DLQ, {
                            "event_id": str(uuid.uuid4()),
                            "event_type": "event.failed", "tenant_id": payload.get("tenant_id", "unknown"),
                            "source": "risk-worker", "timestamp": payload.get("timestamp", "1970-01-01T00:00:00+00:00"),
                            "correlation_id": payload.get("correlation_id", "00000000-0000-0000-0000-000000000000") if _valid_uuid(payload.get("correlation_id")) else "00000000-0000-0000-0000-000000000000",
                            "schema_version": "1.0", "original_event_type": payload.get("event_type", "unknown"),
                            "error_type": error.__class__.__name__,
                        })
                    except Exception:
                        logger.exception("DLQ publish also failed for source event_id=%s", payload.get("event_id"))
                    client.commit()
                if options["max_messages"] and handled >= options["max_messages"]: break
        finally:
            client.close()
