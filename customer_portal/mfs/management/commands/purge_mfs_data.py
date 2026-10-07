from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from mfs.audit import audit
from mfs.models import MfsAuditEvent, Transaction


class Command(BaseCommand):
    help = "Apply the configured transaction retention period; audit records are retained separately."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=settings.MFS_RETENTION_DAYS)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(days=max(options["days"], 1))
        queryset = Transaction.objects.filter(occurred_at__lt=cutoff)
        counts = list(queryset.values("organization_id").annotate(total=Count("id")))
        self.stdout.write(f"Transactions eligible for deletion: {sum(item['total'] for item in counts)}")
        if options["dry_run"]: return
        for item in counts:
            audit("retention.transactions_deleted", organization_id=item["organization_id"], metadata={"count": item["total"], "cutoff": cutoff.isoformat()})
        queryset.delete()
