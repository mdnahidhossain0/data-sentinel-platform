from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("company_name", "email", "status", "country", "created_at")
    list_filter = ("status", "country")
    search_fields = ("company_name", "email", "contact_person")
    readonly_fields = ("external_id", "api_secret_hash", "created_at", "updated_at")
