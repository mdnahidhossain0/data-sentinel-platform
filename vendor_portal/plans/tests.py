import re

from django.test import Client, TestCase

from accounts.models import StaffUser
from plans.models import Plan


class PlanToggleTests(TestCase):
    def setUp(self):
        self.user = StaffUser.objects.create_user(
            username="license-manager",
            password="staff-pass-12345",
            role=StaffUser.ROLE_LICENSE_MANAGER,
        )
        self.plan = Plan.objects.create(
            code="yearly",
            name="Yearly",
            billing_interval=Plan.INTERVAL_YEAR,
            price_usd="249.00",
            duration_days=365,
        )

    def test_toggle_form_includes_csrf_token_and_deactivates_plan(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        response = client.get("/plans/")
        token = re.search(
            rb'name="csrfmiddlewaretoken" value="([^"]+)"',
            response.content,
        ).group(1).decode()

        response = client.post(
            f"/plans/{self.plan.pk}/toggle/",
            {"csrfmiddlewaretoken": token},
        )

        self.assertRedirects(response, "/plans/")
        self.plan.refresh_from_db()
        self.assertFalse(self.plan.is_active)
