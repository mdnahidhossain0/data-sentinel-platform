import json
from unittest.mock import Mock, patch

import requests
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import StaffUser
from audit.models import AuditEvent
from customers.models import Customer
from licenses import services as license_services
from licenses.models import License
from plans.models import Plan


def make_staff(role, username=None):
    return StaffUser.objects.create_user(username=username or role.lower(), password="staff-pass-12345", role=role)


def ok_response():
    response = Mock(status_code=200)
    response.json.return_value = {"status": "ok"}
    return response


CREATE_FORM = {
    "company_name": "Demo Customer",
    "email": "demo@customer.example",
    "initial_password": "Temp-Pass-123456",
    "start_date": "2026-09-26",
    "contact_person": "Dana",
}


@override_settings(CUSTOMER_PORTAL_URL="http://portal.test", VENDOR_PROVISIONING_KEY="shared-key")
class CustomerProvisioningTests(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(
            code="yearly", name="Yearly", billing_interval=Plan.INTERVAL_YEAR,
            price_usd=249, duration_days=366, max_installations=3,
        )
        self.manager = make_staff(StaffUser.ROLE_LICENSE_MANAGER)
        self.client = Client()
        self.client.force_login(self.manager)

    def _create(self, **overrides):
        data = {**CREATE_FORM, "plan": self.plan.pk, **overrides}
        return self.client.post("/customers/new/", data)

    @patch("customers.provisioning.requests.post")
    def test_vendor_creates_customer_license_and_provisions_portal_login(self, mock_post):
        mock_post.return_value = ok_response()
        response = self._create()

        self.assertEqual(response.status_code, 200)
        customer = Customer.objects.get(email="demo@customer.example")
        license_obj = License.objects.get(customer=customer)
        self.assertEqual(license_obj.plan, self.plan)
        self.assertEqual(license_obj.effective_status, License.STATUS_ACTIVE)

        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["X-Vendor-Provisioning-Key"], "shared-key")
        payload = kwargs["json"]
        self.assertEqual(payload["external_id"], str(customer.external_id))
        self.assertEqual(payload["email"], "demo@customer.example")
        self.assertEqual(payload["password"], "Temp-Pass-123456")
        self.assertEqual(payload["status"], "ACTIVE")
        self.assertTrue(customer.check_api_secret(payload["api_secret"]))

        self.assertTrue(AuditEvent.objects.filter(action="customer_created").exists())
        self.assertTrue(AuditEvent.objects.filter(action="customer_portal_provisioned").exists())

    @patch("customers.provisioning.requests.post")
    def test_signing_key_and_license_key_never_sent_to_customer_portal(self, mock_post):
        mock_post.return_value = ok_response()
        self._create()
        sent = json.dumps(mock_post.call_args.kwargs["json"])
        license_obj = License.objects.get()
        self.assertNotIn(license_obj.license_key, sent)
        self.assertNotIn("PRIVATE", sent.upper())

    @patch("customers.provisioning.requests.post")
    def test_api_secret_and_password_are_not_stored_in_plaintext(self, mock_post):
        mock_post.return_value = ok_response()
        self._create()
        customer = Customer.objects.get()
        secret = mock_post.call_args.kwargs["json"]["api_secret"]
        self.assertNotEqual(customer.api_secret_hash, secret)
        self.assertNotIn(secret, customer.api_secret_hash)
        stored = json.dumps([getattr(customer, f.name) for f in Customer._meta.fields], default=str)
        self.assertNotIn("Temp-Pass-123456", stored)

    @patch("customers.provisioning.requests.post")
    def test_customer_still_created_if_portal_unreachable(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("refused")
        response = self._create()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "could not be provisioned")
        self.assertTrue(Customer.objects.filter(email="demo@customer.example").exists())
        self.assertTrue(AuditEvent.objects.filter(action="customer_portal_provision_failed").exists())

    @patch("customers.provisioning.requests.post")
    def test_duplicate_email_is_rejected(self, mock_post):
        mock_post.return_value = ok_response()
        self._create()
        response = self._create(company_name="Someone Else")
        self.assertEqual(Customer.objects.count(), 1)
        self.assertContains(response, "already exists")

    @patch("customers.provisioning.requests.post")
    def test_suspend_and_reactivate_push_account_status(self, mock_post):
        mock_post.return_value = ok_response()
        self._create()
        customer = Customer.objects.get()

        self.client.post(f"/customers/{customer.pk}/suspend/")
        customer.refresh_from_db()
        self.assertEqual(customer.status, Customer.STATUS_SUSPENDED)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["status"], "SUSPENDED")
        self.assertNotIn("password", payload)
        self.assertNotIn("api_secret", payload)

        self.client.post(f"/customers/{customer.pk}/reactivate/")
        self.assertEqual(mock_post.call_args.kwargs["json"]["status"], "ACTIVE")

        self.client.post(f"/customers/{customer.pk}/archive/")
        self.assertEqual(mock_post.call_args.kwargs["json"]["status"], "ARCHIVED")

    @patch("customers.provisioning.requests.post")
    def test_account_status_is_independent_of_license_status(self, mock_post):
        mock_post.return_value = ok_response()
        self._create()
        customer = Customer.objects.get()
        license_obj = License.objects.get()

        license_services.revoke_license(license_obj, reason=License.REASON_FRAUD)
        customer.refresh_from_db()
        self.assertEqual(customer.status, Customer.STATUS_ACTIVE)

        self.client.post(f"/customers/{customer.pk}/suspend/")
        license_obj.refresh_from_db()
        self.assertEqual(license_obj.status, License.STATUS_REVOKED)

    @patch("customers.provisioning.requests.post")
    def test_reset_portal_password_pushes_new_password_and_secret(self, mock_post):
        mock_post.return_value = ok_response()
        self._create()
        customer = Customer.objects.get()
        old_hash = customer.api_secret_hash

        response = self.client.post(f"/customers/{customer.pk}/reset-portal-password/")
        customer.refresh_from_db()
        self.assertNotEqual(customer.api_secret_hash, old_hash)
        payload = mock_post.call_args.kwargs["json"]
        self.assertTrue(customer.check_api_secret(payload["api_secret"]))
        self.assertContains(response, payload["password"])


