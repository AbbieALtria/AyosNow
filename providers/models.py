import uuid

from django.conf import settings
from django.db import models


class Provider(models.Model):
    class ProviderType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        TEAM = "team", "Team"
        COMPANY = "company", "Company"

    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="provider_profile")
    provider_type = models.CharField(max_length=30, choices=ProviderType.choices)
    display_name = models.CharField(max_length=160)
    city = models.ForeignKey("geo.City", on_delete=models.PROTECT)
    verification_status = models.CharField(
        max_length=30,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    verification_reason = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="provider_verifications",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prov_provider"
        indexes = [models.Index(fields=["verification_status", "city"])]

    def __str__(self):
        return self.display_name

    def transition_verification(self, to_status, *, actor=None, reason=""):
        from_status = self.verification_status
        self.verification_status = to_status
        self.verification_reason = reason
        if to_status == self.VerificationStatus.APPROVED:
            from django.utils import timezone

            self.verified_by = actor if getattr(actor, "is_authenticated", False) else None
            self.verified_at = timezone.now()
        self.save(update_fields=["verification_status", "verification_reason", "verified_by", "verified_at", "updated_at"])
        ProviderVerificationHistory.objects.create(
            provider=self,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            actor_user=actor if getattr(actor, "is_authenticated", False) else None,
        )


class ProviderCoverageCity(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="coverage_cities")
    city = models.ForeignKey("geo.City", on_delete=models.PROTECT, related_name="provider_coverage")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prov_coverage_city"
        constraints = [
            models.UniqueConstraint(fields=["provider", "city"], name="ux_provider_coverage_city"),
        ]


class ProviderBankAccount(models.Model):
    provider = models.OneToOneField(Provider, on_delete=models.CASCADE, related_name="bank_account")
    account_name = models.CharField(max_length=160)
    bank_name = models.CharField(max_length=120)
    account_number_last4 = models.CharField(max_length=4)
    payout_method = models.CharField(max_length=60, default="bank_transfer")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prov_bank_account"


class ProviderVerificationHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="verification_history")
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    reason = models.TextField(blank=True)
    actor_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prov_verification_history"
        ordering = ["created_at"]


class ProviderDocument(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="documents")
    upload = models.ForeignKey("core.UploadedFile", null=True, blank=True, on_delete=models.PROTECT, related_name="provider_documents")
    document_type = models.CharField(max_length=60)
    file_url = models.TextField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.SUBMITTED)
    review_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="provider_document_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prov_document"


class ProviderSkill(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="skills")
    service_item = models.ForeignKey("services.ServiceItem", on_delete=models.CASCADE, related_name="provider_skills")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prov_skill"
        constraints = [
            models.UniqueConstraint(fields=["provider", "service_item"], name="ux_provider_skill"),
        ]
