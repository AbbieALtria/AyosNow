from django.contrib import admin

from .models import Provider, ProviderBankAccount, ProviderCoverageCity, ProviderDocument, ProviderSkill, ProviderVerificationHistory


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("display_name", "provider_type", "city", "verification_status", "created_at")
    list_filter = ("provider_type", "verification_status", "city")
    search_fields = ("display_name", "user__mobile", "user__email")


@admin.register(ProviderDocument)
class ProviderDocumentAdmin(admin.ModelAdmin):
    list_display = ("provider", "document_type", "status", "reviewed_by", "created_at")
    list_filter = ("document_type", "status")
    search_fields = ("provider__display_name", "document_type")


@admin.register(ProviderSkill)
class ProviderSkillAdmin(admin.ModelAdmin):
    list_display = ("provider", "service_item", "created_at")
    search_fields = ("provider__display_name", "service_item__name")


@admin.register(ProviderCoverageCity)
class ProviderCoverageCityAdmin(admin.ModelAdmin):
    list_display = ("provider", "city", "created_at")
    search_fields = ("provider__display_name", "city__name")


@admin.register(ProviderBankAccount)
class ProviderBankAccountAdmin(admin.ModelAdmin):
    list_display = ("provider", "bank_name", "account_number_last4", "payout_method", "updated_at")
    search_fields = ("provider__display_name", "bank_name", "account_number_last4")


@admin.register(ProviderVerificationHistory)
class ProviderVerificationHistoryAdmin(admin.ModelAdmin):
    list_display = ("provider", "from_status", "to_status", "actor_user", "created_at")
    list_filter = ("to_status", "created_at")
    search_fields = ("provider__display_name", "reason", "actor_user__username")
    readonly_fields = [field.name for field in ProviderVerificationHistory._meta.fields]