@override_settings(CUSTOMER_PORTAL_URL="http://portal.test", VENDOR_PROVISIONING_KEY="shared-key")
class ProvisioningPermissionTests(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(
            code="yearly", name="Yearly", billing_interval=Plan.INTERVAL_YEAR,
            price_usd=249, duration_days=366, max_installations=3,
        )
        self.customer = Customer.objects.create(company_name="Existing", email="existing@example.com")
        self.license = license_services.generate_license(self.customer, self.plan, start_date=timezone.now())

    @patch("customers.provisioning.requests.post")
    def test_read_only_roles_cannot_create_customers(self, mock_post):
        for role in (StaffUser.ROLE_VIEWER, StaffUser.ROLE_SUPPORT_AGENT):
            client = Client()
            client.force_login(make_staff(role))
            response = client.post("/customers/new/", {**CREATE_FORM, "plan": self.plan.pk})
            self.assertEqual(response.status_code, 302, role)
        self.assertEqual(Customer.objects.count(), 1)
        mock_post.assert_not_called()
        self.assertTrue(AuditEvent.objects.filter(action="permission_denied").exists())

    @patch("customers.provisioning.requests.post")
    def test_read_only_roles_cannot_modify_customers_or_licenses(self, mock_post):
        for role in (StaffUser.ROLE_VIEWER, StaffUser.ROLE_SUPPORT_AGENT):
            client = Client()
            client.force_login(make_staff(role))
            client.post(f"/customers/{self.customer.pk}/suspend/")
            client.post(f"/customers/{self.customer.pk}/reset-portal-password/")
            client.post(f"/licenses/{self.license.pk}/revoke/", {"reason": "FRAUD"})
            client.post("/licenses/generate/", {"customer": self.customer.pk, "plan": self.plan.pk, "start_date": "2026-09-26"})
        self.customer.refresh_from_db()
        self.license.refresh_from_db()
        self.assertEqual(self.customer.status, Customer.STATUS_ACTIVE)
        self.assertEqual(self.license.status, License.STATUS_ACTIVE)
        self.assertEqual(License.objects.count(), 1)
        mock_post.assert_not_called()

    def test_anonymous_cannot_reach_customer_creation(self):
        response = Client().post("/customers/new/", {**CREATE_FORM, "plan": self.plan.pk})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.headers["Location"])
        self.assertEqual(Customer.objects.count(), 1)


class PartnerApiIsolationTests(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(
            code="yearly", name="Yearly", billing_interval=Plan.INTERVAL_YEAR,
            price_usd=249, duration_days=366, max_installations=3,
        )
        self.a = Customer.objects.create(company_name="Customer A", email="a@example.com")
        self.b = Customer.objects.create(company_name="Customer B", email="b@example.com")
        self.secret_a = self.a.set_api_secret()
        self.secret_b = self.b.set_api_secret()
        self.a.save()
        self.b.save()
        self.license_a = license_services.generate_license(self.a, self.plan, start_date=timezone.now())
        self.license_b = license_services.generate_license(self.b, self.plan, start_date=timezone.now())

    def _status(self, customer, secret):
        return Client().get(
            "/api/v1/partner/status/",
            headers={"X-Sentinel-Account": str(customer.external_id), "X-Sentinel-Secret": secret},
        )

    def test_identity_maps_to_the_correct_vendor_customer(self):
        body = self._status(self.a, self.secret_a).json()
        self.assertEqual(body["customer"]["company_name"], "Customer A")
        self.assertEqual(body["license"]["license_key"], self.license_a.license_key)

    def test_customer_a_never_receives_customer_b_data(self):
        body = json.dumps(self._status(self.a, self.secret_a).json())
        self.assertNotIn("Customer B", body)
        self.assertNotIn(self.license_b.license_key, body)

    def test_customer_a_id_with_customer_b_secret_is_rejected(self):
        self.assertEqual(self._status(self.a, self.secret_b).status_code, 401)
        self.assertEqual(self._status(self.b, self.secret_a).status_code, 401)

    def test_installations_are_scoped_to_the_authenticated_customer(self):
        from installations.models import Installation

        Installation.objects.create(customer=self.a, license=self.license_a, agent_version="1.0", last_check_in=timezone.now())
        Installation.objects.create(customer=self.b, license=self.license_b, agent_version="9.9", last_check_in=timezone.now())
        body = self._status(self.a, self.secret_a).json()
        self.assertEqual(len(body["installations"]), 1)
        self.assertEqual(body["installations"][0]["agent_version"], "1.0")

    def test_license_status_changes_are_reflected_live(self):
        license_services.revoke_license(self.license_a, reason=License.REASON_FRAUD)
        self.assertEqual(self._status(self.a, self.secret_a).json()["license"]["status"], "REVOKED")
        self.assertEqual(self._status(self.b, self.secret_b).json()["license"]["status"], "ACTIVE")
