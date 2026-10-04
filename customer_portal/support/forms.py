from django import forms

from .models import SupportTicket


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ["subject", "message", "priority"]
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}
