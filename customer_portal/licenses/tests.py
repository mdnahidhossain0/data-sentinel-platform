from unittest.mock import patch

from django.test import TestCase

from accounts.models import CustomerUser, Organization
from api_client.client import SentinelCloudUnavailable

LICENSE_PAYLOAD = {
    "customer": {"company_name": "Acme University", "status": "ACTIVE"},
    "license": {
        "license_key": "DSK1.secretpayload.secretsignature",
        "status": "ACTIVE",
        "plan": "yearly",
        "plan_name": "Yearly",
        "price_usd": "249.00",
        "billing_interval": "year",
        "issue_date": "2026-09-26T00:00:00+00:00",
        "start_date": "2026-09-26T00:00:00+00:00",
        "expires_at": "2027-09-26T00:00:00+00:00",
        "max_installations": 3,
    },
    "installations": [{"installation_id": "inst-a", "agent_version": "1.0.0", "status": "ONLINE"}],
}


def make_customer(name, email, external_id, secret):
    org = Organization.objects.create(name=name, external_id=external_id, api_secret=secret)
    user = CustomerUser.objects.create_user(username=email, email=email, password="correct-horse-battery12", organization=org)
    return org, user


class CustomerLicenseTests(TestCase):
    def setUp(self):
        self.org, self.user = make_customer(
            "Acme University", "jordan@acme.example", "11111111-1111-1111-1111-111111111111", "secret-a"
        )
        self.client.login(username="jordan@acme.example", password="correct-horse-battery12")

    @patch("licenses.views.get_client_for_organization")
    def test_customer_sees_vendor_created_license(self, mock_get_client):
        mock_get_client.return_value.get_partner_status.return_value = LICENSE_PAYLOAD
        response = self.client.get("/license/")
        self.assertContains(response, "Yearly")
        self.assertContains(response, "249.00")
        self.assertContains(response, "ACTIVE")

    @patch("licenses.views.get_client_for_organization")
    def test_license_key_absent_from_initial_html(self, mock_get_client):
        mock_get_client.return_value.get_partner_status.return_value = LICENSE_PAYLOAD
        response = self.client.get("/license/")
        self.assertNotContains(response, "DSK1.")
        self.assertNotContains(response, "secretpayload")

    @patch("licenses.views.get_client_for_organization")
    def test_reveal_returns_key_for_authenticated_customer(self, mock_get_client):
        mock_get_client.return_value.get_partner_status.return_value = LICENSE_PAYLOAD
        response = self.client.post("/license/reveal/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["license_key"], "DSK1.secretpayload.secretsignature")

    def test_reveal_requires_login(self):
        self.client.logout()
        response = self.client.post("/license/reveal/")
        self.assertEqual(response.status_code, 302)

    @patch("licenses.views.get_client_for_organization")
    def test_no_license_assigned_shows_contact_vendor(self, mock_get_client):
        mock_get_client.return_value.get_partner_status.return_value = {
            "customer": {"company_name": "Acme University", "status": "ACTIVE"}, "license": None, "installations": [],
        }
        response = self.client.get("/license/")
        self.assertContains(response, "No active license has been assigned to your account. Please contact your vendor.")

    @patch("licenses.views.get_client_for_organization")
    def test_vendor_api_unavailable_is_handled_gracefully(self, mock_get_client):
        mock_get_client.return_value.get_partner_status.side_effect = SentinelCloudUnavailable("down")
        response = self.client.get("/license/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Couldn't reach the license server")

        response = self.client.post("/license/reveal/")
        self.assertEqual(response.status_code, 503)


class CrossCustomerIsolationTests(TestCase):
    def test_each_customer_only_queries_the_api_with_their_own_credentials(self):
        _, user_a = make_customer("Org A", "a@example.com", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "secret-a")
        make_customer("Org B", "b@example.com", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "secret-b")
        self.client.login(username="a@example.com", password="correct-horse-battery12")

        with patch("api_client.client.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = LICENSE_PAYLOAD
            self.client.get("/license/")

        headers = mock_get.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Sentinel-Account"], "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        self.assertEqual(headers["X-Sentinel-Secret"], "secret-a")
        self.assertNotIn("secret-b", str(mock_get.call_args))
