from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "actor", "action", "target_type", "target_id", "ip_address")
    list_filter = ("action", "target_type")
    search_fields = ("action", "target_type", "target_id", "actor__username")
    readonly_fields = [f.name for f in AuditEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
