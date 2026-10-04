import secrets

from django import forms
from django.utils import timezone

from plans.models import Plan

from .models import Customer


class CustomerForm(forms.ModelForm):
    """Editing an existing customer's info only - never touches credentials, license, or plan."""

    class Meta:
        model = Customer
        fields = [
            "company_name",
            "contact_person",
            "email",
            "phone",
            "country",
            "organization_type",
            "status",
            "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


def _generate_temp_password():
    return secrets.token_urlsafe(9)


class CustomerCreateForm(forms.Form):
    """The only way a customer account is created: info + login credential + license, all at once."""

    company_name = forms.CharField(max_length=255, label="Company name")
    contact_person = forms.CharField(max_length=255, required=False)
    email = forms.EmailField(label="Customer login email")
    phone = forms.CharField(max_length=50, required=False)
    country = forms.CharField(max_length=100, required=False)
    organization_type = forms.CharField(max_length=100, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    initial_password = forms.CharField(
        label="Temporary password",
        initial=_generate_temp_password,
        help_text="Shown once after creation - relay it to the customer securely. They can change it after logging in.",
    )

    plan = forms.ModelChoiceField(queryset=Plan.objects.filter(is_active=True))
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), initial=timezone.now)
    duration_days = forms.IntegerField(required=False, help_text="Leave blank to use the plan's default duration.")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if Customer.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A customer with this email already exists.")
        return email
