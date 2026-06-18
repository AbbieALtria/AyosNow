from django.contrib import admin

from .models import UploadedFile


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "purpose", "owner_user", "content_type", "size_bytes", "status", "created_at")
    list_filter = ("purpose", "status", "content_type", "created_at")
    search_fields = ("original_filename", "storage_key", "owner_user__username", "attached_entity_id")
    readonly_fields = [field.name for field in UploadedFile._meta.fields]
