from django import forms

from .models import CustomerUser, Organization


class ProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerUser
        fields = ("first_name", "last_name", "email", "phone")


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ("name", "country", "timezone")
