from decimal import Decimal
import secrets

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import OtpChallenge, User
from accounts.sms import get_sms_backend
from audit.models import AuditLog, Notification, notify_ops, notify_user, write_audit
from bookings.models import Assignment, Booking
from complaints.models import Complaint, ComplaintEvidence
from core.models import UploadedFile
from core.uploads import build_public_url, build_upload_url, upload_is_expired
from customers.models import Customer, CustomerAddress
from finance.models import GatewayEvent, Payment, Payout, WalletLedgerEntry
from finance.gateways import canonical_payload, get_payment_gateway
from providers.models import Provider, ProviderBankAccount, ProviderCoverageCity, ProviderDocument, ProviderSkill
from services.models import ServiceCategory, ServiceItem

from .responses import error, success
from .serializers import (
    AssignProviderSerializer,
    AssignmentSerializer,
    BookingSerializer,
    CancelBookingSerializer,
    CheckoutSerializer,
    CompleteJobSerializer,
    ComplaintSerializer,
    CreateBookingSerializer,
    CreateComplaintSerializer,
    CustomerAddressSerializer,
    CustomerSerializer,
    LoginSerializer,
    OtpSendSerializer,
    OtpVerifySerializer,
    PaymentWebhookSerializer,
    PayoutRequestSerializer,
    PayoutSerializer,
    ProviderSummarySerializer,
    ProviderProfileSerializer,
    RegisterCustomerSerializer,
    RegisterProviderSerializer,
    ServiceCategorySerializer,
    SimulatePaymentCaptureSerializer,
    UpdateComplaintSerializer,
    UpdatePayoutSerializer,
    UpdateProviderVerificationSerializer,
    UploadConfirmSerializer,
    UploadedFileSerializer,
    UploadRequestSerializer,
    WalletLedgerSerializer,
    NotificationSerializer,
)


def _idempotency_key(request):
    return request.headers.get("Idempotency-Key", "").strip()


def _current_customer(user):
    return getattr(user, "customer_profile", None)


def _current_provider(user):
    return getattr(user, "provider_profile", None)


def _token_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "user": {
            "id": str(user.id),
            "username": user.username,
            "mobile": user.mobile,
            "email": user.email,
            "user_type": user.user_type,
            "is_staff": user.is_staff,
        },
    }


def _display(value):
    return str(value).replace("_", " ")


def _booking_label(booking):
    return booking.service_snapshot.get("name") if booking.service_snapshot else booking.service_item.name


def _timeline_item(*, created_at, event_type, title, actor=None, details=None):
    return {
        "created_at": created_at,
        "event_type": event_type,
        "title": title,
        "actor": actor.username if actor else None,
        "details": details or {},
    }


def _audit_timeline(entity_type, entity_id):
    return [
        _timeline_item(
            created_at=event.created_at,
            event_type="audit",
            title=_display(event.action),
            actor=event.actor_user,
            details={"before": event.before_data, "after": event.after_data},
        )
        for event in AuditLog.objects.filter(entity_type=entity_type, entity_id=entity_id).select_related("actor_user")
    ]


def _sum_amount(queryset):
    return queryset.aggregate(total=Sum("amount"))["total"] or Decimal("0")


def _sum_requested(queryset):
    return queryset.aggregate(total=Sum("requested_amount"))["total"] or Decimal("0")


def _provider_available_balance(provider):
    credits = _sum_amount(provider.wallet_entries.filter(direction=WalletLedgerEntry.Direction.CREDIT, is_available=True))
    debits = _sum_amount(provider.wallet_entries.filter(direction=WalletLedgerEntry.Direction.DEBIT, is_available=True))
    return credits - debits


def _provider_held_balance(provider):
    return _sum_requested(
        provider.payouts.filter(
            status__in=[
                Payout.Status.REQUESTED,
                Payout.Status.UNDER_REVIEW,
                Payout.Status.APPROVED,
            ]
        )
    )


def _create_wallet_entry_once(**kwargs):
    entry, _created = WalletLedgerEntry.objects.get_or_create(
        provider=kwargs["provider"],
        source_type=kwargs["source_type"],
        source_id=kwargs["source_id"],
        entry_type=kwargs["entry_type"],
        defaults=kwargs,
    )
    return entry


def _reject_legacy_urls(urls):
    if urls:
        return error("VALIDATION_ERROR", "Use signed upload_ids instead of raw file URLs.", status=400)
    return None


def _claim_uploads(*, upload_ids, owner, purpose, entity_type, entity_id):
    uploads = []
    for upload_id in upload_ids or []:
        upload = get_object_or_404(UploadedFile, id=upload_id)
        if upload.owner_user_id != owner.id and not owner.is_staff:
            return None, error("FORBIDDEN", "You cannot attach another user's upload.", status=403)
        if upload.purpose != purpose:
            return None, error("VALIDATION_ERROR", "Upload purpose does not match this action.", status=400)
        if upload.status != UploadedFile.Status.UPLOADED:
            return None, error("VALIDATION_ERROR", "Upload must be confirmed before it can be attached.", status=400)
        upload.status = UploadedFile.Status.ATTACHED
        upload.attached_entity_type = entity_type
        upload.attached_entity_id = entity_id
        upload.save(update_fields=["status", "attached_entity_type", "attached_entity_id"])
        uploads.append(upload)
    return uploads, None


def _can_access_upload(user, upload):
    if user.is_staff:
        return True
    if upload.owner_user_id == user.id:
        return True
    provider = _current_provider(user)
    customer = _current_customer(user)
    if upload.attached_entity_type == "complaint" and upload.attached_entity_id:
        complaint = Complaint.objects.filter(id=upload.attached_entity_id).first()
        if not complaint:
            return False
        if customer and complaint.booking.customer_id == customer.id:
            return True
        if provider and complaint.booking.assignments.filter(provider=provider).exists():
            return True
    if upload.attached_entity_type == "booking" and upload.attached_entity_id:
        booking = Booking.objects.filter(id=upload.attached_entity_id).first()
        if not booking:
            return False
        if customer and booking.customer_id == customer.id:
            return True
        if provider and booking.assignments.filter(provider=provider).exists():
            return True
    if upload.attached_entity_type == "provider" and upload.attached_entity_id and provider:
        return provider.id == upload.attached_entity_id
    return False


