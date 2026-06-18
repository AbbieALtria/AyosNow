from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import OtpChallenge, User


@admin.register(User)
class AyosNowUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("AyosNow", {"fields": ("user_type", "mobile", "mobile_verified_at")}),
    )
    list_display = ("username", "email", "mobile", "user_type", "is_active", "is_staff")
    list_filter = ("user_type", "is_active", "is_staff")


@admin.register(OtpChallenge)
class OtpChallengeAdmin(admin.ModelAdmin):
    list_display = ("mobile", "purpose", "attempt_count", "expires_at", "verified_at", "created_at")
    search_fields = ("mobile",)
    list_filter = ("purpose", "verified_at")
