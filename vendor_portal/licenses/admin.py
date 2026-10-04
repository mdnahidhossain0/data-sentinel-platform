from django.contrib import admin

from .models import License


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "plan", "status", "start_date", "expires_at")
    list_filter = ("status", "plan")
    search_fields = ("customer__company_name", "license_key")
    readonly_fields = ("license_key", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False
