from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomerUser, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "external_id", "is_linked", "created_at")
    readonly_fields = ("external_id", "api_secret", "created_at", "updated_at")


@admin.register(CustomerUser)
class CustomerUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Sentinel", {"fields": ("organization", "is_org_owner", "phone")}),)
    list_display = ("username", "email", "organization", "is_org_owner", "is_active")
