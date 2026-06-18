from django.contrib import admin

from .models import Customer, CustomerAddress


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "status", "user", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("first_name", "last_name", "user__mobile", "user__email")


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ("label", "customer", "city", "is_active", "created_at")
    list_filter = ("is_active", "city")
    search_fields = ("label", "line1", "customer__first_name", "customer__last_name")
