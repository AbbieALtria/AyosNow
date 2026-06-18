from django.contrib import admin

from .models import GatewayEvent, Payment, Payout, WalletLedgerEntry


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "amount", "currency", "status", "gateway", "created_at")
    list_filter = ("status", "gateway", "currency")
    search_fields = ("id", "booking__id", "gateway_reference", "idempotency_key")


@admin.register(GatewayEvent)
class GatewayEventAdmin(admin.ModelAdmin):
    list_display = ("gateway", "event_id", "event_type", "payment", "received_at")
    search_fields = ("event_id", "event_type", "payment__id")


@admin.register(WalletLedgerEntry)
class WalletLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("provider", "entry_type", "direction", "amount", "currency", "is_available", "created_at")
    list_filter = ("entry_type", "direction", "is_available")
    search_fields = ("provider__display_name", "source_id", "notes")
    readonly_fields = [field.name for field in WalletLedgerEntry._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("provider", "requested_amount", "currency", "status", "created_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("provider__display_name", "payout_reference")
