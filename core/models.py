import uuid

from django.conf import settings
from django.db import models


class UploadedFile(models.Model):
    class Purpose(models.TextChoices):
        PROVIDER_DOCUMENT = "provider_document", "Provider document"
        COMPLAINT_EVIDENCE = "complaint_evidence", "Complaint evidence"
        COMPLETION_EVIDENCE = "completion_evidence", "Completion evidence"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending upload"
        UPLOADED = "uploaded", "Uploaded"
        ATTACHED = "attached", "Attached"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_files")
    purpose = models.CharField(max_length=60, choices=Purpose.choices)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    size_bytes = models.PositiveIntegerField()
    storage_key = models.CharField(max_length=255, unique=True)
    public_url = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    attached_entity_type = models.CharField(max_length=80, blank=True)
    attached_entity_id = models.UUIDField(null=True, blank=True)
    upload_expires_at = models.DateTimeField()
    uploaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_uploaded_file"
        indexes = [
            models.Index(fields=["owner_user", "purpose", "-created_at"]),
            models.Index(fields=["attached_entity_type", "attached_entity_id"]),
        ]

    def __str__(self):
        return f"{self.purpose}:{self.original_filename}"
