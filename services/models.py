import uuid

from django.db import models


class ServiceCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = "svc_category"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class ServiceItem(models.Model):
    class PricingModel(models.TextChoices):
        FIXED = "fixed", "Fixed"
        ESTIMATED = "estimated", "Estimated"
        QUOTE_REQUIRED = "quote_required", "Quote required"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name="items")
    name = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    pricing_model = models.CharField(max_length=30, choices=PricingModel.choices)
    base_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "svc_item"
        ordering = ["category__sort_order", "name"]

    def __str__(self):
        return self.name
