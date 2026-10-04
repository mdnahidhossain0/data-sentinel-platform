from django import forms

from .models import Plan


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = [
            "code",
            "name",
            "billing_interval",
            "price_usd",
            "currency",
            "duration_days",
            "max_installations",
            "is_active",
        ]
