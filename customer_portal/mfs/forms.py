from django import forms

from .models import DataSource, ReviewDecision


class DataSourceForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "••••••••",
            "class": "w-full rounded-xl border border-slate-700 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 shadow-sm transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30",
        }),
        required=False,
        help_text="Stored encrypted; leave blank to retain existing credential.",
    )

    class Meta:
        model = DataSource
        fields = ("name", "engine", "host", "port", "database_name", "username", "password", "ssl_required")
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 shadow-sm transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30",
                "placeholder": "Payments primary replica",
            }),
            "engine": forms.Select(attrs={
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 shadow-sm transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30",
            }),
            "host": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 shadow-sm transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30",
                "placeholder": "db.internal.example.com",
            }),
            "port": forms.NumberInput(attrs={
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 shadow-sm transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30",
                "min": "1",
                "max": "65535",
            }),
            "database_name": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 shadow-sm transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30",
                "placeholder": "core_mfs",
            }),
            "username": forms.TextInput(attrs={
                "class": "w-full rounded-xl border border-slate-700 bg-slate-950/80 px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 shadow-sm transition focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30",
                "placeholder": "readonly_user",
            }),
            "ssl_required": forms.CheckboxInput(attrs={
                "class": "h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-600 focus:ring-brand-500",
            }),
        }


class ReviewDecisionForm(forms.ModelForm):
    class Meta:
        model = ReviewDecision
        fields = ("decision", "reason", "comments")


class AssistantForm(forms.Form):
    question = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={
            "rows": 3,
            "class": (
                "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 "
                "text-sm text-slate-100 placeholder-slate-500 shadow-sm "
                "focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
            ),
            "placeholder": "Ask about recent high-risk transactions, merchants, or a transaction ID.",
        }),
    )
