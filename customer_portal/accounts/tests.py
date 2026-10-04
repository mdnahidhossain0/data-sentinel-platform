import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from support.models import SupportTicket

from .models import CustomerUser, Organization


class AuthenticationTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Acme University")
        self.user = CustomerUser.objects.create_user(
            username="jordan@acme.example", email="jordan@acme.example",
            password="correct-horse-battery12", organization=self.org, is_org_owner=True,
        )

    def test_login_succeeds_with_correct_credentials(self):
        ok = self.client.login(username="jordan@acme.example", password="correct-horse-battery12")
        self.assertTrue(ok)

    def test_login_fails_with_wrong_password(self):
        ok = self.client.login(username="jordan@acme.example", password="wrong-password")
        self.assertFalse(ok)

    def test_dashboard_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.headers["Location"])

    def test_support_tickets_require_login(self):
        response = self.client.get("/support/")
        self.assertEqual(response.status_code, 302)

    def test_signup_endpoint_no_longer_exists(self):
        response = self.client.get("/accounts/signup/")
        self.assertEqual(response.status_code, 404)

    def test_link_account_endpoint_no_longer_exists(self):
        response = self.client.get("/accounts/link-account/")
        self.assertEqual(response.status_code, 404)

    def test_suspended_customer_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        ok = self.client.login(username="jordan@acme.example", password="correct-horse-battery12")
        self.assertFalse(ok)

    def test_suspending_mid_session_logs_the_customer_out(self):
        self.client.login(username="jordan@acme.example", password="correct-horse-battery12")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        self.user.is_active = False
        self.user.save()

        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.headers["Location"])

        response = self.client.get("/", follow=True)
        self.assertContains(response, "suspended")

        response = self.client.get("/license/")
        self.assertEqual(response.status_code, 302)


class OrganizationIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="Org A")
        self.org_b = Organization.objects.create(name="Org B")
        self.user_a = CustomerUser.objects.create_user(username="a@example.com", password="pw-a-1234567", organization=self.org_a)
        self.user_b = CustomerUser.objects.create_user(username="b@example.com", password="pw-b-1234567", organization=self.org_b)
        self.ticket_b = SupportTicket.objects.create(
            organization=self.org_b, created_by=self.user_b, subject="Org B's private issue", message="secret"
        )

    def test_user_cannot_see_another_orgs_ticket(self):
        self.client.login(username="a@example.com", password="pw-a-1234567")
        response = self.client.get(f"/support/{self.ticket_b.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_ticket_list_only_shows_own_organization(self):
        SupportTicket.objects.create(organization=self.org_a, created_by=self.user_a, subject="Org A issue", message="hi")
        self.client.login(username="a@example.com", password="pw-a-1234567")
        response = self.client.get("/support/")
        self.assertContains(response, "Org A issue")
        self.assertNotContains(response, "Org B's private issue")


class InstallationVisibilityTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Acme University", external_id="11111111-1111-1111-1111-111111111111"
        )
        self.org.api_secret = "s3cr3t"
        self.org.save()
        self.user = CustomerUser.objects.create_user(username="jordan@acme.example", password="correct-horse-battery12", organization=self.org)
        self.client.login(username="jordan@acme.example", password="correct-horse-battery12")

    @patch("installations.views.get_client_for_organization")
    def test_installations_render_from_partner_api(self, mock_get_client):
        mock_client = mock_get_client.return_value
        mock_client.get_partner_status.return_value = {
            "installations": [{"installation_id": "abc-1", "agent_version": "1.0.0", "status": "ONLINE"}]
        }
        response = self.client.get("/installations/")
        self.assertContains(response, "abc-1")
        self.assertContains(response, "Online")

    def test_incompletely_provisioned_organization_shows_contact_vendor(self):
        self.org.external_id = None
        self.org.api_secret = ""
        self.org.save()
        response = self.client.get("/installations/")
        self.assertContains(response, "contact your vendor")


