from django.db import migrations, models


def promote_owners(apps, schema_editor):
    CustomerUser = apps.get_model("accounts", "CustomerUser")
    CustomerUser.objects.filter(is_org_owner=True).update(role="ORG_ADMIN")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_remove_customeruser_email_verified_and_more")]
    operations = [
        migrations.AddField(
            model_name="customeruser",
            name="role",
            field=models.CharField(
                choices=[
                    ("ORG_ADMIN", "Organization Admin"),
                    ("RISK_ANALYST", "Risk Analyst"),
                    ("REVIEWER", "Reviewer"),
                    ("VIEWER", "Viewer"),
                ],
                default="VIEWER",
                max_length=20,
            ),
        ),
        migrations.RunPython(promote_owners, migrations.RunPython.noop),
    ]
