from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q
from django.utils import timezone
import uuid

from accounts.models import Organization
from mfs.audit import audit
from mfs.models import DataPipeline, DataQualityMetric, ReviewDecision, RiskAssessment, Transaction, TransactionEvent
from mfs.kpis import create_business_kpi_snapshot
from mfs.streaming import event_envelope, publish


ACTIONS = ["validate_ingestion", "data_quality", "historical_backfill", "prepare_features", "train_model",
           "evaluate_model", "discover_schemas", "aggregate_analytics", "risk_report", "recover_failed"]


class Command(BaseCommand):
    help = "Execute one auditable Airflow-managed MFS pipeline operation."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=ACTIONS)
        parser.add_argument("--organization", type=int)

    def handle(self, *args, **options):
        action = options["action"]
        organizations = Organization.objects.filter(pk=options["organization"]) if options["organization"] else Organization.objects.all()
        if action == "discover_schemas": call_command("discover_mfs_schema"); return
        for org in organizations:
            pipeline, _ = DataPipeline.objects.get_or_create(organization=org, name=action, defaults={"pipeline_type": "AIRFLOW"})
            pipeline.status, pipeline.last_run_at = "RUNNING", timezone.now(); pipeline.save()
            try:
                metadata, processed = self._run(action, org)
                pipeline.status, pipeline.last_success_at = "SUCCESS", timezone.now()
                pipeline.records_processed += processed; pipeline.metadata = metadata; pipeline.save()
                audit("pipeline.completed", organization=org, target=pipeline, metadata=metadata)
                if action in {"validate_ingestion", "data_quality"} and org.external_id:
                    try:
                        publish(settings.KAFKA_TOPIC_DATA_QUALITY, {
                            "event_id": str(uuid.uuid4()), "event_type": "data_quality.measured",
                            "tenant_id": str(org.external_id), "source": "airflow",
                            "timestamp": timezone.now().isoformat(), "correlation_id": str(uuid.uuid4()),
                            "schema_version": "1.0", "pipeline": action, "metrics": metadata,
                        })
                    except Exception as error:
                        self.stderr.write(f"Data-quality event publish failed ({error.__class__.__name__})")
            except Exception as error:
                pipeline.status, pipeline.errors = "FAILED", pipeline.errors + 1; pipeline.metadata = {"error_type": error.__class__.__name__}; pipeline.save()
                raise

    def _run(self, action, org):
        if action == "train_model": call_command("train_risk_model", organization=org.pk); return {"trained": True}, 1
        if action == "validate_ingestion":
            total = TransactionEvent.objects.filter(organization=org).count()
            failed = TransactionEvent.objects.filter(organization=org, status="FAILED").count()
            DataQualityMetric.objects.create(organization=org, metric_name="ingestion_failure_rate", value=failed / max(total, 1), threshold=.01, passed=failed / max(total, 1) <= .01)
            return {"total": total, "failed": failed}, total
        if action == "data_quality":
            total = Transaction.objects.filter(organization=org).count()
            invalid = Transaction.objects.filter(organization=org).filter(Q(amount__lt=0) | Q(customer__isnull=True)).count()
            DataQualityMetric.objects.create(organization=org, metric_name="invalid_transaction_rate", value=invalid / max(total, 1), threshold=.001, passed=invalid == 0)
            return {"total": total, "invalid": invalid}, total
        if action == "recover_failed":
            recovered = 0
            for event in TransactionEvent.objects.select_related("transaction", "organization").filter(organization=org, status="FAILED"):
                try:
                    publish(settings.KAFKA_TOPIC_TRANSACTIONS, event_envelope(event))
                except Exception:
                    continue
                event.status, event.error_code = event.STATUS_PUBLISHED, ""
                event.save(update_fields=["status", "error_code", "updated_at"])
                recovered += 1
            return {"republished": recovered}, recovered
        if action == "evaluate_model":
            model = org.modelversion_set.filter(status="ACTIVE").first()
            return {"metrics": model.metrics if model else {}, "synthetic": bool(model and model.is_synthetic)}, 1 if model else 0
        if action == "risk_report":
            snapshot = create_business_kpi_snapshot(org, days=30, generated_by="AIRFLOW")
            return snapshot.metrics, snapshot.metrics["transactions_total"]
        if action == "aggregate_analytics":
            stats = RiskAssessment.objects.filter(organization=org).aggregate(total=Count("id"), high=Count("id", filter=Q(level="HIGH")))
            reviewed = ReviewDecision.objects.filter(organization=org).count()
            stats["reviewed"] = reviewed
            return stats, stats["total"]
        if action in {"historical_backfill", "prepare_features"}:
            count = Transaction.objects.filter(organization=org).count()
            return {"eligible_transactions": count}, count
        raise CommandError("Unsupported action")
