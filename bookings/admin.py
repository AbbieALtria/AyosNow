from django.contrib import admin

from .models import Assignment, Booking, BookingStatusHistory


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "service_item", "status", "requested_schedule", "created_at")
    list_filter = ("status", "service_item", "requested_schedule")
    search_fields = ("id", "customer__first_name", "customer__last_name", "description")
    readonly_fields = ("service_snapshot", "address_snapshot")


@admin.register(BookingStatusHistory)
class BookingStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("booking", "from_status", "to_status", "actor_user", "created_at")
    list_filter = ("to_status", "created_at")
    search_fields = ("booking__id", "reason")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("booking", "provider", "status", "assigned_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("booking__id", "provider__display_name")
