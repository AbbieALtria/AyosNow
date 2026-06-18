from django.core.management.base import BaseCommand

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from accounts.models import User
from audit.models import AuditLog
from bookings.models import Assignment, Booking
from complaints.models import Complaint
from customers.models import Customer, CustomerAddress
from finance.models import Payment, Payout, WalletLedgerEntry
from geo.models import Barangay, City, Region
from providers.models import Provider, ProviderDocument
from services.models import ServiceCategory, ServiceItem


class Command(BaseCommand):
    help = "Seed AyosNow MVP roles, launch locations, and service catalog."

    def handle(self, *args, **options):
        groups = {role: Group.objects.get_or_create(name=role)[0] for role in ["dispatcher", "support_agent", "finance_officer", "operations_manager", "system_admin"]}
        model_permissions = {
            "dispatcher": [Booking, Assignment],
            "support_agent": [Customer, CustomerAddress, Booking, Complaint],
            "finance_officer": [Payment, WalletLedgerEntry, Payout],
            "operations_manager": [Provider, ProviderDocument, Booking, Assignment, Complaint],
            "system_admin": [User, AuditLog, Booking, Assignment, Customer, Provider, Payment, Payout, Complaint],
        }
        for role, models in model_permissions.items():
            for model in models:
                content_type = ContentType.objects.get_for_model(model)
                groups[role].permissions.add(*Permission.objects.filter(content_type=content_type))

        ncr, _ = Region.objects.get_or_create(name="National Capital Region")
        cities = ["Makati", "Taguig", "Quezon City", "Manila", "Pasig"]
        for city_name in cities:
            city, _ = City.objects.get_or_create(region=ncr, name=city_name)
            Barangay.objects.get_or_create(city=city, name="MVP Launch Area")

        home, _ = ServiceCategory.objects.get_or_create(
            name="Home Services",
            defaults={"description": "Cleaning, repair, maintenance, and home support.", "sort_order": 10},
        )
        maintenance, _ = ServiceCategory.objects.get_or_create(
            name="Maintenance",
            defaults={"description": "Basic repair and maintenance jobs.", "sort_order": 20},
        )
        delivery, _ = ServiceCategory.objects.get_or_create(
            name="Delivery & Errands",
            defaults={"description": "Local delivery and personal errands.", "sort_order": 30},
        )

        service_items = [
            (home, "General Cleaning", "fixed", "1200.00"),
            (home, "Deep Cleaning", "estimated", "2500.00"),
            (maintenance, "Plumbing Repair", "estimated", "1500.00"),
            (maintenance, "Electrical Repair", "estimated", "1500.00"),
            (delivery, "Local Errand", "fixed", "500.00"),
        ]
        for category, name, pricing_model, base_price in service_items:
            ServiceItem.objects.get_or_create(
                category=category,
                name=name,
                defaults={
                    "description": f"MVP service item for {name.lower()}.",
                    "pricing_model": pricing_model,
                    "base_price": base_price,
                },
            )

        self.stdout.write(self.style.SUCCESS("Seeded MVP roles, launch locations, and service catalog."))
