from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import OtpChallenge, User
from audit.models import AuditLog, Notification
from bookings.models import Assignment, Booking
from customers.models import CustomerAddress
from finance.models import GatewayEvent, Payment, Payout, WalletLedgerEntry
from finance.gateways import canonical_payload, sign_payload
from complaints.models import Complaint
from core.models import UploadedFile
from providers.models import Provider, ProviderCoverageCity, ProviderSkill
from services.models import ServiceItem


class ApiFlowTests(TestCase):
    def setUp(self):
        call_command("seed_demo", verbosity=0)
        self.client = APIClient()
        self.customer_user = User.objects.get(mobile="+639170000100")
        self.provider_user = User.objects.get(mobile="+639170000200")
        self.provider = self.provider_user.provider_profile
        self.service_item = ServiceItem.objects.get(name="General Cleaning")
        self.address = CustomerAddress.objects.get(customer=self.customer_user.customer_profile)
        self.admin_user = User.objects.create_superuser(
            username="admin-test",
            email="admin@test.local",
            password="AdminPass123",
            user_type=User.UserType.ADMIN,
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def test_catalog_is_public(self):
        response = self.client.get("/api/v1/services/categories")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertGreaterEqual(len(response.data["data"]), 1)

    @override_settings(DEBUG=True)
    def test_customer_registration_login_and_otp(self):
        response = self.client.post(
            "/api/v1/auth/customer/register",
            {
                "mobile": "+639170000300",
                "password": "StrongPass123",
                "first_name": "New",
                "last_name": "Customer",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        otp_token = response.data["data"]["otp_token"]
        otp_code = response.data["data"]["dev_otp"]

        bad = self.client.post("/api/v1/auth/otp/verify", {"otp_token": otp_token, "otp_code": "000000"}, format="json")
        self.assertEqual(bad.status_code, 422)

        good = self.client.post("/api/v1/auth/otp/verify", {"otp_token": otp_token, "otp_code": otp_code}, format="json")
        self.assertEqual(good.status_code, 200)
        self.assertIn("access_token", good.data["data"])

        login = self.client.post(
            "/api/v1/auth/login",
            {"identifier": "+639170000300", "password": "StrongPass123", "user_type": "customer"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("refresh_token", login.data["data"])
        refresh = self.client.post("/api/v1/auth/token/refresh", {"refresh": login.data["data"]["refresh_token"]}, format="json")
        self.assertEqual(refresh.status_code, 200)
        self.assertIn("access", refresh.data)

        mismatch = self.client.post(
            "/api/v1/auth/login",
            {"identifier": "+639170000300", "password": "StrongPass123", "user_type": "provider"},
            format="json",
        )
        self.assertEqual(mismatch.status_code, 403)

    @override_settings(AYOSNOW_OTP_RESEND_COOLDOWN_SECONDS=60)
    def test_otp_resend_cooldown(self):
        first = self.client.post("/api/v1/auth/otp/send", {"mobile": "+639179999999", "purpose": "login"}, format="json")
        self.assertEqual(first.status_code, 200)
        second = self.client.post("/api/v1/auth/otp/send", {"mobile": "+639179999999", "purpose": "login"}, format="json")
        self.assertEqual(second.status_code, 429)

    def test_expired_otp_and_max_attempts(self):
        expired = OtpChallenge.objects.create(
            mobile="+639178888888",
            purpose=OtpChallenge.Purpose.LOGIN,
            otp_hash=make_password("111111"),
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        expired_response = self.client.post(
            "/api/v1/auth/otp/verify",
            {"otp_token": str(expired.id), "otp_code": "111111"},
            format="json",
        )
        self.assertEqual(expired_response.status_code, 422)

        limited = OtpChallenge.objects.create(
            mobile="+639177777777",
            purpose=OtpChallenge.Purpose.LOGIN,
            otp_hash=make_password("222222"),
            attempt_count=5,
            max_attempts=5,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )
        limited_response = self.client.post(
            "/api/v1/auth/otp/verify",
            {"otp_token": str(limited.id), "otp_code": "222222"},
            format="json",
        )
        self.assertEqual(limited_response.status_code, 429)

    def test_booking_dispatch_provider_checkout_wallet_and_complaint_flow(self):
        self.auth(self.customer_user)
        booking_response = self.client.post(
            "/api/v1/bookings",
            {
                "service_item_id": str(self.service_item.id),
                "customer_address_id": str(self.address.id),
                "requested_schedule": timezone.now().isoformat(),
                "description": "Please clean the unit.",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="booking-key-001",
        )
        self.assertEqual(booking_response.status_code, 201)
        booking_id = booking_response.data["data"]["id"]
        history = self.client.get("/api/v1/customers/bookings")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data["data"][0]["id"], booking_id)
        self.assertIn("latest_assignment_status", history.data["data"][0])
        self.assertTrue(Notification.objects.filter(audience_role=Notification.AudienceRole.OPS, entity_id=booking_id).exists())

        self.auth(self.admin_user)
        assign_response = self.client.post(
            "/api/v1/admin/dispatch/assign",
            {"booking_id": booking_id, "provider_id": str(self.provider.id), "reason": "Best eligible provider"},
            format="json",
        )
        self.assertEqual(assign_response.status_code, 200)
        assignment_id = assign_response.data["data"]["id"]
        provider_notifications = self.client.get("/api/v1/notifications")
        self.assertEqual(provider_notifications.status_code, 200)

        self.auth(self.provider_user)
        provider_notifications = self.client.get("/api/v1/notifications")
        self.assertEqual(provider_notifications.status_code, 200)
        self.assertTrue(any(item["title"] == "New job assigned" for item in provider_notifications.data["data"]))
        accept_response = self.client.post(f"/api/v1/providers/jobs/{assignment_id}/accept")
        self.assertEqual(accept_response.status_code, 200)
        complete_response = self.client.post(
            f"/api/v1/providers/jobs/{assignment_id}/complete",
            {"completion_notes": "Done", "evidence_urls": []},
            format="json",
        )
        self.assertEqual(complete_response.status_code, 200)

        self.auth(self.customer_user)
        booking_timeline = self.client.get(f"/api/v1/bookings/{booking_id}/timeline")
        self.assertEqual(booking_timeline.status_code, 200)
        self.assertTrue(any(item["event_type"] == "booking_status" for item in booking_timeline.data["data"]))
        checkout_response = self.client.post(
            "/api/v1/payments/checkout",
            {"booking_id": booking_id, "payment_method": "gcash"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="payment-key-001",
        )
        self.assertEqual(checkout_response.status_code, 201)
        payment = Payment.objects.get(id=checkout_response.data["data"]["payment_id"])

        self.client.force_authenticate(user=None)
        webhook_payload = {
            "gateway": payment.gateway,
            "event_id": "evt-001",
            "event_type": "payment.captured",
            "payment_reference": payment.gateway_reference,
            "status": "captured",
            "amount": str(payment.amount),
            "currency": payment.currency,
        }
        bad_signature = self.client.post(
            "/api/v1/payments/webhook",
            webhook_payload,
            format="json",
            HTTP_X_AYOSNOW_SIGNATURE="sha256=bad",
        )
        self.assertEqual(bad_signature.status_code, 401)
        self.assertEqual(GatewayEvent.objects.filter(event_id="evt-001").count(), 0)

        signature = sign_payload(canonical_payload(webhook_payload), settings.PAYMENT_WEBHOOK_SECRET)
        webhook = self.client.post("/api/v1/payments/webhook", webhook_payload, format="json", HTTP_X_AYOSNOW_SIGNATURE=signature)
        self.assertEqual(webhook.status_code, 200)
        duplicate = self.client.post("/api/v1/payments/webhook", webhook_payload, format="json", HTTP_X_AYOSNOW_SIGNATURE=signature)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(GatewayEvent.objects.filter(event_id="evt-001").count(), 1)
        self.assertEqual(WalletLedgerEntry.objects.filter(provider=self.provider).count(), 1)

        mismatch_payload = {**webhook_payload, "event_id": "evt-amount-mismatch", "amount": "1.00"}
        mismatch_signature = sign_payload(canonical_payload(mismatch_payload), settings.PAYMENT_WEBHOOK_SECRET)
        mismatch = self.client.post(
            "/api/v1/payments/webhook",
            mismatch_payload,
            format="json",
            HTTP_X_AYOSNOW_SIGNATURE=mismatch_signature,
        )
        self.assertEqual(mismatch.status_code, 422)

        self.auth(self.provider_user)
        wallet = self.client.get("/api/v1/providers/wallet")
        self.assertEqual(wallet.status_code, 200)
        self.assertGreater(float(wallet.data["data"]["available_balance"]), 0)

        self.auth(self.customer_user)
        complaint = self.client.post(
            "/api/v1/complaints",
            {"booking_id": booking_id, "category": "quality", "description": "Needs review."},
            format="json",
        )
        self.assertEqual(complaint.status_code, 201)
        self.assertEqual(Booking.objects.get(id=booking_id).status, Booking.Status.DISPUTED)
        customer_complaints = self.client.get("/api/v1/customers/complaints")
        self.assertEqual(customer_complaints.status_code, 200)
        self.assertEqual(customer_complaints.data["data"][0]["status"], Complaint.Status.OPEN)
        complaint_id = complaint.data["data"]["id"]
        complaint_timeline = self.client.get(f"/api/v1/complaints/{complaint_id}/timeline")
        self.assertEqual(complaint_timeline.status_code, 200)
        self.assertTrue(any(item["title"] == "Complaint opened" for item in complaint_timeline.data["data"]))

        self.auth(self.admin_user)
        ops_complaints = self.client.get("/api/v1/admin/complaints")
        self.assertEqual(ops_complaints.status_code, 200)
        complaint_filter = self.client.get("/api/v1/admin/complaints?status=open&q=quality")
        self.assertEqual(complaint_filter.status_code, 200)
        self.assertTrue(any(item["id"] == complaint_id for item in complaint_filter.data["data"]))
        complaint_id = ops_complaints.data["data"][0]["id"]
        update = self.client.post(
            f"/api/v1/admin/complaints/{complaint_id}/update",
            {"status": "resolved", "resolution": "Resolved after review.", "financial_impact": "0.00"},
            format="json",
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.data["data"]["status"], Complaint.Status.RESOLVED)
        notifications = self.client.get("/api/v1/notifications")
        self.assertEqual(notifications.status_code, 200)
        self.assertTrue(any(item["title"] == "New complaint opened" for item in notifications.data["data"]))

    def test_ops_provider_lookup_and_payment_simulation(self):
        self.auth(self.customer_user)
        booking_response = self.client.post(
            "/api/v1/bookings",
            {
                "service_item_id": str(self.service_item.id),
                "customer_address_id": str(self.address.id),
                "requested_schedule": timezone.now().isoformat(),
                "description": "Ops dispatch test.",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="booking-key-ops",
        )
        booking_id = booking_response.data["data"]["id"]

        self.auth(self.admin_user)
        providers = self.client.get(f"/api/v1/admin/providers/approved?service_item_id={self.service_item.id}")
        self.assertEqual(providers.status_code, 200)
        self.assertGreaterEqual(len(providers.data["data"]), 1)
        provider_search = self.client.get("/api/v1/admin/providers?q=Demo")
        self.assertEqual(provider_search.status_code, 200)
        self.assertTrue(any(item["display_name"] == "Demo Provider" for item in provider_search.data["data"]))
        provider_status_filter = self.client.get("/api/v1/admin/providers?status=approved")
        self.assertEqual(provider_status_filter.status_code, 200)
        self.assertTrue(all(item["verification_status"] == Provider.VerificationStatus.APPROVED for item in provider_status_filter.data["data"]))

        queue_search = self.client.get("/api/v1/admin/dispatch/queue?q=Ops")
        self.assertEqual(queue_search.status_code, 200)
        self.assertTrue(any(item["id"] == booking_id for item in queue_search.data["data"]))

        assign = self.client.post(
            "/api/v1/admin/dispatch/assign",
            {"booking_id": booking_id, "provider_id": str(self.provider.id), "reason": "Ops test assignment"},
            format="json",
        )
        self.assertEqual(assign.status_code, 200)

        self.auth(self.provider_user)
        assignment_id = assign.data["data"]["id"]
        self.client.post(f"/api/v1/providers/jobs/{assignment_id}/accept")

        self.auth(self.admin_user)
        capture = self.client.post("/api/v1/admin/payments/simulate-capture", {"booking_id": booking_id}, format="json")
        self.assertEqual(capture.status_code, 200)
        self.assertEqual(capture.data["data"]["status"], Payment.Status.CAPTURED)
        self.assertEqual(WalletLedgerEntry.objects.filter(provider=self.provider).count(), 1)
        ledger_entry = WalletLedgerEntry.objects.get(provider=self.provider, entry_type=WalletLedgerEntry.EntryType.PROVIDER_EARNING)
        ledger_entry.notes = "Changed after posting"
        with self.assertRaises(ValidationError):
            ledger_entry.save()

        self.auth(self.provider_user)
        oversized = self.client.post(
            "/api/v1/providers/payouts",
            {"amount": "100000.00", "notes": "Too much"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="payout-key-too-large",
        )
        self.assertEqual(oversized.status_code, 422)
        payout = self.client.post(
            "/api/v1/providers/payouts",
            {"amount": "100.00", "notes": "Weekly payout"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="payout-key-ops",
        )
        self.assertEqual(payout.status_code, 201)
        payout_id = payout.data["data"]["id"]
        duplicate = self.client.post(
            "/api/v1/providers/payouts",
            {"amount": "100.00", "notes": "Weekly payout"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="payout-key-ops",
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.data["data"]["id"], payout_id)
        conflict = self.client.post(
            "/api/v1/providers/payouts",
            {"amount": "101.00", "notes": "Different"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="payout-key-ops",
        )
        self.assertEqual(conflict.status_code, 409)
        wallet_after_hold = self.client.get("/api/v1/providers/wallet")
        self.assertEqual(wallet_after_hold.status_code, 200)
        self.assertEqual(Decimal(wallet_after_hold.data["data"]["held_balance"]), Decimal("100.00"))
        provider_notifications = self.client.get("/api/v1/notifications")
        self.assertEqual(provider_notifications.status_code, 200)
        self.assertTrue(any(item["title"] == "Payout requested" for item in provider_notifications.data["data"]))
        history = self.client.get("/api/v1/providers/payouts/history")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data["data"][0]["status"], Payout.Status.REQUESTED)

        self.auth(self.admin_user)
        payouts = self.client.get("/api/v1/admin/payouts")
        self.assertEqual(payouts.status_code, 200)
        payout_id = payouts.data["data"][0]["id"]
        payout_filter = self.client.get("/api/v1/admin/payouts?status=requested&q=Weekly")
        self.assertEqual(payout_filter.status_code, 200)
        self.assertTrue(any(item["id"] == payout_id for item in payout_filter.data["data"]))
        update = self.client.post(
            f"/api/v1/admin/payouts/{payout_id}/update",
            {"status": "released", "finance_reason": "Paid", "payout_reference": "BANK-001"},
            format="json",
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.data["data"]["status"], Payout.Status.RELEASED)
        changed_terminal = self.client.post(
            f"/api/v1/admin/payouts/{payout_id}/update",
            {"status": "failed", "finance_reason": "Too late", "payout_reference": "BANK-001"},
            format="json",
        )
        self.assertEqual(changed_terminal.status_code, 422)
        payout_timeline = self.client.get(f"/api/v1/payouts/{payout_id}/timeline")
        self.assertEqual(payout_timeline.status_code, 200)
        self.assertTrue(any(item["event_type"] == "payout_review" for item in payout_timeline.data["data"]))
        summary = self.client.get("/api/v1/admin/finance/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertIn("payout_released", summary.data["data"])
        self.assertIn("wallet_available", summary.data["data"])
        reconciliation = self.client.get("/api/v1/admin/finance/reconciliation")
        self.assertEqual(reconciliation.status_code, 200)
        self.assertIn("providers", reconciliation.data["data"])

    def test_failed_payout_releases_wallet_hold(self):
        WalletLedgerEntry.objects.create(
            provider=self.provider,
            source_type="test",
            source_id=self.service_item.id,
            entry_type=WalletLedgerEntry.EntryType.ADJUSTMENT,
            direction=WalletLedgerEntry.Direction.CREDIT,
            amount="150.00",
            currency="PHP",
            notes="Test funding",
        )
        self.auth(self.provider_user)
        payout = self.client.post(
            "/api/v1/providers/payouts",
            {"amount": "125.00", "notes": "Release hold test"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="payout-key-failed",
        )
        self.assertEqual(payout.status_code, 201)
        wallet_with_hold = self.client.get("/api/v1/providers/wallet")
        self.assertEqual(Decimal(wallet_with_hold.data["data"]["available_balance"]), Decimal("25.00"))
        self.assertEqual(Decimal(wallet_with_hold.data["data"]["held_balance"]), Decimal("125.00"))

        self.auth(self.admin_user)
        update = self.client.post(
            f"/api/v1/admin/payouts/{payout.data['data']['id']}/update",
            {"status": "failed", "finance_reason": "Bank rejected", "payout_reference": "BANK-FAIL"},
            format="json",
        )
        self.assertEqual(update.status_code, 200)

        self.auth(self.provider_user)
        wallet_after_failure = self.client.get("/api/v1/providers/wallet")
        self.assertEqual(Decimal(wallet_after_failure.data["data"]["available_balance"]), Decimal("150.00"))
        self.assertEqual(Decimal(wallet_after_failure.data["data"]["held_balance"]), Decimal("0.00"))

    def test_provider_verification_controls_dispatch(self):
        pending_user = User.objects.create_user(
            username="+639170009900",
            mobile="+639170009900",
            password="ProviderPass123",
            user_type=User.UserType.PROVIDER,
        )
        pending_provider = Provider.objects.create(
            user=pending_user,
            provider_type=Provider.ProviderType.INDIVIDUAL,
            display_name="Pending Provider",
            city=self.address.city,
        )
        ProviderSkill.objects.create(provider=pending_provider, service_item=self.service_item)
        ProviderCoverageCity.objects.create(provider=pending_provider, city=self.address.city)

        self.auth(self.customer_user)
        booking_response = self.client.post(
            "/api/v1/bookings",
            {
                "service_item_id": str(self.service_item.id),
                "customer_address_id": str(self.address.id),
                "requested_schedule": timezone.now().isoformat(),
                "description": "Verification dispatch test.",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="booking-key-verification",
        )
        booking_id = booking_response.data["data"]["id"]

        self.auth(self.admin_user)
        approved_lookup = self.client.get(f"/api/v1/admin/providers/approved?service_item_id={self.service_item.id}")
        self.assertFalse(any(item["id"] == str(pending_provider.id) for item in approved_lookup.data["data"]))

        pending_assign = self.client.post(
            "/api/v1/admin/dispatch/assign",
            {"booking_id": booking_id, "provider_id": str(pending_provider.id), "reason": "Try pending"},
            format="json",
        )
        self.assertEqual(pending_assign.status_code, 422)

        approve = self.client.post(
            f"/api/v1/admin/providers/{pending_provider.id}/verification",
            {"status": "approved", "reason": "Documents reviewed"},
            format="json",
        )
        self.assertEqual(approve.status_code, 200)
        self.assertEqual(approve.data["data"]["verification_status"], Provider.VerificationStatus.APPROVED)
        self.assertTrue(AuditLog.objects.filter(action="provider_verification_updated", entity_id=pending_provider.id).exists())

        approved_assign = self.client.post(
            "/api/v1/admin/dispatch/assign",
            {"booking_id": booking_id, "provider_id": str(pending_provider.id), "reason": "Approved provider"},
            format="json",
        )
        self.assertEqual(approved_assign.status_code, 200)

        suspend = self.client.post(
            f"/api/v1/admin/providers/{pending_provider.id}/verification",
            {"status": "suspended", "reason": "Compliance review"},
            format="json",
        )
        self.assertEqual(suspend.status_code, 200)

        self.auth(pending_user)
        accept = self.client.post(f"/api/v1/providers/jobs/{approved_assign.data['data']['id']}/accept")
        self.assertEqual(accept.status_code, 403)
        timeline = self.client.get(f"/api/v1/providers/{pending_provider.id}/timeline")
        self.assertEqual(timeline.status_code, 200)
        self.assertTrue(any(item["event_type"] == "provider_verification" for item in timeline.data["data"]))

    def test_signed_upload_limits_attachment_and_private_access(self):
        self.auth(self.customer_user)
        bad_type = self.client.post(
            "/api/v1/uploads/request",
            {
                "purpose": "complaint_evidence",
                "filename": "script.exe",
                "content_type": "application/x-msdownload",
                "size_bytes": 100,
            },
            format="json",
        )
        self.assertEqual(bad_type.status_code, 400)

        too_large = self.client.post(
            "/api/v1/uploads/request",
            {
                "purpose": "complaint_evidence",
                "filename": "large.pdf",
                "content_type": "application/pdf",
                "size_bytes": 99999999,
            },
            format="json",
        )
        self.assertEqual(too_large.status_code, 400)

        upload_response = self.client.post(
            "/api/v1/uploads/request",
            {
                "purpose": "complaint_evidence",
                "filename": "evidence.pdf",
                "content_type": "application/pdf",
                "size_bytes": 1200,
            },
            format="json",
        )
        self.assertEqual(upload_response.status_code, 201)
        upload_id = upload_response.data["data"]["upload"]["id"]
        self.assertIn("upload_url", upload_response.data["data"])

        self.auth(self.provider_user)
        wrong_owner_confirm = self.client.post("/api/v1/uploads/confirm", {"upload_id": upload_id}, format="json")
        self.assertEqual(wrong_owner_confirm.status_code, 403)

        self.auth(self.customer_user)
        confirm = self.client.post("/api/v1/uploads/confirm", {"upload_id": upload_id}, format="json")
        self.assertEqual(confirm.status_code, 200)
        self.assertEqual(confirm.data["data"]["status"], UploadedFile.Status.UPLOADED)

        booking_response = self.client.post(
            "/api/v1/bookings",
            {
                "service_item_id": str(self.service_item.id),
                "customer_address_id": str(self.address.id),
                "requested_schedule": timezone.now().isoformat(),
                "description": "Upload evidence test.",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="booking-key-upload-evidence",
        )
        booking_id = booking_response.data["data"]["id"]
        legacy_url = self.client.post(
            "/api/v1/complaints",
            {"booking_id": booking_id, "category": "quality", "description": "Bad URL.", "evidence_urls": ["https://example.test/file.pdf"]},
            format="json",
        )
        self.assertEqual(legacy_url.status_code, 400)
        complaint = self.client.post(
            "/api/v1/complaints",
            {
                "booking_id": booking_id,
                "category": "quality",
                "description": "Attached uploaded evidence.",
                "evidence_upload_ids": [upload_id],
            },
            format="json",
        )
        self.assertEqual(complaint.status_code, 201)
        upload = UploadedFile.objects.get(id=upload_id)
        self.assertEqual(upload.status, UploadedFile.Status.ATTACHED)
        self.assertEqual(upload.attached_entity_type, "complaint")

        self.auth(self.provider_user)
        forbidden = self.client.get(f"/api/v1/uploads/{upload_id}")
        self.assertEqual(forbidden.status_code, 403)

        self.auth(self.admin_user)
        allowed = self.client.get(f"/api/v1/uploads/{upload_id}")
        self.assertEqual(allowed.status_code, 200)

    def test_provider_completion_evidence_requires_confirmed_upload(self):
        self.auth(self.customer_user)
        booking_response = self.client.post(
            "/api/v1/bookings",
            {
                "service_item_id": str(self.service_item.id),
                "customer_address_id": str(self.address.id),
                "requested_schedule": timezone.now().isoformat(),
                "description": "Completion upload test.",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="booking-key-completion-upload",
        )
        booking_id = booking_response.data["data"]["id"]

        self.auth(self.admin_user)
        assign = self.client.post(
            "/api/v1/admin/dispatch/assign",
            {"booking_id": booking_id, "provider_id": str(self.provider.id), "reason": "Evidence test"},
            format="json",
        )
        assignment_id = assign.data["data"]["id"]

        self.auth(self.provider_user)
        upload_response = self.client.post(
            "/api/v1/uploads/request",
            {
                "purpose": "completion_evidence",
                "filename": "done.png",
                "content_type": "image/png",
                "size_bytes": 2400,
            },
            format="json",
        )
        upload_id = upload_response.data["data"]["upload"]["id"]
        self.client.post(f"/api/v1/providers/jobs/{assignment_id}/accept")
        unconfirmed = self.client.post(
            f"/api/v1/providers/jobs/{assignment_id}/complete",
            {"completion_notes": "Done", "evidence_upload_ids": [upload_id]},
            format="json",
        )
        self.assertEqual(unconfirmed.status_code, 400)
        self.client.post("/api/v1/uploads/confirm", {"upload_id": upload_id}, format="json")
        complete = self.client.post(
            f"/api/v1/providers/jobs/{assignment_id}/complete",
            {"completion_notes": "Done", "evidence_upload_ids": [upload_id]},
            format="json",
        )
        self.assertEqual(complete.status_code, 200)
        upload = UploadedFile.objects.get(id=upload_id)
        self.assertEqual(upload.status, UploadedFile.Status.ATTACHED)
        self.assertEqual(upload.attached_entity_type, "booking")
