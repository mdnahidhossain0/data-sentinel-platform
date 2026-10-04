from django import forms
from django.utils import timezone

from customers.models import Customer
from plans.models import Plan

from .models import License


class GenerateLicenseForm(forms.Form):
    customer = forms.ModelChoiceField(queryset=Customer.objects.filter(status=Customer.STATUS_ACTIVE))
    plan = forms.ModelChoiceField(queryset=Plan.objects.filter(is_active=True))
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), initial=timezone.now)
    duration_days = forms.IntegerField(required=False, help_text="Leave blank to use the plan's default duration.")
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class RevokeLicenseForm(forms.Form):
    reason = forms.ChoiceField(choices=License.REVOCATION_REASON_CHOICES)
    details = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ExtendLicenseForm(forms.Form):
    additional_days = forms.IntegerField(min_value=1, initial=30)


class ChangePlanForm(forms.Form):
    plan = forms.ModelChoiceField(queryset=Plan.objects.filter(is_active=True))
