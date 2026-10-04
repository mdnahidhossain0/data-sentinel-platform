from django.core.management.base import BaseCommand
from django.utils import timezone

from customers.models import Customer
from licenses.services import generate_license
from plans.models import Plan


class Command(BaseCommand):
    help = "Seeds the Monthly/Yearly plans and one demo customer with an active license."

    def handle(self, *args, **options):
        monthly, _ = Plan.objects.update_or_create(
            code="monthly",
            defaults={
                "name": "Monthly",
                "billing_interval": Plan.INTERVAL_MONTH,
                "price_usd": 29,
                "duration_days": 31,
                "max_installations": 1,
                "is_active": True,
            },
        )
        yearly, _ = Plan.objects.update_or_create(
            code="yearly",
            defaults={
                "name": "Yearly",
                "billing_interval": Plan.INTERVAL_YEAR,
                "price_usd": 249,
                "duration_days": 366,
                "max_installations": 3,
                "is_active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("Plans ready: Monthly ($29), Yearly ($249)."))

        customer, created = Customer.objects.get_or_create(
            email="ops@acme-university.example",
            defaults={"company_name": "Acme University", "contact_person": "Jordan Lee", "country": "United States"},
        )
        if created:
            license_obj = generate_license(customer=customer, plan=yearly, start_date=timezone.now())
            self.stdout.write(self.style.SUCCESS(f"Demo customer created with license #{license_obj.pk}."))
        else:
            self.stdout.write("Demo customer already exists — skipped.")
