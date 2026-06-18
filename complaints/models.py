import uuid

from django.conf import settings
from django.db import models


class Complaint(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        UNDER_REVIEW = "under_review", "Under review"
        AWAITING_CUSTOMER = "awaiting_customer", "Awaiting customer"
        AWAITING_PROVIDER = "awaiting_provider", "Awaiting provider"
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"
        ESCALATED = "escalated", "Escalated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey("bookings.Booking", on_delete=models.PROTECT, related_name="complaints")
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="complaints_opened")
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.OPEN)
    category = models.CharField(max_length=80)
    description = models.TextField()
    resolution = models.TextField(blank=True)
    financial_impact = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="complaints_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "qa_complaint"
        indexes = [models.Index(fields=["status", "-created_at"])]


class ComplaintEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name="evidence")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    upload = models.ForeignKey("core.UploadedFile", null=True, blank=True, on_delete=models.PROTECT, related_name="complaint_evidence")
    file_url = models.TextField()
    file_type = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "qa_complaint_evidence"
