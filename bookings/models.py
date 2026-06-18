import uuid

from django.conf import settings
from django.db import models


class Booking(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        PENDING_DISPATCH = "pending_dispatch", "Pending dispatch"
        ASSIGNED = "assigned", "Assigned"
        PROVIDER_ACCEPTED = "provider_accepted", "Provider accepted"
        PROVIDER_DECLINED = "provider_declined", "Provider declined"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED_BY_PROVIDER = "completed_by_provider", "Completed by provider"
        CONFIRMED_COMPLETED = "confirmed_completed", "Confirmed completed"
        CANCELLED = "cancelled", "Cancelled"
        DISPUTED = "disputed", "Disputed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="bookings")
    service_item = models.ForeignKey("services.ServiceItem", on_delete=models.PROTECT, related_name="bookings")
    customer_address = models.ForeignKey("customers.CustomerAddress", on_delete=models.PROTECT)
    service_snapshot = models.JSONField()
    address_snapshot = models.JSONField()
    requested_schedule = models.DateTimeField()
    description = models.TextField()
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.PENDING_DISPATCH)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "book_booking"
        indexes = [
            models.Index(fields=["status", "requested_schedule"]),
            models.Index(fields=["customer", "-created_at"]),
        ]

    def transition_to(self, to_status, *, actor=None, reason=""):
        from_status = self.status
        self.status = to_status
        if to_status == self.Status.CANCELLED:
            self.cancellation_reason = reason
        self.save(update_fields=["status", "cancellation_reason", "updated_at"])
        BookingStatusHistory.objects.create(
            booking=self,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            actor_user=actor if getattr(actor, "is_authenticated", False) else None,
        )


class BookingStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=40, blank=True)
    to_status = models.CharField(max_length=40)
    reason = models.TextField(blank=True)
    actor_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "book_status_history"
        ordering = ["created_at"]


class Assignment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="assignments")
    provider = models.ForeignKey("providers.Provider", on_delete=models.PROTECT, related_name="assignments")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ASSIGNED)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assignments_made")
    assignment_reason = models.TextField(blank=True)
    provider_response_reason = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)
    completion_evidence_urls = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "book_assignment"
        indexes = [models.Index(fields=["provider", "status"])]
