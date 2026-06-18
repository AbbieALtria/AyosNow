from django.contrib import admin

from .models import AuditLog, Notification


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor_user", "action", "entity_type", "entity_id")
    list_filter = ("action", "entity_type")
    search_fields = ("entity_id", "action", "actor_user__username")
    readonly_fields = [field.name for field in AuditLog._meta.fields]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "recipient_user", "audience_role", "title", "entity_type", "is_read")
    list_filter = ("audience_role", "entity_type", "is_read", "created_at")
    search_fields = ("title", "message", "recipient_user__username", "entity_id")