def _generate_otp_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def _issue_otp(*, mobile, purpose, user=None):
    cooldown_start = timezone.now() - timezone.timedelta(seconds=settings.AYOSNOW_OTP_RESEND_COOLDOWN_SECONDS)
    recent = OtpChallenge.objects.filter(
        mobile=mobile,
        purpose=purpose,
        verified_at__isnull=True,
        created_at__gte=cooldown_start,
    ).order_by("-created_at").first()
    if recent:
        return None, None, "OTP was sent recently. Please wait before requesting another code."
    code = _generate_otp_code()
    otp = OtpChallenge.objects.create(
        user=user,
        mobile=mobile,
        purpose=purpose,
        otp_hash=make_password(code),
        max_attempts=settings.AYOSNOW_OTP_MAX_ATTEMPTS,
        expires_at=timezone.now() + timezone.timedelta(seconds=settings.AYOSNOW_OTP_EXPIRY_SECONDS),
    )
    get_sms_backend(settings.AYOSNOW_SMS_BACKEND).send_otp(mobile=mobile, code=code, purpose=purpose)
    return otp, code, None


def _otp_response(otp, code=None):
    data = {"otp_token": str(otp.id), "expires_in": settings.AYOSNOW_OTP_EXPIRY_SECONDS}
    if settings.DEBUG and code:
        data["dev_otp"] = code
    return data


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def register_customer(request):
    serializer = RegisterCustomerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=data["mobile"],
                mobile=data["mobile"],
                email=data.get("email") or None,
                password=data["password"],
                user_type=User.UserType.CUSTOMER,
                is_active=True,
            )
            customer = Customer.objects.create(
                user=user,
                first_name=data["first_name"],
                last_name=data["last_name"],
            )
            otp, code, issue_error = _issue_otp(mobile=data["mobile"], purpose=OtpChallenge.Purpose.REGISTER, user=user)
            if issue_error:
                raise IntegrityError(issue_error)
            write_audit(actor=user, action="customer_registered", entity_type="customer", entity_id=customer.id)
    except IntegrityError:
        return error("CONFLICT", "Mobile or email already exists.", status=409)
    return success({"customer_id": str(customer.id), "otp_required": True, **_otp_response(otp, code)}, status=201)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def register_provider(request):
    serializer = RegisterProviderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    legacy_error = _reject_legacy_urls(data.get("document_urls", []))
    if legacy_error:
        return legacy_error
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=data["mobile"],
                mobile=data["mobile"],
                password=data["password"],
                user_type=User.UserType.PROVIDER,
                is_active=True,
            )
            provider = Provider.objects.create(
                user=user,
                provider_type=data["provider_type"],
                display_name=data["display_name"],
                city_id=data["city_id"],
            )
            for service_item_id in data["service_item_ids"]:
                ProviderSkill.objects.create(provider=provider, service_item_id=service_item_id)
            coverage_city_ids = data.get("coverage_city_ids") or [data["city_id"]]
            for city_id in coverage_city_ids:
                ProviderCoverageCity.objects.get_or_create(provider=provider, city_id=city_id)
            uploads, upload_error = _claim_uploads(
                upload_ids=data.get("document_upload_ids", []),
                owner=user,
                purpose=UploadedFile.Purpose.PROVIDER_DOCUMENT,
                entity_type="provider",
                entity_id=provider.id,
            )
            if upload_error:
                raise IntegrityError("invalid_provider_document_upload")
            for index, upload in enumerate(uploads, start=1):
                ProviderDocument.objects.create(
                    provider=provider,
                    upload=upload,
                    document_type=f"application_document_{index}",
                    file_url=upload.public_url,
                )
            account_number = data.get("account_number", "")
            if data.get("bank_name") and data.get("account_name") and account_number:
                ProviderBankAccount.objects.create(
                    provider=provider,
                    bank_name=data["bank_name"],
                    account_name=data["account_name"],
                    account_number_last4=account_number[-4:],
                    payout_method=data.get("payout_method") or "bank_transfer",
                )
            write_audit(actor=user, action="provider_registered", entity_type="provider", entity_id=provider.id)
            notify_ops(
                title="New provider application",
                message=f"{provider.display_name} submitted a provider application.",
                entity_type="provider",
                entity_id=provider.id,
            )
    except IntegrityError:
        return error("CONFLICT", "Mobile already exists or provider data is invalid.", status=409)
    return success({"provider_id": str(provider.id), "verification_status": provider.verification_status}, status=201)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    identifier = serializer.validated_data["identifier"]
    user = User.objects.filter(mobile=identifier).first() or User.objects.filter(email=identifier).first() or User.objects.filter(username=identifier).first()
    if not user:
        return error("UNAUTHORIZED", "Invalid credentials.", status=401)
    authenticated = authenticate(request, username=user.username, password=serializer.validated_data["password"])
    if not authenticated:
        return error("UNAUTHORIZED", "Invalid credentials.", status=401)
    expected_type = serializer.validated_data.get("user_type")
    if expected_type and authenticated.user_type != expected_type:
        return error("FORBIDDEN", "User type does not match this login flow.", status=403)
    return success(_token_payload(authenticated))


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def send_otp(request):
    serializer = OtpSendSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    otp, code, issue_error = _issue_otp(
        mobile=serializer.validated_data["mobile"],
        purpose=serializer.validated_data["purpose"],
    )
    if issue_error:
        return error("RATE_LIMITED", issue_error, status=429)
    return success(_otp_response(otp, code))


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def verify_otp(request):
    serializer = OtpVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    otp = get_object_or_404(OtpChallenge, id=serializer.validated_data["otp_token"])
    if otp.expires_at < timezone.now():
        return error("BUSINESS_RULE_FAILED", "OTP has expired.", status=422)
    if otp.attempt_count >= otp.max_attempts:
        return error("RATE_LIMITED", "OTP attempt limit reached.", status=429)
    if not check_password(serializer.validated_data["otp_code"], otp.otp_hash):
        otp.attempt_count += 1
        otp.save(update_fields=["attempt_count"])
        return error("BUSINESS_RULE_FAILED", "Invalid OTP code.", status=422)
    otp.verified_at = timezone.now()
    otp.save(update_fields=["verified_at"])
    if otp.user and otp.purpose == OtpChallenge.Purpose.REGISTER:
        otp.user.mobile_verified_at = timezone.now()
        otp.user.save(update_fields=["mobile_verified_at"])
    payload = {"verified": True}
    if otp.user:
        payload.update(_token_payload(otp.user))
    return success(payload)


@api_view(["GET"])
def customer_me(request):
    customer = _current_customer(request.user)
    if not customer:
        return error("FORBIDDEN", "Current user is not a customer.", status=403)
    return success(
        {
            "customer": CustomerSerializer(customer).data,
            "addresses": CustomerAddressSerializer(customer.addresses.all(), many=True).data,
        }
    )


