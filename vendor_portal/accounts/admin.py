from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import StaffUser


@admin.register(StaffUser)
class StaffUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Sentinel", {"fields": ("role", "two_factor_enabled")}),)
    list_display = ("username", "email", "role", "is_active", "is_superuser")
    list_filter = ("role", "is_active")
