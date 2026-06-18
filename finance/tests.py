from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from django.test import SimpleTestCase, override_settings

from finance.gateways import PayMongoPaymentGateway, basic_auth_header, decimal_to_centavos, sign_payload


class PayMongoGatewayTests(SimpleTestCase):
    def test_decimal_to_centavos(self):
        self.assertEqual(decimal_to_centavos(Decimal("499.99")), 49999)

    @override_settings(
        PAYMONGO_SECRET_KEY="sk_test_123",
        PAYMONGO_CHECKOUT_URL="https://api.paymongo.com/v1/checkout_sessions",
        PAYMONGO_SUCCESS_URL="https://ayosnow.example/app/",
        PAYMONGO_CANCEL_URL="https://ayosnow.example/app/",
        PAYMENT_GATEWAY_TIMEOUT_SECONDS=7,
    )
    @patch("finance.gateways.post_json")
    def test_paymongo_checkout_uses_basic_auth_and_metadata(self, post_json):
        post_json.return_value = {
            "data": {
                "id": "cs_test_123",
                "attributes": {"checkout_url": "https://checkout.paymongo.com/cs_test_123"},
            }
        }
        payment = SimpleNamespace(
            id="payment-123",
            booking_id="booking-123",
            amount=Decimal("500.00"),
            currency="PHP",
        )

        result = PayMongoPaymentGateway().create_checkout(
            payment=payment,
            payment_method="gcash",
            idempotency_key="idem-001",
        )

        self.assertEqual(result["gateway"], "paymongo")
        self.assertEqual(result["gateway_reference"], "cs_test_123")
        self.assertEqual(result["checkout_url"], "https://checkout.paymongo.com/cs_test_123")
        _url, payload = post_json.call_args.args
        headers = post_json.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], basic_auth_header("sk_test_123", ""))
        self.assertEqual(headers["Idempotency-Key"], "idem-001")
        attrs = payload["data"]["attributes"]
        self.assertEqual(attrs["payment_method_types"], ["gcash"])
        self.assertEqual(attrs["line_items"][0]["amount"], 50000)
        self.assertEqual(attrs["metadata"]["payment_id"], "payment-123")

    @override_settings(PAYMONGO_SECRET_KEY="")
    def test_paymongo_checkout_requires_secret_key(self):
        payment = SimpleNamespace(id="payment-123", booking_id="booking-123", amount=Decimal("1.00"), currency="PHP")

        with self.assertRaises(ImproperlyConfigured):
            PayMongoPaymentGateway().create_checkout(payment=payment, payment_method="gcash", idempotency_key="idem-001")

    @override_settings(PAYMONGO_WEBHOOK_SECRET="webhook-secret", PAYMENT_WEBHOOK_SECRET="fallback-secret")
    def test_paymongo_webhook_signature_uses_paymongo_secret(self):
        payload = b'{"event":"ok"}'
        signature = sign_payload(payload, "webhook-secret")

        self.assertTrue(PayMongoPaymentGateway().verify_webhook_signature(payload=payload, signature=signature))

    @override_settings(PAYMONGO_WEBHOOK_SECRET="webhook-secret", PAYMENT_WEBHOOK_SECRET="fallback-secret")
    def test_paymongo_webhook_signature_rejects_bad_signature(self):
        with self.assertRaises(SuspiciousOperation):
            PayMongoPaymentGateway().verify_webhook_signature(payload=b"{}", signature="sha256=bad")
