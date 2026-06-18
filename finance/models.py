import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        CAPTURED = "captured", "Captured"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey("bookings.Booking", on_delete=models.PROTECT, related_name="payments")
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="PHP")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    gateway = models.CharField(max_length=60)
    gateway_reference = models.CharField(max_length=160, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)
    checkout_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fin_payment"
        indexes = [models.Index(fields=["booking", "status"])]


class GatewayEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, null=True, blank=True, on_delete=models.PROTECT, related_name="gateway_events")
    gateway = models.CharField(max_length=60)
    event_id = models.CharField(max_length=160)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fin_gateway_event"
        constraints = [models.UniqueConstraint(fields=["gateway", "event_id"], name="ux_gateway_event")]


class WalletLedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        PAYMENT_CAPTURED = "payment_captured", "Payment captured"
        PROVIDER_EARNING = "provider_earning", "Provider earning"
        COMMISSION = "commission", "Commission"
        REFUND = "refund", "Refund"
        ADJUSTMENT = "adjustment", "Adjustment"
        PAYOUT_REQUESTED = "payout_requested", "Payout requested"
        PAYOUT_RELEASED = "payout_released", "Payout released"
        PAYOUT_FAILED = "payout_failed", "Payout failed"
        HOLD = "hold", "Hold"
        HOLD_RELEASED = "hold_released", "Hold released"

    class Direction(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey("providers.Provider", on_delete=models.PROTECT, related_name="wallet_entries")
    source_type = models.CharField(max_length=60)
    source_id = models.UUIDField()
    entry_type = models.CharField(max_length=60, choices=EntryType.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="PHP")
    is_available = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fin_wallet_ledger"
        indexes = [
            models.Index(fields=["provider", "-created_at"]),
            models.Index(fields=["source_type", "source_id", "entry_type"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="ck_wallet_ledger_positive_amount"),
            models.UniqueConstraint(fields=["provider", "source_type", "source_id", "entry_type"], name="ux_wallet_ledger_source_entry"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and WalletLedgerEntry.objects.filter(pk=self.pk).exists():
            raise ValidationError("Wallet ledger entries are immutable.")
        super().save(*args, **kwargs)


class Payout(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RELEASED = "released", "Released"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey("providers.Provider", on_delete=models.PROTECT, related_name="payouts")
    idempotency_key = models.CharField(max_length=160, unique=True)
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="PHP")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.REQUESTED)
    provider_notes = models.TextField(blank=True)
    finance_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    payout_reference = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fin_payout"
        indexes = [models.Index(fields=["provider", "status"])]
        constraints = [models.CheckConstraint(check=models.Q(requested_amount__gt=0), name="ck_payout_positive_amount")]
