from decimal import Decimal

from rest_framework import serializers

from accounts.models import User
from audit.models import Notification
from bookings.models import Assignment, Booking
from complaints.models import Complaint
from core.models import UploadedFile
from customers.models import Customer, CustomerAddress
from finance.models import Payment, Payout, WalletLedgerEntry
from providers.models import Provider, ProviderBankAccount, ProviderCoverageCity, ProviderDocument, ProviderSkill
from services.models import ServiceCategory, ServiceItem


class RegisterCustomerSerializer(serializers.Serializer):
    mobile = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(min_length=8, write_only=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class RegisterProviderSerializer(serializers.Serializer):
    provider_type = serializers.ChoiceField(choices=Provider.ProviderType.choices)
    mobile = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)
    display_name = serializers.CharField()
    city_id = serializers.UUIDField()
    service_item_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    coverage_city_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    document_urls = serializers.ListField(child=serializers.URLField(), required=False, allow_empty=True)
    document_upload_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    bank_name = serializers.CharField(required=False, allow_blank=True)
    account_name = serializers.CharField(required=False, allow_blank=True)
    account_number = serializers.CharField(required=False, allow_blank=True)
    payout_method = serializers.CharField(required=False, allow_blank=True)


class ProviderSummarySerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source="city.name", read_only=True)
    service_names = serializers.SerializerMethodField()
    coverage_city_names = serializers.SerializerMethodField()
    document_count = serializers.IntegerField(source="documents.count", read_only=True)
    has_bank_account = serializers.SerializerMethodField()

    class Meta:
        model = Provider
        fields = [
            "id",
            "display_name",
            "provider_type",
            "verification_status",
            "verification_reason",
            "city",
            "city_name",
            "service_names",
            "coverage_city_names",
            "document_count",
            "has_bank_account",
            "created_at",
        ]

    def get_service_names(self, obj):
        return [skill.service_item.name for skill in obj.skills.select_related("service_item").all()]

    def get_coverage_city_names(self, obj):
        return [coverage.city.name for coverage in obj.coverage_cities.select_related("city").all()]

    def get_has_bank_account(self, obj):
        return hasattr(obj, "bank_account")


class ProviderProfileSerializer(ProviderSummarySerializer):
    documents = serializers.SerializerMethodField()
    bank_account = serializers.SerializerMethodField()

    class Meta(ProviderSummarySerializer.Meta):
        fields = ProviderSummarySerializer.Meta.fields + ["documents", "bank_account"]

    def get_documents(self, obj):
        return [
            {"id": str(document.id), "document_type": document.document_type, "status": document.status, "created_at": document.created_at}
            for document in obj.documents.order_by("-created_at")
        ]

    def get_bank_account(self, obj):
        account = getattr(obj, "bank_account", None)
        if not account:
            return None
        return {
            "bank_name": account.bank_name,
            "account_name": account.account_name,
            "account_number_last4": account.account_number_last4,
            "payout_method": account.payout_method,
        }


class UpdateProviderVerificationSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Provider.VerificationStatus.choices)
    reason = serializers.CharField(required=False, allow_blank=True)


class OtpSendSerializer(serializers.Serializer):
    mobile = serializers.CharField()
    purpose = serializers.CharField()


class OtpVerifySerializer(serializers.Serializer):
    otp_token = serializers.UUIDField()
    otp_code = serializers.CharField(min_length=6, max_length=6)


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)
    user_type = serializers.ChoiceField(choices=User.UserType.choices, required=False)


class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = [
            "id",
            "label",
            "region",
            "city",
            "barangay",
            "line1",
            "landmark",
            "latitude",
            "longitude",
            "is_active",
        ]


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "first_name", "last_name", "status"]


class ServiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceItem
        fields = ["id", "name", "description", "pricing_model", "base_price"]


class ServiceCategorySerializer(serializers.ModelSerializer):
    items = ServiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = ServiceCategory
        fields = ["id", "name", "description", "items"]


class BookingSerializer(serializers.ModelSerializer):
    latest_assignment_status = serializers.SerializerMethodField()
    latest_provider_name = serializers.SerializerMethodField()
    latest_payment_status = serializers.SerializerMethodField()
    open_complaint_status = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "customer",
            "service_item",
            "customer_address",
            "service_snapshot",
            "address_snapshot",
            "requested_schedule",
            "description",
            "status",
            "cancellation_reason",
            "created_at",
            "updated_at",
            "latest_assignment_status",
            "latest_provider_name",
            "latest_payment_status",
            "open_complaint_status",
        ]
        read_only_fields = ["service_snapshot", "address_snapshot", "status", "cancellation_reason"]

    def get_latest_assignment_status(self, obj):
        assignment = obj.assignments.order_by("-created_at").first()
        return assignment.status if assignment else None

    def get_latest_provider_name(self, obj):
        assignment = obj.assignments.select_related("provider").order_by("-created_at").first()
        return assignment.provider.display_name if assignment else None

    def get_latest_payment_status(self, obj):
        payment = obj.payments.order_by("-created_at").first()
        return payment.status if payment else None

    def get_open_complaint_status(self, obj):
        complaint = obj.complaints.exclude(status__in=[Complaint.Status.RESOLVED, Complaint.Status.REJECTED]).order_by("-created_at").first()
        return complaint.status if complaint else None


