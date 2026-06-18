from django.contrib import admin

from .models import ServiceCategory, ServiceItem


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(ServiceItem)
class ServiceItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "pricing_model", "base_price", "is_active")
    list_filter = ("category", "pricing_model", "is_active")
    search_fields = ("name", "description")
