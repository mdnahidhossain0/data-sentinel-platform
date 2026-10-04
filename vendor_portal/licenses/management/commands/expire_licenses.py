from django.core.management.base import BaseCommand
from django.utils import timezone

from audit.services import log_system_action
from licenses.models import License


class Command(BaseCommand):
    help = "Marks ACTIVE licenses past their expiry date as EXPIRED. Safe to run frequently via cron."

    def handle(self, *args, **options):
        overdue = License.objects.filter(status=License.STATUS_ACTIVE, expires_at__lt=timezone.now())
        count = 0
        for license_obj in overdue:
            license_obj.status = License.STATUS_EXPIRED
            license_obj.save(update_fields=["status", "updated_at"])
            log_system_action("license_expired", target=license_obj)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Marked {count} license(s) as expired."))