@api_view(["POST"])
def request_upload(request):
    serializer = UploadRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if data["content_type"] not in settings.AYOSNOW_UPLOAD_ALLOWED_TYPES:
        return error("VALIDATION_ERROR", "File type is not allowed.", status=400)
    if data["size_bytes"] > settings.AYOSNOW_UPLOAD_MAX_BYTES:
        return error("VALIDATION_ERROR", "File exceeds the maximum upload size.", status=400)
    suffix = data["filename"].split(".")[-1].lower() if "." in data["filename"] else "bin"
    storage_key = f"{data['purpose']}/{request.user.id}/{secrets.token_urlsafe(18)}.{suffix}"
    expires_at = timezone.now() + timezone.timedelta(seconds=settings.AYOSNOW_UPLOAD_URL_TTL_SECONDS)
    upload = UploadedFile.objects.create(
        owner_user=request.user,
        purpose=data["purpose"],
        original_filename=data["filename"],
        content_type=data["content_type"],
        size_bytes=data["size_bytes"],
        storage_key=storage_key,
        public_url=build_public_url(storage_key),
        upload_expires_at=expires_at,
    )
    return success(
        {
            "upload": UploadedFileSerializer(upload).data,
            "upload_url": build_upload_url(upload),
            "expires_at": expires_at,
            "max_size_bytes": settings.AYOSNOW_UPLOAD_MAX_BYTES,
            "allowed_types": settings.AYOSNOW_UPLOAD_ALLOWED_TYPES,
        },
        status=201,
    )


@api_view(["POST"])
def confirm_upload(request):
    serializer = UploadConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    upload = get_object_or_404(UploadedFile, id=serializer.validated_data["upload_id"])
    if upload.owner_user_id != request.user.id and not request.user.is_staff:
        return error("FORBIDDEN", "You cannot confirm another user's upload.", status=403)
    if upload_is_expired(upload):
        upload.status = UploadedFile.Status.REJECTED
        upload.save(update_fields=["status"])
        return error("BUSINESS_RULE_FAILED", "Upload URL has expired.", status=422)
    if upload.status == UploadedFile.Status.PENDING:
        upload.status = UploadedFile.Status.UPLOADED
        upload.uploaded_at = timezone.now()
        upload.save(update_fields=["status", "uploaded_at"])
    return success(UploadedFileSerializer(upload).data)


@api_view(["GET"])
def get_upload(request, upload_id):
    upload = get_object_or_404(UploadedFile, id=upload_id)
    if not _can_access_upload(request.user, upload):
        return error("FORBIDDEN", "You cannot access this upload.", status=403)
    return success(UploadedFileSerializer(upload).data)


@api_view(["GET"])
def notifications(request):
    role_filter = Q(recipient_user=request.user)
    if request.user.is_staff or request.user.user_type == User.UserType.ADMIN:
        role_filter |= Q(audience_role=Notification.AudienceRole.OPS)
    elif request.user.user_type == User.UserType.CUSTOMER:
        role_filter |= Q(audience_role=Notification.AudienceRole.CUSTOMER)
    elif request.user.user_type == User.UserType.PROVIDER:
        role_filter |= Q(audience_role=Notification.AudienceRole.PROVIDER)
    items = Notification.objects.filter(role_filter).order_by("-created_at")[:50]
    unread_count = Notification.objects.filter(role_filter, is_read=False).count()
    return success(NotificationSerializer(items, many=True).data, meta={"unread_count": unread_count})


@api_view(["POST"])
def mark_notification_read(request, notification_id):
    role_filter = Q(id=notification_id, recipient_user=request.user)
    if request.user.is_staff or request.user.user_type == User.UserType.ADMIN:
        role_filter |= Q(id=notification_id, audience_role=Notification.AudienceRole.OPS)
    notification = get_object_or_404(Notification, role_filter)
    notification.mark_read()
    return success(NotificationSerializer(notification).data)


