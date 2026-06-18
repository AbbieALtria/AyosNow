import hashlib
import hmac
import json
import base64
import urllib.request
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import SuspiciousOperation
from django.utils.module_loading import import_string


class PaymentGateway:
    gateway_name = "base"

    def create_checkout(self, *, payment, payment_method, idempotency_key):
        raise NotImplementedError

    def verify_webhook_signature(self, *, payload, signature):
        raise NotImplementedError


class DevelopmentPaymentGateway(PaymentGateway):
    gateway_name = "dev_gateway"

    def create_checkout(self, *, payment, payment_method, idempotency_key):
        reference = f"DEV-{idempotency_key[:24]}"
        return {
            "gateway": self.gateway_name,
            "gateway_reference": reference,
            "checkout_url": f"https://payments.example.test/checkout/{reference}?method={payment_method}",
        }

    def verify_webhook_signature(self, *, payload, signature):
        expected = sign_payload(payload, settings.PAYMENT_WEBHOOK_SECRET)
        if not hmac.compare_digest(signature or "", expected):
            raise SuspiciousOperation("Invalid payment webhook signature.")
        return True


class PayMongoPaymentGateway(DevelopmentPaymentGateway):
    gateway_name = "paymongo"

    def create_checkout(self, *, payment, payment_method, idempotency_key):
        secret_key = getattr(settings, "PAYMONGO_SECRET_KEY", "")
        if not secret_key:
            raise ImproperlyConfigured("PAYMONGO_SECRET_KEY is required for PayMongo checkout.")

        payload = {
            "data": {
                "attributes": {
                    "send_email_receipt": False,
                    "show_description": True,
                    "show_line_items": True,
                    "cancel_url": settings.PAYMONGO_CANCEL_URL,
                    "success_url": settings.PAYMONGO_SUCCESS_URL,
                    "payment_method_types": [payment_method],
                    "line_items": [
                        {
                            "currency": payment.currency,
                            "amount": decimal_to_centavos(payment.amount),
                            "name": f"AyosNow booking {payment.booking_id}",
                            "quantity": 1,
                        }
                    ],
                    "metadata": {
                        "payment_id": str(payment.id),
                        "booking_id": str(payment.booking_id),
                        "idempotency_key": idempotency_key,
                    },
                }
            }
        }
        response = post_json(
            settings.PAYMONGO_CHECKOUT_URL,
            payload,
            headers={
                "Authorization": basic_auth_header(secret_key, ""),
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            timeout=settings.PAYMENT_GATEWAY_TIMEOUT_SECONDS,
        )
        data = response.get("data", {})
        attributes = data.get("attributes", {})
        checkout_url = attributes.get("checkout_url")
        reference = data.get("id")
        if not checkout_url or not reference:
            raise SuspiciousOperation("PayMongo checkout response is missing checkout_url or id.")
        return {
            "gateway": self.gateway_name,
            "gateway_reference": reference,
            "checkout_url": checkout_url,
        }

    def verify_webhook_signature(self, *, payload, signature):
        secret = settings.PAYMONGO_WEBHOOK_SECRET or settings.PAYMENT_WEBHOOK_SECRET
        expected = sign_payload(payload, secret)
        if not hmac.compare_digest(signature or "", expected):
            raise SuspiciousOperation("Invalid PayMongo webhook signature.")
        return True


class XenditPaymentGateway(DevelopmentPaymentGateway):
    gateway_name = "xendit"


def canonical_payload(data):
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sign_payload(payload, secret):
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def basic_auth_header(username, password):
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def decimal_to_centavos(amount):
    return int((Decimal(amount) * Decimal("100")).quantize(Decimal("1")))


def post_json(url, payload, *, headers=None, timeout=10):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers or {},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except Exception as exc:
        raise SuspiciousOperation(f"Payment gateway request failed: {exc}") from exc


def get_payment_gateway(path=None):
    gateway_class = import_string(path or settings.AYOSNOW_PAYMENT_GATEWAY_BACKEND)
    return gateway_class()