class CreateBookingSerializer(serializers.Serializer):
    service_item_id = serializers.UUIDField()
    customer_address_id = serializers.UUIDField()
    requested_schedule = serializers.DateTimeField()
    description = serializers.CharField()
    photo_urls = serializers.ListField(child=serializers.URLField(), required=False)


class CancelBookingSerializer(serializers.Serializer):
    reason = serializers.CharField()


class AssignProviderSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField()
    provider_id = serializers.UUIDField()
    reason = serializers.CharField()


class AssignmentSerializer(serializers.ModelSerializer):
    booking_status = serializers.CharField(source="booking.status", read_only=True)
    service_name = serializers.SerializerMethodField()
    open_complaint_status = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "booking",
            "booking_status",
            "service_name",
            "provider",
            "status",
            "open_complaint_status",
            "assignment_reason",
            "provider_response_reason",
            "completion_notes",
            "completion_evidence_urls",
            "created_at",
        ]

    def get_service_name(self, obj):
        return obj.booking.service_snapshot.get("name") if obj.booking.service_snapshot else obj.booking.service_item.name

    def get_open_complaint_status(self, obj):
        complaint = obj.booking.complaints.exclude(status__in=[Complaint.Status.RESOLVED, Complaint.Status.REJECTED]).order_by("-created_at").first()
        return complaint.status if complaint else None


class CompleteJobSerializer(serializers.Serializer):
    completion_notes = serializers.CharField()
    evidence_urls = serializers.ListField(child=serializers.URLField(), required=False)
    evidence_upload_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)


class CheckoutSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(choices=["card", "gcash", "maya", "bank_transfer"])


class PaymentWebhookSerializer(serializers.Serializer):
    gateway = serializers.CharField()
    event_id = serializers.CharField()
    event_type = serializers.CharField()
    payment_reference = serializers.CharField()
    status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3)


class SimulatePaymentCaptureSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField()


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "booking", "amount", "currency", "status", "gateway", "gateway_reference", "checkout_url"]


class WalletLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletLedgerEntry
        fields = ["id", "entry_type", "direction", "amount", "currency", "is_available", "notes", "created_at"]


class PayoutRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    notes = serializers.CharField(required=False, allow_blank=True)


class UpdatePayoutSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Payout.Status.choices)
    finance_reason = serializers.CharField(required=False, allow_blank=True)
    payout_reference = serializers.CharField(required=False, allow_blank=True)


class PayoutSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.display_name", read_only=True)

    class Meta:
        model = Payout
        fields = [
            "id",
            "provider",
            "provider_name",
            "requested_amount",
            "currency",
            "status",
            "provider_notes",
            "finance_reason",
            "payout_reference",
            "reviewed_at",
            "released_at",
            "created_at",
        ]


class CreateComplaintSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField()
    category = serializers.CharField()
    description = serializers.CharField()
    evidence_urls = serializers.ListField(child=serializers.URLField(), required=False)
    evidence_upload_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)


class UpdateComplaintSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Complaint.Status.choices)
    resolution = serializers.CharField(required=False, allow_blank=True)
    financial_impact = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)


class ComplaintSerializer(serializers.ModelSerializer):
    booking_status = serializers.CharField(source="booking.status", read_only=True)
    service_name = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = [
            "id",
            "booking",
            "booking_status",
            "service_name",
            "customer_name",
            "status",
            "category",
            "description",
            "resolution",
            "financial_impact",
            "created_at",
            "updated_at",
        ]

    def get_service_name(self, obj):
        return obj.booking.service_snapshot.get("name") if obj.booking.service_snapshot else obj.booking.service_item.name

    def get_customer_name(self, obj):
        return str(obj.booking.customer)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient_user",
            "audience_role",
            "title",
            "message",
            "entity_type",
            "entity_id",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields


class UploadRequestSerializer(serializers.Serializer):
    purpose = serializers.ChoiceField(choices=UploadedFile.Purpose.choices)
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=120)
    size_bytes = serializers.IntegerField(min_value=1)


class UploadConfirmSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField()


class UploadedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedFile
        fields = [
            "id",
            "purpose",
            "original_filename",
            "content_type",
            "size_bytes",
            "status",
            "public_url",
            "attached_entity_type",
            "attached_entity_id",
            "created_at",
            "uploaded_at",
        ]
        read_only_fields = fields
