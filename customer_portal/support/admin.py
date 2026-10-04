from django.contrib import admin

from .models import SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("subject", "organization", "priority", "status", "created_at")
    list_filter = ("status", "priority")
