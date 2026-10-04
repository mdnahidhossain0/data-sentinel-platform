from django.test import TestCase
from django.utils import timezone

from customers.models import Customer
from licenses import services
from licenses.crypto import InvalidLicenseKey, verify_license_key
from licenses.models import License
from plans.models import Plan


class LicenseLifecycleTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(company_name="Acme University", email="ops@acme.example")
        self.plan = Plan.objects.create(
            code="yearly", name="Yearly", billing_interval=Plan.INTERVAL_YEAR,
            price_usd=249, duration_days=366, max_installations=3,
        )

    def test_generated_license_verifies(self):
        license_obj = services.generate_license(self.customer, self.plan, start_date=timezone.now())
        payload = verify_license_key(license_obj.license_key)
        self.assertEqual(payload["customer"], "Acme University")
        self.assertEqual(payload["plan"], "yearly")
        self.assertEqual(license_obj.effective_status, License.STATUS_ACTIVE)

    def test_tampered_key_is_rejected(self):
        license_obj = services.generate_license(self.customer, self.plan, start_date=timezone.now())
        tampered = license_obj.license_key[:-4] + "abcd"
        with self.assertRaises(InvalidLicenseKey):
            verify_license_key(tampered)

    def test_revoke_sets_status_and_reason(self):
        license_obj = services.generate_license(self.customer, self.plan, start_date=timezone.now())
        services.revoke_license(license_obj, reason=License.REASON_FRAUD)
        license_obj.refresh_from_db()
        self.assertEqual(license_obj.effective_status, License.STATUS_REVOKED)
        self.assertEqual(license_obj.revocation_reason, License.REASON_FRAUD)

    def test_expired_license_reports_expired_status(self):
        license_obj = services.generate_license(
            self.customer, self.plan, start_date=timezone.now(), duration_days=-1
        )
        self.assertEqual(license_obj.effective_status, License.STATUS_EXPIRED)

    def test_extend_pushes_out_expiry_and_reissues_key(self):
        license_obj = services.generate_license(self.customer, self.plan, start_date=timezone.now())
        original_expiry = license_obj.expires_at
        original_key = license_obj.license_key
        services.extend_license(license_obj, additional_days=30)
        license_obj.refresh_from_db()
        self.assertGreater(license_obj.expires_at, original_expiry)
        self.assertNotEqual(license_obj.license_key, original_key)
