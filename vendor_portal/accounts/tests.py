from django.test import Client, TestCase

from accounts.models import StaffUser
from audit.models import AuditEvent


class StaffAuthenticationTests(TestCase):
    def setUp(self):
        self.user = StaffUser.objects.create_user(username="ops", password="staff-pass-12345", role=StaffUser.ROLE_VIEWER)

    def test_login_logout_and_failed_login_are_audited(self):
        client = Client()
        client.post("/accounts/login/", {"username": "ops", "password": "wrong"})
        self.assertTrue(AuditEvent.objects.filter(action="login_failed").exists())

        client.post("/accounts/login/", {"username": "ops", "password": "staff-pass-12345"})
        self.assertTrue(AuditEvent.objects.filter(action="login", actor=self.user).exists())

        client.post("/accounts/logout/")
        self.assertTrue(AuditEvent.objects.filter(action="logout", actor=self.user).exists())

    def test_password_change_works(self):
        client = Client()
        client.force_login(self.user)
        response = client.post("/accounts/password-change/", {
            "old_password": "staff-pass-12345", "new_password1": "Another-new-pass-77x", "new_password2": "Another-new-pass-77x",
        })
        self.assertRedirects(response, "/accounts/password-change/done/")

    def test_only_super_admin_can_manage_staff(self):
        client = Client()
        client.force_login(self.user)
        response = client.get("/accounts/admin-users/")
        self.assertEqual(response.status_code, 302)
        admin = StaffUser.objects.create_user(username="root", password="staff-pass-12345", role=StaffUser.ROLE_SUPER_ADMIN)
        client.force_login(admin)
        self.assertEqual(client.get("/accounts/admin-users/").status_code, 200)
