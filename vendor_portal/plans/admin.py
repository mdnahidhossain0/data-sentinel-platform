from django.contrib import admin

from .models import Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "billing_interval", "price_usd", "is_active")
    list_filter = ("is_active", "billing_interval")
