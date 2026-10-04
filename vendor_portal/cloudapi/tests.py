import json

from django.test import Client, TestCase
from django.utils import timezone

from customers.models import Customer
from installations.models import Installation
from licenses import services
from licenses.models import License
from plans.models import Plan


class CheckInApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = Customer.objects.create(company_name="Acme University", email="ops@acme.example")
        self.plan = Plan.objects.create(
            code="yearly", name="Yearly", billing_interval=Plan.INTERVAL_YEAR,
            price_usd=249, duration_days=366, max_installations=3,
        )
        self.license_obj = services.generate_license(self.customer, self.plan, start_date=timezone.now())

    def _check_in(self, installation_id="11111111-1111-1111-1111-111111111111"):
        return self.client.post(
            "/api/v1/check-in/",
            data=json.dumps({
                "license_key": self.license_obj.license_key,
                "installation_id": installation_id,
                "agent_version": "1.0.0",
                "plan": "yearly",
            }),
            content_type="application/json",
        )

    def test_valid_license_checks_in_and_registers_installation(self):
        response = self._check_in()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["license_status"], "ACTIVE")
        self.assertFalse(body["revoked"])
        self.assertTrue(Installation.objects.filter(customer=self.customer).exists())

    def test_revoked_license_reports_revoked(self):
        services.revoke_license(self.license_obj, reason=License.REASON_FRAUD)
        response = self._check_in()
        body = response.json()
        self.assertEqual(body["license_status"], "REVOKED")
        self.assertTrue(body["revoked"])

    def test_unknown_license_key_is_rejected(self):
        self.license_obj.license_key = "DSK1.notreal.notreal"
        response = self._check_in()
        self.assertEqual(response.json()["license_status"], "INVALID")

    def test_missing_fields_returns_400(self):
        response = self.client.post("/api/v1/check-in/", data=json.dumps({}), content_type="application/json")
        self.assertEqual(response.status_code, 400)


class PartnerApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = Customer.objects.create(company_name="Acme University", email="ops@acme.example")
        self.plan = Plan.objects.create(
            code="yearly", name="Yearly", billing_interval=Plan.INTERVAL_YEAR,
            price_usd=249, duration_days=366, max_installations=3,
        )
        services.generate_license(self.customer, self.plan, start_date=timezone.now())
        self.raw_secret = self.customer.set_api_secret()
        self.customer.save()

    def test_valid_credentials_return_license_status(self):
        response = self.client.get(
            "/api/v1/partner/status/",
            headers={"X-Sentinel-Account": str(self.customer.external_id), "X-Sentinel-Secret": self.raw_secret},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["license"]["status"], "ACTIVE")
        self.assertEqual(body["license"]["plan"], "yearly")

    def test_invalid_secret_is_rejected(self):
        response = self.client.get(
            "/api/v1/partner/status/",
            headers={"X-Sentinel-Account": str(self.customer.external_id), "X-Sentinel-Secret": "wrong"},
        )
        self.assertEqual(response.status_code, 401)
