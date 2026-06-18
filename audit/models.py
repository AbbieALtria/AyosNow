import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=80)
    entity_id = models.UUIDField(null=True, blank=True)
    before_data = models.JSONField(null=True, blank=True)
    after_data = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "aud_audit_log"
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "-created_at"]),
            models.Index(fields=["actor_user", "-created_at"]),
        ]


class Notification(models.Model):
    class AudienceRole(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        PROVIDER = "provider", "Provider"
        OPS = "ops", "Operations"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    audience_role = models.CharField(max_length=30, choices=AudienceRole.choices, blank=True)
    title = models.CharField(max_length=160)
    message = models.TextField()
    entity_type = models.CharField(max_length=80, blank=True)
    entity_id = models.UUIDField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "aud_notification"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient_user", "is_read", "-created_at"]),
            models.Index(fields=["audience_role", "is_read", "-created_at"]),
            models.Index(fields=["entity_type", "entity_id", "-created_at"]),
        ]

    def mark_read(self):
        if self.is_read:
            return
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])


def write_audit(*, actor=None, action, entity_type, entity_id=None, before=None, after=None, request=None):
    ip_address = None
    user_agent = ""
    if request is not None:
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
    return AuditLog.objects.create(
        actor_user=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=before,
        after_data=after,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def notify_user(*, user, title, message, entity_type="", entity_id=None):
    if not user:
        return None
    return Notification.objects.create(
        recipient_user=user,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def notify_role(*, audience_role, title, message, entity_type="", entity_id=None):
    return Notification.objects.create(
        audience_role=audience_role,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def notify_ops(*, title, message, entity_type="", entity_id=None):
    return notify_role(
        audience_role=Notification.AudienceRole.OPS,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
    )