@api_view(["GET"])
def booking_timeline(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    customer = _current_customer(request.user)
    provider = _current_provider(request.user)
    allowed = request.user.is_staff or (customer and booking.customer_id == customer.id)
    allowed = allowed or (provider and booking.assignments.filter(provider=provider).exists())
    if not allowed:
        return error("FORBIDDEN", "You cannot access this booking timeline.", status=403)
    status_events = [
        _timeline_item(
            created_at=event.created_at,
            event_type="booking_status",
            title=f"Booking moved from {_display(event.from_status or 'new')} to {_display(event.to_status)}",
            actor=event.actor_user,
            details={"from": event.from_status, "to": event.to_status, "reason": event.reason},
        )
        for event in booking.status_history.select_related("actor_user").all()
    ]
    audit_events = _audit_timeline("booking", booking.id)
    assignment_events = []
    for assignment in booking.assignments.select_related("provider", "assigned_by").all():
        assignment_events.append(
            _timeline_item(
                created_at=assignment.created_at,
                event_type="assignment",
                title=f"Assigned to {assignment.provider.display_name}",
                actor=assignment.assigned_by,
                details={"assignment_id": str(assignment.id), "status": assignment.status},
            )
        )
        assignment_events.extend(_audit_timeline("assignment", assignment.id))
    complaint_events = [
        _timeline_item(
            created_at=complaint.created_at,
            event_type="complaint",
            title=f"Complaint opened: {_display(complaint.category)}",
            actor=complaint.opened_by,
            details={"complaint_id": str(complaint.id), "status": complaint.status},
        )
        for complaint in booking.complaints.select_related("opened_by").all()
    ]
    payment_events = [
        _timeline_item(
            created_at=payment.updated_at,
            event_type="payment",
            title=f"Payment {_display(payment.status)}",
            details={"payment_id": str(payment.id), "amount": str(payment.amount), "currency": payment.currency},
        )
        for payment in booking.payments.all()
    ]
    timeline = sorted(status_events + audit_events + assignment_events + complaint_events + payment_events, key=lambda event: event["created_at"])
    return success(timeline)


@api_view(["GET"])
def complaint_timeline(request, complaint_id):
    complaint = get_object_or_404(Complaint, id=complaint_id)
    customer = _current_customer(request.user)
    provider = _current_provider(request.user)
    allowed = request.user.is_staff or (customer and complaint.booking.customer_id == customer.id)
    allowed = allowed or (provider and complaint.booking.assignments.filter(provider=provider).exists())
    if not allowed:
        return error("FORBIDDEN", "You cannot access this complaint timeline.", status=403)
    timeline = [
        _timeline_item(
            created_at=complaint.created_at,
            event_type="complaint",
            title="Complaint opened",
            actor=complaint.opened_by,
            details={"status": complaint.status, "category": complaint.category},
        )
    ]
    timeline.extend(_audit_timeline("complaint", complaint.id))
    return success(sorted(timeline, key=lambda event: event["created_at"]))


@api_view(["GET"])
def payout_timeline(request, payout_id):
    payout = get_object_or_404(Payout, id=payout_id)
    provider = _current_provider(request.user)
    if not request.user.is_staff and not (provider and payout.provider_id == provider.id):
        return error("FORBIDDEN", "You cannot access this payout timeline.", status=403)
    timeline = [
        _timeline_item(
            created_at=payout.created_at,
            event_type="payout",
            title="Payout requested",
            details={"status": payout.status, "amount": str(payout.requested_amount), "currency": payout.currency},
        )
    ]
    timeline.extend(_audit_timeline("payout", payout.id))
    if payout.reviewed_at:
        timeline.append(
            _timeline_item(
                created_at=payout.reviewed_at,
                event_type="payout_review",
                title=f"Payout {_display(payout.status)}",
                actor=payout.reviewed_by,
                details={"reference": payout.payout_reference, "reason": payout.finance_reason},
            )
        )
    return success(sorted(timeline, key=lambda event: event["created_at"]))


@api_view(["POST"])
def create_address(request):
    customer = _current_customer(request.user)
    if not customer:
        return error("FORBIDDEN", "Current user is not a customer.", status=403)
    serializer = CustomerAddressSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    address = serializer.save(customer=customer)
    write_audit(actor=request.user, action="customer_address_created", entity_type="customer_address", entity_id=address.id)
    return success(CustomerAddressSerializer(address).data, status=201)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def service_categories(request):
    categories = ServiceCategory.objects.filter(is_active=True, items__is_active=True).distinct().prefetch_related("items")
    return success(ServiceCategorySerializer(categories, many=True).data)


@api_view(["POST"])
def create_booking(request):
    key = _idempotency_key(request)
    if not key:
        return error("VALIDATION_ERROR", "Idempotency-Key header is required.", status=400)
    customer = _current_customer(request.user)
    if not customer:
        return error("FORBIDDEN", "Current user is not a customer.", status=403)
    serializer = CreateBookingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    service_item = get_object_or_404(ServiceItem, id=data["service_item_id"], is_active=True)
    address = get_object_or_404(CustomerAddress, id=data["customer_address_id"], customer=customer, is_active=True)
    booking = Booking.objects.create(
        customer=customer,
        service_item=service_item,
        customer_address=address,
        service_snapshot={"id": str(service_item.id), "name": service_item.name, "pricing_model": service_item.pricing_model},
        address_snapshot={"id": str(address.id), "label": address.label, "line1": address.line1, "city_id": str(address.city_id)},
        requested_schedule=data["requested_schedule"],
        description=data["description"],
    )
    booking.transition_to(Booking.Status.PENDING_DISPATCH, actor=request.user, reason="booking_created")
    write_audit(actor=request.user, action="booking_created", entity_type="booking", entity_id=booking.id, request=request)
    notify_ops(
        title="New booking waiting for dispatch",
        message=f"{_booking_label(booking)} is ready to assign.",
        entity_type="booking",
        entity_id=booking.id,
    )
    return success(BookingSerializer(booking).data, status=201)


@api_view(["GET"])
def customer_bookings(request):
    customer = _current_customer(request.user)
    if not customer:
        return error("FORBIDDEN", "Current user is not a customer.", status=403)
    bookings = (
        Booking.objects.filter(customer=customer)
        .select_related("service_item", "customer_address")
        .prefetch_related("assignments", "payments")
        .order_by("-created_at")
    )
    return success(BookingSerializer(bookings, many=True).data)


@api_view(["GET"])
def get_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    customer = _current_customer(request.user)
    provider = _current_provider(request.user)
    allowed = request.user.is_staff or (customer and booking.customer_id == customer.id)
    allowed = allowed or (provider and booking.assignments.filter(provider=provider).exists())
    if not allowed:
        return error("FORBIDDEN", "You cannot access this booking.", status=403)
    return success(BookingSerializer(booking).data)


@api_view(["POST"])
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    serializer = CancelBookingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    if booking.status == Booking.Status.IN_PROGRESS and not request.user.is_staff:
        return error("BUSINESS_RULE_FAILED", "Customer cannot cancel an in-progress booking.", status=422)
    booking.transition_to(Booking.Status.CANCELLED, actor=request.user, reason=serializer.validated_data["reason"])
    write_audit(actor=request.user, action="booking_cancelled", entity_type="booking", entity_id=booking.id, request=request)
    notify_ops(title="Booking cancelled", message=f"Booking {booking.id} was cancelled.", entity_type="booking", entity_id=booking.id)
    return success(BookingSerializer(booking).data)


@api_view(["GET"])
def dispatch_queue(request):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    status_filter = request.query_params.get("status")
    search = request.query_params.get("q", "").strip()
    statuses = [Booking.Status.PENDING_DISPATCH, Booking.Status.PROVIDER_DECLINED]
    if status_filter:
        statuses = [status_filter]
    bookings = Booking.objects.filter(status__in=statuses).select_related("service_item", "customer_address", "customer")
    if search:
        bookings = bookings.filter(
            Q(id__icontains=search)
            | Q(description__icontains=search)
            | Q(service_item__name__icontains=search)
            | Q(customer_address__line1__icontains=search)
        )
    return success(BookingSerializer(bookings.order_by("requested_schedule")[:100], many=True).data)


@api_view(["GET"])
def approved_providers(request):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    service_item_id = request.query_params.get("service_item_id")
    city_id = request.query_params.get("city_id")
    providers = Provider.objects.filter(verification_status=Provider.VerificationStatus.APPROVED)
    if service_item_id:
        providers = providers.filter(skills__service_item_id=service_item_id)
    if city_id:
        providers = providers.filter(coverage_cities__city_id=city_id)
    providers = providers.distinct().order_by("display_name").prefetch_related("skills__service_item", "coverage_cities__city", "documents")
    return success(ProviderSummarySerializer(providers, many=True).data)


@api_view(["GET"])
def provider_me(request):
    provider = _current_provider(request.user)
    if not provider:
        return error("FORBIDDEN", "Current user is not a provider.", status=403)
    provider = (
        Provider.objects.select_related("city", "bank_account")
        .prefetch_related("skills__service_item", "coverage_cities__city", "documents")
        .get(id=provider.id)
    )
    return success(ProviderProfileSerializer(provider).data)


@api_view(["GET"])
def admin_providers(request):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    status_filter = request.query_params.get("status")
    search = request.query_params.get("q", "").strip()
    providers = Provider.objects.select_related("city").prefetch_related("skills__service_item", "coverage_cities__city", "documents").order_by("-created_at")
    if status_filter:
        providers = providers.filter(verification_status=status_filter)
    if search:
        providers = providers.filter(
            Q(display_name__icontains=search)
            | Q(user__mobile__icontains=search)
            | Q(user__email__icontains=search)
            | Q(city__name__icontains=search)
            | Q(skills__service_item__name__icontains=search)
        ).distinct()
    return success(ProviderSummarySerializer(providers[:100], many=True).data)


@api_view(["POST"])
def update_provider_verification(request, provider_id):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    provider = get_object_or_404(Provider, id=provider_id)
    serializer = UpdateProviderVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    before = {"verification_status": provider.verification_status, "verification_reason": provider.verification_reason}
    provider.transition_verification(
        serializer.validated_data["status"],
        actor=request.user,
        reason=serializer.validated_data.get("reason", ""),
    )
    write_audit(
        actor=request.user,
        action="provider_verification_updated",
        entity_type="provider",
        entity_id=provider.id,
        before=before,
        after={"verification_status": provider.verification_status, "verification_reason": provider.verification_reason},
        request=request,
    )
    notify_user(
        user=provider.user,
        title="Provider verification updated",
        message=f"Your provider application is now {_display(provider.verification_status)}.",
        entity_type="provider",
        entity_id=provider.id,
    )
    return success(ProviderProfileSerializer(provider).data)


@api_view(["GET"])
def provider_timeline(request, provider_id):
    provider = get_object_or_404(Provider, id=provider_id)
    current_provider = _current_provider(request.user)
    if not request.user.is_staff and not (current_provider and current_provider.id == provider.id):
        return error("FORBIDDEN", "You cannot access this provider timeline.", status=403)
    history_events = [
        _timeline_item(
            created_at=event.created_at,
            event_type="provider_verification",
            title=f"Verification moved from {_display(event.from_status or 'new')} to {_display(event.to_status)}",
            actor=event.actor_user,
            details={"from": event.from_status, "to": event.to_status, "reason": event.reason},
        )
        for event in provider.verification_history.select_related("actor_user").all()
    ]
    audit_events = _audit_timeline("provider", provider.id)
    return success(sorted(history_events + audit_events, key=lambda event: event["created_at"]))


@api_view(["POST"])
def assign_provider(request):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    serializer = AssignProviderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    booking = get_object_or_404(Booking, id=data["booking_id"])
    provider = get_object_or_404(Provider, id=data["provider_id"])
    if provider.verification_status != Provider.VerificationStatus.APPROVED:
        return error("BUSINESS_RULE_FAILED", "Provider must be approved before assignment.", status=422)
    if not ProviderSkill.objects.filter(provider=provider, service_item=booking.service_item).exists():
        return error("BUSINESS_RULE_FAILED", "Provider does not have the required service skill.", status=422)
    if not ProviderCoverageCity.objects.filter(provider=provider, city_id=booking.customer_address.city_id).exists():
        return error("BUSINESS_RULE_FAILED", "Provider does not cover the booking city.", status=422)
    assignment = Assignment.objects.create(
        booking=booking,
        provider=provider,
        assigned_by=request.user,
        assignment_reason=data["reason"],
    )
    booking.transition_to(Booking.Status.ASSIGNED, actor=request.user, reason=data["reason"])
    write_audit(actor=request.user, action="provider_assigned", entity_type="assignment", entity_id=assignment.id, request=request)
    notify_user(
        user=booking.customer.user,
        title="Provider assigned",
        message=f"{provider.display_name} has been assigned to your {_booking_label(booking)} booking.",
        entity_type="booking",
        entity_id=booking.id,
    )
    notify_user(
        user=provider.user,
        title="New job assigned",
        message=f"You have a new {_booking_label(booking)} job to review.",
        entity_type="booking",
        entity_id=booking.id,
    )
    return success(AssignmentSerializer(assignment).data)


@api_view(["GET"])
def provider_jobs(request):
    provider = _current_provider(request.user)
    if not provider:
        return error("FORBIDDEN", "Current user is not a provider.", status=403)
    return success(AssignmentSerializer(provider.assignments.order_by("-created_at"), many=True).data)


@api_view(["POST"])
def accept_job(request, assignment_id):
    provider = _current_provider(request.user)
    if not provider:
        return error("FORBIDDEN", "Current user is not a provider.", status=403)
    if provider.verification_status != Provider.VerificationStatus.APPROVED:
        return error("FORBIDDEN", "Provider must be approved to accept jobs.", status=403)
    assignment = get_object_or_404(Assignment, id=assignment_id, provider=provider)
    assignment.status = Assignment.Status.ACCEPTED
    assignment.responded_at = timezone.now()
    assignment.save(update_fields=["status", "responded_at"])
    assignment.booking.transition_to(Booking.Status.PROVIDER_ACCEPTED, actor=request.user, reason="provider_accepted")
    write_audit(actor=request.user, action="job_accepted", entity_type="assignment", entity_id=assignment.id, request=request)
    notify_user(
        user=assignment.booking.customer.user,
        title="Provider accepted your booking",
        message=f"{assignment.provider.display_name} accepted your {_booking_label(assignment.booking)} job.",
        entity_type="booking",
        entity_id=assignment.booking_id,
    )
    notify_ops(
        title="Provider accepted job",
        message=f"{assignment.provider.display_name} accepted booking {assignment.booking_id}.",
        entity_type="booking",
        entity_id=assignment.booking_id,
    )
    return success(AssignmentSerializer(assignment).data)


@api_view(["POST"])
def complete_job(request, job_id):
    provider = _current_provider(request.user)
    if not provider:
        return error("FORBIDDEN", "Current user is not a provider.", status=403)
    if provider.verification_status != Provider.VerificationStatus.APPROVED:
        return error("FORBIDDEN", "Provider must be approved to complete jobs.", status=403)
    assignment = get_object_or_404(Assignment, id=job_id, provider=provider, status=Assignment.Status.ACCEPTED)
    serializer = CompleteJobSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    legacy_error = _reject_legacy_urls(serializer.validated_data.get("evidence_urls", []))
    if legacy_error:
        return legacy_error
    assignment.status = Assignment.Status.COMPLETED
    assignment.completion_notes = serializer.validated_data["completion_notes"]
    uploads, upload_error = _claim_uploads(
        upload_ids=serializer.validated_data.get("evidence_upload_ids", []),
        owner=request.user,
        purpose=UploadedFile.Purpose.COMPLETION_EVIDENCE,
        entity_type="booking",
        entity_id=assignment.booking_id,
    )
    if upload_error:
        return upload_error
    assignment.completion_evidence_urls = [upload.public_url for upload in uploads]
    assignment.save(update_fields=["status", "completion_notes", "completion_evidence_urls"])
    assignment.booking.transition_to(Booking.Status.COMPLETED_BY_PROVIDER, actor=request.user, reason="provider_completed")
    write_audit(actor=request.user, action="job_completed_by_provider", entity_type="assignment", entity_id=assignment.id, request=request)
    notify_user(
        user=assignment.booking.customer.user,
        title="Job marked complete",
        message=f"{assignment.provider.display_name} marked your {_booking_label(assignment.booking)} booking complete.",
        entity_type="booking",
        entity_id=assignment.booking_id,
    )
    notify_ops(
        title="Provider completed job",
        message=f"{assignment.provider.display_name} completed booking {assignment.booking_id}.",
        entity_type="booking",
        entity_id=assignment.booking_id,
    )
    return success(BookingSerializer(assignment.booking).data)


@api_view(["POST"])
def create_checkout(request):
    key = _idempotency_key(request)
    if not key:
        return error("VALIDATION_ERROR", "Idempotency-Key header is required.", status=400)
    serializer = CheckoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    booking = get_object_or_404(Booking, id=serializer.validated_data["booking_id"])
    amount = booking.service_item.base_price or Decimal("0.00")
    gateway = get_payment_gateway()
    payment, created = Payment.objects.get_or_create(
        idempotency_key=key,
        defaults={
            "booking": booking,
            "customer": booking.customer,
            "amount": amount,
            "currency": settings.AYOSNOW_DEFAULT_CURRENCY,
            "gateway": gateway.gateway_name,
        },
    )
    if created:
        checkout = gateway.create_checkout(
            payment=payment,
            payment_method=serializer.validated_data["payment_method"],
            idempotency_key=key,
        )
        payment.gateway = checkout["gateway"]
        payment.gateway_reference = checkout["gateway_reference"]
        payment.checkout_url = checkout["checkout_url"]
        payment.save(update_fields=["gateway", "gateway_reference", "checkout_url", "updated_at"])
    return success({"payment_id": str(payment.id), "checkout_url": payment.checkout_url, "status": payment.status}, status=201 if created else 200)


def _capture_payment(payment):
    if payment.status == Payment.Status.CAPTURED:
        return False
    payment.status = Payment.Status.CAPTURED
    payment.save(update_fields=["status", "updated_at"])
    assignment = payment.booking.assignments.filter(status__in=[Assignment.Status.ACCEPTED, Assignment.Status.COMPLETED]).first()
    if assignment and not WalletLedgerEntry.objects.filter(source_type="payment", source_id=payment.id, provider=assignment.provider).exists():
        provider_amount = payment.amount * Decimal(str(1 - settings.AYOSNOW_COMMISSION_RATE))
        _create_wallet_entry_once(
            provider=assignment.provider,
            source_type="payment",
            source_id=payment.id,
            entry_type=WalletLedgerEntry.EntryType.PROVIDER_EARNING,
            direction=WalletLedgerEntry.Direction.CREDIT,
            amount=provider_amount,
            currency=payment.currency,
            notes="Provider earning from captured payment",
        )
        notify_user(
            user=assignment.provider.user,
            title="Wallet credited",
            message=f"Payment captured for booking {payment.booking_id}; provider earnings were credited.",
            entity_type="booking",
            entity_id=payment.booking_id,
        )
    notify_user(
        user=payment.customer.user,
        title="Payment captured",
        message=f"Payment for your {_booking_label(payment.booking)} booking was captured.",
        entity_type="booking",
        entity_id=payment.booking_id,
    )
    return True


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def payment_webhook(request):
    signature = request.headers.get("X-AyosNow-Signature", "")
    gateway = get_payment_gateway()
    try:
        gateway.verify_webhook_signature(payload=canonical_payload(request.data), signature=signature)
    except Exception:
        return error("INVALID_SIGNATURE", "Payment webhook signature is invalid.", status=401)
    serializer = PaymentWebhookSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    payment = Payment.objects.filter(gateway_reference=data["payment_reference"]).first()
    if payment and (data["amount"] != payment.amount or data["currency"] != payment.currency):
        return error("WEBHOOK_MISMATCH", "Payment webhook amount or currency does not match local payment.", status=422)
    event, created = GatewayEvent.objects.get_or_create(
        gateway=data["gateway"],
        event_id=data["event_id"],
        defaults={"payment": payment, "event_type": data["event_type"], "payload": request.data},
    )
    if not created:
        return success({"duplicate": True})
    if payment and data["status"] == "captured":
        _capture_payment(payment)
    return success({"accepted": True})


@api_view(["POST"])
def simulate_payment_capture(request):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    serializer = SimulatePaymentCaptureSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    booking = get_object_or_404(Booking, id=serializer.validated_data["booking_id"])
    payment = booking.payments.order_by("-created_at").first()
    if not payment:
        payment = Payment.objects.create(
            booking=booking,
            customer=booking.customer,
            amount=booking.service_item.base_price or Decimal("0.00"),
            currency=settings.AYOSNOW_DEFAULT_CURRENCY,
            status=Payment.Status.PENDING,
            gateway="manual_simulator",
            gateway_reference=f"SIM-{booking.id}",
            idempotency_key=f"simulate-{booking.id}",
        )
    changed = _capture_payment(payment)
    write_audit(actor=request.user, action="payment_capture_simulated", entity_type="payment", entity_id=payment.id, request=request)
    return success({"payment_id": str(payment.id), "status": payment.status, "changed": changed})


@api_view(["GET"])
def provider_wallet(request):
    provider = _current_provider(request.user)
    if not provider:
        return error("FORBIDDEN", "Current user is not a provider.", status=403)
    entries = provider.wallet_entries.order_by("-created_at")[:20]
    return success(
        {
            "provider_id": str(provider.id),
            "available_balance": _provider_available_balance(provider),
            "held_balance": _provider_held_balance(provider),
            "currency": settings.AYOSNOW_DEFAULT_CURRENCY,
            "recent_entries": WalletLedgerSerializer(entries, many=True).data,
        }
    )


@api_view(["POST"])
def request_payout(request):
    key = _idempotency_key(request)
    if not key:
        return error("VALIDATION_ERROR", "Idempotency-Key header is required.", status=400)
    provider = _current_provider(request.user)
    if not provider:
        return error("FORBIDDEN", "Current user is not a provider.", status=403)
    serializer = PayoutRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    amount = serializer.validated_data["amount"]
    with transaction.atomic():
        existing = Payout.objects.select_for_update().filter(idempotency_key=key).first()
        if existing:
            if existing.provider_id != provider.id or existing.requested_amount != amount:
                return error("IDEMPOTENCY_CONFLICT", "Idempotency-Key was already used with different payout data.", status=409)
            return success(PayoutSerializer(existing).data)

        provider = Provider.objects.select_for_update().get(id=provider.id)
        available = _provider_available_balance(provider)
        if amount > available:
            return error("BUSINESS_RULE_FAILED", "Payout amount exceeds available wallet balance.", status=422)

        payout = Payout.objects.create(
            provider=provider,
            idempotency_key=key,
            requested_amount=amount,
            currency=settings.AYOSNOW_DEFAULT_CURRENCY,
            provider_notes=serializer.validated_data.get("notes", ""),
        )
        _create_wallet_entry_once(
            provider=provider,
            source_type="payout",
            source_id=payout.id,
            entry_type=WalletLedgerEntry.EntryType.HOLD,
            direction=WalletLedgerEntry.Direction.DEBIT,
            amount=amount,
            currency=payout.currency,
            is_available=True,
            created_by=request.user,
            notes="Payout hold",
        )
        write_audit(actor=request.user, action="payout_requested", entity_type="payout", entity_id=payout.id, request=request)
        notify_user(
            user=provider.user,
            title="Payout requested",
            message=f"Your payout request for {payout.currency} {payout.requested_amount} is queued for review.",
            entity_type="payout",
            entity_id=payout.id,
        )
        notify_ops(
            title="New payout request",
            message=f"{provider.display_name} requested {payout.currency} {payout.requested_amount}.",
            entity_type="payout",
            entity_id=payout.id,
        )
    return success(PayoutSerializer(payout).data, status=201)


@api_view(["GET"])
def provider_payouts(request):
    provider = _current_provider(request.user)
    if not provider:
        return error("FORBIDDEN", "Current user is not a provider.", status=403)
    payouts = provider.payouts.order_by("-created_at")
    return success(PayoutSerializer(payouts, many=True).data)


@api_view(["GET"])
def admin_payouts(request):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    status_filter = request.query_params.get("status")
    search = request.query_params.get("q", "").strip()
    payouts = Payout.objects.select_related("provider").order_by("-created_at")
    if status_filter:
        payouts = payouts.filter(status=status_filter)
    if search:
        payouts = payouts.filter(
            Q(provider__display_name__icontains=search)
            | Q(provider_notes__icontains=search)
            | Q(finance_reason__icontains=search)
            | Q(payout_reference__icontains=search)
            | Q(id__icontains=search)
        )
    return success(PayoutSerializer(payouts[:100], many=True).data)


@api_view(["POST"])
def update_payout(request, payout_id):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    serializer = UpdatePayoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    status_value = serializer.validated_data["status"]
    with transaction.atomic():
        payout = get_object_or_404(Payout.objects.select_for_update().select_related("provider", "provider__user"), id=payout_id)
        terminal_statuses = [Payout.Status.RELEASED, Payout.Status.REJECTED, Payout.Status.FAILED]
        if payout.status in terminal_statuses and status_value != payout.status:
            return error("BUSINESS_RULE_FAILED", "Terminal payout status cannot be changed.", status=422)

        before = {"status": payout.status, "finance_reason": payout.finance_reason, "payout_reference": payout.payout_reference}
        payout.status = status_value
        payout.finance_reason = serializer.validated_data.get("finance_reason", payout.finance_reason)
        payout.payout_reference = serializer.validated_data.get("payout_reference", payout.payout_reference)
        payout.reviewed_by = request.user
        payout.reviewed_at = timezone.now()
        if status_value == Payout.Status.RELEASED:
            payout.released_at = payout.released_at or timezone.now()
            _create_wallet_entry_once(
                provider=payout.provider,
                source_type="payout",
                source_id=payout.id,
                entry_type=WalletLedgerEntry.EntryType.PAYOUT_RELEASED,
                direction=WalletLedgerEntry.Direction.DEBIT,
                amount=payout.requested_amount,
                currency=payout.currency,
                is_available=False,
                created_by=request.user,
                notes="Payout released",
            )
        elif status_value in [Payout.Status.FAILED, Payout.Status.REJECTED]:
            _create_wallet_entry_once(
                provider=payout.provider,
                source_type="payout",
                source_id=payout.id,
                entry_type=WalletLedgerEntry.EntryType.HOLD_RELEASED,
                direction=WalletLedgerEntry.Direction.CREDIT,
                amount=payout.requested_amount,
                currency=payout.currency,
                is_available=True,
                created_by=request.user,
                notes=f"Payout {status_value} and hold released",
            )
        payout.save()
        write_audit(
            actor=request.user,
            action="payout_updated",
            entity_type="payout",
            entity_id=payout.id,
            before=before,
            after={"status": payout.status, "finance_reason": payout.finance_reason, "payout_reference": payout.payout_reference},
            request=request,
        )
        notify_user(
            user=payout.provider.user,
            title="Payout status updated",
            message=f"Your payout is now {_display(payout.status)}.",
            entity_type="payout",
            entity_id=payout.id,
        )
    return success(PayoutSerializer(payout).data)


@api_view(["GET"])
def finance_summary(request):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    available_total = Decimal("0")
    held_total = Decimal("0")
    for provider in Provider.objects.all():
        available_total += _provider_available_balance(provider)
        held_total += _provider_held_balance(provider)
    return success(
        {
            "captured_revenue": Payment.objects.filter(status=Payment.Status.CAPTURED).aggregate(total=Sum("amount"))["total"] or Decimal("0"),
            "provider_earnings": WalletLedgerEntry.objects.filter(entry_type=WalletLedgerEntry.EntryType.PROVIDER_EARNING).aggregate(total=Sum("amount"))["total"] or Decimal("0"),
            "payout_requested": Payout.objects.filter(status=Payout.Status.REQUESTED).aggregate(total=Sum("requested_amount"))["total"] or Decimal("0"),
            "payout_released": Payout.objects.filter(status=Payout.Status.RELEASED).aggregate(total=Sum("requested_amount"))["total"] or Decimal("0"),
            "wallet_available": available_total,
            "wallet_held": held_total,
        }
    )


@api_view(["GET"])
def finance_reconciliation(request):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    captured_revenue = Payment.objects.filter(status=Payment.Status.CAPTURED).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    provider_earnings = WalletLedgerEntry.objects.filter(entry_type=WalletLedgerEntry.EntryType.PROVIDER_EARNING).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    active_holds = _sum_requested(Payout.objects.filter(status__in=[Payout.Status.REQUESTED, Payout.Status.UNDER_REVIEW, Payout.Status.APPROVED]))
    released_payouts = _sum_requested(Payout.objects.filter(status=Payout.Status.RELEASED))
    restored_holds = _sum_amount(WalletLedgerEntry.objects.filter(entry_type=WalletLedgerEntry.EntryType.HOLD_RELEASED))
    provider_rows = []
    total_available = Decimal("0")
    total_held = Decimal("0")
    for provider in Provider.objects.order_by("display_name"):
        available = _provider_available_balance(provider)
        held = _provider_held_balance(provider)
        total_available += available
        total_held += held
        provider_rows.append(
            {
                "provider_id": str(provider.id),
                "provider_name": provider.display_name,
                "available_balance": available,
                "held_balance": held,
                "active_payouts": provider.payouts.filter(status__in=[Payout.Status.REQUESTED, Payout.Status.UNDER_REVIEW, Payout.Status.APPROVED]).count(),
                "ledger_entries": provider.wallet_entries.count(),
            }
        )
    return success(
        {
            "captured_revenue": captured_revenue,
            "provider_earnings": provider_earnings,
            "active_holds": active_holds,
            "released_payouts": released_payouts,
            "restored_holds": restored_holds,
            "wallet_available": total_available,
            "wallet_held": total_held,
            "providers": provider_rows,
        }
    )


@api_view(["POST"])
def create_complaint(request):
    serializer = CreateComplaintSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    legacy_error = _reject_legacy_urls(serializer.validated_data.get("evidence_urls", []))
    if legacy_error:
        return legacy_error
    booking = get_object_or_404(Booking, id=serializer.validated_data["booking_id"])
    complaint = Complaint.objects.create(
        booking=booking,
        opened_by=request.user,
        category=serializer.validated_data["category"],
        description=serializer.validated_data["description"],
    )
    uploads, upload_error = _claim_uploads(
        upload_ids=serializer.validated_data.get("evidence_upload_ids", []),
        owner=request.user,
        purpose=UploadedFile.Purpose.COMPLAINT_EVIDENCE,
        entity_type="complaint",
        entity_id=complaint.id,
    )
    if upload_error:
        complaint.delete()
        return upload_error
    for upload in uploads:
        ComplaintEvidence.objects.create(
            complaint=complaint,
            uploaded_by=request.user,
            upload=upload,
            file_url=upload.public_url,
            file_type=upload.content_type,
        )
    booking.transition_to(Booking.Status.DISPUTED, actor=request.user, reason="complaint_created")
    write_audit(actor=request.user, action="complaint_created", entity_type="complaint", entity_id=complaint.id, request=request)
    notify_user(
        user=booking.customer.user,
        title="Complaint submitted",
        message=f"Your complaint for booking {booking.id} has been opened.",
        entity_type="complaint",
        entity_id=complaint.id,
    )
    assignment = booking.assignments.select_related("provider__user").order_by("-created_at").first()
    if assignment:
        notify_user(
            user=assignment.provider.user,
            title="Booking has an open complaint",
            message=f"Complaint opened for booking {booking.id}.",
            entity_type="complaint",
            entity_id=complaint.id,
        )
    notify_ops(
        title="New complaint opened",
        message=f"{complaint.category} complaint opened for booking {booking.id}.",
        entity_type="complaint",
        entity_id=complaint.id,
    )
    return success(ComplaintSerializer(complaint).data, status=201)


@api_view(["GET"])
def customer_complaints(request):
    customer = _current_customer(request.user)
    if not customer:
        return error("FORBIDDEN", "Current user is not a customer.", status=403)
    complaints = Complaint.objects.filter(booking__customer=customer).select_related("booking", "booking__customer").order_by("-created_at")
    return success(ComplaintSerializer(complaints, many=True).data)


@api_view(["GET"])
def admin_complaints(request):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    status_filter = request.query_params.get("status")
    search = request.query_params.get("q", "").strip()
    complaints = Complaint.objects.select_related("booking", "booking__customer").order_by("-created_at")
    if status_filter:
        complaints = complaints.filter(status=status_filter)
    if search:
        complaints = complaints.filter(
            Q(id__icontains=search)
            | Q(category__icontains=search)
            | Q(description__icontains=search)
            | Q(resolution__icontains=search)
            | Q(booking__service_item__name__icontains=search)
        )
    return success(ComplaintSerializer(complaints[:100], many=True).data)


@api_view(["POST"])
def update_complaint(request, complaint_id):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    complaint = get_object_or_404(Complaint, id=complaint_id)
    serializer = UpdateComplaintSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    before = {"status": complaint.status, "resolution": complaint.resolution, "financial_impact": str(complaint.financial_impact)}
    complaint.status = serializer.validated_data["status"]
    complaint.resolution = serializer.validated_data.get("resolution", complaint.resolution)
    if "financial_impact" in serializer.validated_data:
        complaint.financial_impact = serializer.validated_data["financial_impact"]
    if complaint.status in [Complaint.Status.RESOLVED, Complaint.Status.REJECTED]:
        complaint.resolved_by = request.user
        complaint.resolved_at = timezone.now()
    complaint.save()
    write_audit(
        actor=request.user,
        action="complaint_updated",
        entity_type="complaint",
        entity_id=complaint.id,
        before=before,
        after={"status": complaint.status, "resolution": complaint.resolution, "financial_impact": str(complaint.financial_impact)},
        request=request,
    )
    notify_user(
        user=complaint.booking.customer.user,
        title="Complaint status updated",
        message=f"Your complaint is now {_display(complaint.status)}.",
        entity_type="complaint",
        entity_id=complaint.id,
    )
    assignment = complaint.booking.assignments.select_related("provider__user").order_by("-created_at").first()
    if assignment:
        notify_user(
            user=assignment.provider.user,
            title="Complaint status updated",
            message=f"Complaint for booking {complaint.booking_id} is now {_display(complaint.status)}.",
            entity_type="complaint",
            entity_id=complaint.id,
        )
    return success(ComplaintSerializer(complaint).data)


@api_view(["GET"])
def executive_report(request):
    if not request.user.is_staff:
        return error("FORBIDDEN", "Admin access required.", status=403)
    return success(
        {
            "booking_count": Booking.objects.count(),
            "captured_revenue": Payment.objects.filter(status=Payment.Status.CAPTURED).aggregate(total=Sum("amount"))["total"] or Decimal("0"),
            "provider_earnings": WalletLedgerEntry.objects.filter(entry_type=WalletLedgerEntry.EntryType.PROVIDER_EARNING).aggregate(total=Sum("amount"))["total"] or Decimal("0"),
            "payout_total": Payout.objects.filter(status=Payout.Status.RELEASED).aggregate(total=Sum("requested_amount"))["total"] or Decimal("0"),
            "complaint_count": Complaint.objects.count(),
            "cancellation_rate": 0,
        }
    )
