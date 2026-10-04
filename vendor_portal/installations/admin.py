from django.contrib import admin

from .models import Installation


@admin.register(Installation)
class InstallationAdmin(admin.ModelAdmin):
    list_display = ("installation_id", "customer", "agent_version", "last_check_in")
    search_fields = ("installation_id", "customer__company_name")
    readonly_fields = ("installation_id", "first_seen")