@override_settings(VENDOR_PROVISIONING_KEY="test-shared-key")
class ProvisioningEndpointTests(TestCase):
    def _post(self, payload, key="test-shared-key"):
        return self.client.post(
            "/internal/provision/",
            data=json.dumps(payload),
            content_type="application/json",
            headers={"X-Vendor-Provisioning-Key": key},
        )

    def test_wrong_key_is_rejected(self):
        response = self._post({"external_id": "22222222-2222-2222-2222-222222222222"}, key="wrong")
        self.assertEqual(response.status_code, 401)

    def test_creating_new_account_requires_email_and_password(self):
        response = self._post({"external_id": "22222222-2222-2222-2222-222222222222"})
        self.assertEqual(response.status_code, 400)

    def test_valid_request_creates_organization_and_login(self):
        response = self._post({
            "external_id": "33333333-3333-3333-3333-333333333333",
            "api_secret": "s3cr3t",
            "email": "new-customer@example.com",
            "password": "temp-pass-123456",
            "organization_name": "New University",
            "status": "ACTIVE",
        })
        self.assertEqual(response.status_code, 200)

        org = Organization.objects.get(external_id="33333333-3333-3333-3333-333333333333")
        self.assertEqual(org.name, "New University")
        self.assertEqual(org.api_secret, "s3cr3t")

        user = CustomerUser.objects.get(organization=org)
        self.assertTrue(user.is_active)
        self.assertTrue(self.client.login(username="new-customer@example.com", password="temp-pass-123456"))

    def test_status_only_update_does_not_require_credentials(self):
        self._post({
            "external_id": "44444444-4444-4444-4444-444444444444",
            "api_secret": "s3cr3t",
            "email": "another@example.com",
            "password": "temp-pass-123456",
            "organization_name": "Another Org",
            "status": "ACTIVE",
        })
        response = self._post({
            "external_id": "44444444-4444-4444-4444-444444444444",
            "organization_name": "Another Org",
            "status": "SUSPENDED",
        })
        self.assertEqual(response.status_code, 200)
        user = CustomerUser.objects.get(username="another@example.com")
        self.assertFalse(user.is_active)


class PasswordResetTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Acme University")
        self.user = CustomerUser.objects.create_user(
            username="jordan@acme.example", email="jordan@acme.example",
            password="correct-horse-battery12", organization=self.org,
        )

    def test_reset_sends_email_for_existing_customer(self):
        from django.core import mail

        response = self.client.post("/accounts/password-reset/", {"email": "jordan@acme.example"})
        self.assertRedirects(response, "/accounts/password-reset/done/")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)

    def test_reset_never_creates_a_customer(self):
        from django.core import mail

        before = (CustomerUser.objects.count(), Organization.objects.count())
        response = self.client.post("/accounts/password-reset/", {"email": "stranger@example.com"})
        self.assertRedirects(response, "/accounts/password-reset/done/")
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(before, (CustomerUser.objects.count(), Organization.objects.count()))

    def test_full_reset_flow_changes_password(self):
        from django.core import mail

        self.client.post("/accounts/password-reset/", {"email": "jordan@acme.example"})
        link = [line for line in mail.outbox[0].body.splitlines() if "/accounts/reset/" in line][0].strip()
        path = "/" + link.split("/", 3)[3]
        response = self.client.get(path, follow=True)
        response = self.client.post(response.request["PATH_INFO"], {"new_password1": "Brand-new-pass-991", "new_password2": "Brand-new-pass-991"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.login(username="jordan@acme.example", password="Brand-new-pass-991"))

    def test_password_change_works_when_logged_in(self):
        self.client.login(username="jordan@acme.example", password="correct-horse-battery12")
        response = self.client.post("/accounts/password-change/", {
            "old_password": "correct-horse-battery12", "new_password1": "Another-new-pass-77", "new_password2": "Another-new-pass-77",
        })
        self.assertRedirects(response, "/accounts/password-change/done/")
