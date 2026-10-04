from unittest.mock import patch

from django.test import TestCase, override_settings

from accounts.models import CustomerUser, Organization

from .models import InsightsReport
from .seed import seed_demo_orders


def make_customer(name, email):
    org = Organization.objects.create(name=name)
    user = CustomerUser.objects.create_user(username=email, email=email, password="correct-horse-battery12", organization=org)
    return org, user


@override_settings(INSIGHTS_DB_PATH=":memory:does-not-persist")
class SeedAndRunReportTests(TestCase):
    def setUp(self):
        self.org, self.user = make_customer("Acme University", "jordan@acme.example")
        self.client.login(username="jordan@acme.example", password="correct-horse-battery12")

    def test_seed_then_run_report_end_to_end(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name

        with self.settings(INSIGHTS_DB_PATH=db_path):
            count = seed_demo_orders(days=30)
            self.assertGreater(count, 0)

            response = self.client.post("/insights/run/", {"window_days": 30}, follow=True)
            self.assertEqual(response.status_code, 200)

            report = InsightsReport.objects.get(organization=self.org)
            self.assertEqual(report.status, InsightsReport.STATUS_OK)
            self.assertEqual(report.summary["total_orders"], count)
            self.assertContains(response, "Insights")
            self.assertTrue(len(report.insight_text) >= 1)

    def test_report_run_with_no_data_is_marked_no_data(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name

        with self.settings(INSIGHTS_DB_PATH=db_path):
            self.client.post("/insights/run/", {"window_days": 7})
            report = InsightsReport.objects.get(organization=self.org)
            self.assertEqual(report.status, InsightsReport.STATUS_NO_DATA)

    @patch("insights.views.db.get_connection")
    def test_unreachable_database_is_handled_gracefully(self, mock_get_connection):
        mock_get_connection.side_effect = OSError("could not connect to server")
        response = self.client.post("/insights/run/", {"window_days": 30}, follow=True)
        self.assertEqual(response.status_code, 200)
        report = InsightsReport.objects.get(organization=self.org)
        self.assertEqual(report.status, InsightsReport.STATUS_ERROR)
        self.assertIn("could not connect", report.error_message)
        self.assertContains(response, "Could not connect to the database")

    def test_window_days_is_clamped_to_sane_bounds(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            db_path = f.name

        with self.settings(INSIGHTS_DB_PATH=db_path):
            seed_demo_orders(days=10)
            self.client.post("/insights/run/", {"window_days": 99999})
            report = InsightsReport.objects.latest("created_at")
            self.assertLessEqual(report.window_days, 365)


class OrganizationIsolationTests(TestCase):
    def setUp(self):
        self.org_a, self.user_a = make_customer("Org A", "a@example.com")
        self.org_b, self.user_b = make_customer("Org B", "b@example.com")
        self.report_b = InsightsReport.objects.create(
            organization=self.org_b, requested_by=self.user_b, window_days=30,
            status=InsightsReport.STATUS_OK, summary={"total_orders": 5},
        )

    def test_customer_a_cannot_view_customer_bs_report(self):
        self.client.login(username="a@example.com", password="correct-horse-battery12")
        response = self.client.get(f"/insights/{self.report_b.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_report_list_only_shows_own_organization(self):
        InsightsReport.objects.create(organization=self.org_a, requested_by=self.user_a, window_days=30, status=InsightsReport.STATUS_OK)
        self.client.login(username="a@example.com", password="correct-horse-battery12")
        response = self.client.get("/insights/")
        self.assertEqual(response.context["reports"].count(), 1)

    def test_insights_requires_login(self):
        response = self.client.get("/insights/")
        self.assertEqual(response.status_code, 302)
