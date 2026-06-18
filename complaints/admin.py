from django.contrib import admin

from .models import Complaint, ComplaintEvidence


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "status", "category", "opened_by", "created_at")
    list_filter = ("status", "category", "created_at")
    search_fields = ("id", "booking__id", "description")


@admin.register(ComplaintEvidence)
class ComplaintEvidenceAdmin(admin.ModelAdmin):
    list_display = ("complaint", "uploaded_by", "file_type", "created_at")
    search_fields = ("complaint__id", "file_url")
