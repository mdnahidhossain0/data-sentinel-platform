from django import forms

from .models import DataSource, ReviewDecision


class DataSourceForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False, help_text="Stored encrypted; leave blank to retain existing credential.")

    class Meta:
        model = DataSource
        fields = ("name", "engine", "host", "port", "database_name", "username", "password", "ssl_required")


class ReviewDecisionForm(forms.ModelForm):
    class Meta:
        model = ReviewDecision
        fields = ("decision", "reason", "comments")


class AssistantForm(forms.Form):
    question = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))
