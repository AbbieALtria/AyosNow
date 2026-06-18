from django.core.management import call_command
from django.core.management.base import BaseCommand

from accounts.models import User
from bookings.models import Assignment, Booking
from customers.models import Customer, CustomerAddress
from geo.models import Barangay, City, Region
from providers.models import Provider, ProviderCoverageCity, ProviderSkill
from services.models import ServiceItem


class Command(BaseCommand):
    help = "Create demo customer/provider records for local MVP testing."

    def handle(self, *args, **options):
        call_command("seed_mvp")

        city = City.objects.get(name="Makati")
        region = Region.objects.get(name="National Capital Region")
        barangay = Barangay.objects.filter(city=city).first()
        service_item = ServiceItem.objects.get(name="General Cleaning")

        customer_user, _ = User.objects.get_or_create(
            username="+639170000100",
            defaults={
                "mobile": "+639170000100",
                "email": "customer.demo@ayosnow.test",
                "user_type": User.UserType.CUSTOMER,
                "mobile_verified_at": "2026-06-17T00:00:00Z",
            },
        )
        customer_user.set_password("DemoPass123")
        customer_user.save()
        customer, _ = Customer.objects.get_or_create(
            user=customer_user,
            defaults={"first_name": "Demo", "last_name": "Customer"},
        )
        CustomerAddress.objects.get_or_create(
            customer=customer,
            label="Home",
            defaults={
                "region": region,
                "city": city,
                "barangay": barangay,
                "line1": "123 Ayos Street",
                "landmark": "Near MVP Launch Area",
            },
        )

        provider_user, _ = User.objects.get_or_create(
            username="+639170000200",
            defaults={
                "mobile": "+639170000200",
                "email": "provider.demo@ayosnow.test",
                "user_type": User.UserType.PROVIDER,
                "mobile_verified_at": "2026-06-17T00:00:00Z",
            },
        )
        provider_user.set_password("DemoPass123")
        provider_user.save()
        provider, _ = Provider.objects.get_or_create(
            user=provider_user,
            defaults={
                "provider_type": Provider.ProviderType.INDIVIDUAL,
                "display_name": "Demo Provider",
                "city": city,
                "verification_status": Provider.VerificationStatus.APPROVED,
            },
        )
        if provider.verification_status != Provider.VerificationStatus.APPROVED:
            provider.verification_status = Provider.VerificationStatus.APPROVED
            provider.save(update_fields=["verification_status"])
        ProviderSkill.objects.get_or_create(provider=provider, service_item=service_item)
        ProviderCoverageCity.objects.get_or_create(provider=provider, city=city)

        admin_user, _ = User.objects.get_or_create(
            username="demo-dispatcher",
            defaults={
                "email": "dispatcher.demo@ayosnow.test",
                "user_type": User.UserType.ADMIN,
                "is_staff": True,
                "is_superuser": False,
            },
        )
        admin_user.set_password("DemoPass123")
        admin_user.save()

        address = CustomerAddress.objects.get(customer=customer, label="Home")
        booking, _ = Booking.objects.get_or_create(
            customer=customer,
            service_item=service_item,
            customer_address=address,
            description="Demo cleaning job for provider portal.",
            defaults={
                "service_snapshot": {
                    "id": str(service_item.id),
                    "name": service_item.name,
                    "pricing_model": service_item.pricing_model,
                },
                "address_snapshot": {
                    "id": str(address.id),
                    "label": address.label,
                    "line1": address.line1,
                    "city_id": str(address.city_id),
                },
                "requested_schedule": "2026-06-18T10:00:00Z",
                "status": Booking.Status.ASSIGNED,
            },
        )
        Assignment.objects.get_or_create(
            booking=booking,
            provider=provider,
            status=Assignment.Status.ASSIGNED,
            defaults={
                "assigned_by": admin_user,
                "assignment_reason": "Demo assigned job",
            },
        )

        self.stdout.write(self.style.SUCCESS("Seeded demo customer and provider."))
