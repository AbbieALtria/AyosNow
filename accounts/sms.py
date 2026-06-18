import logging
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class SmsBackend:
    def send_otp(self, *, mobile, code, purpose):
        raise NotImplementedError


class ConsoleSmsBackend(SmsBackend):
    def send_otp(self, *, mobile, code, purpose):
        logger.info("AyosNow OTP for %s (%s): %s", mobile, purpose, code)
        print(f"AyosNow OTP for {mobile} ({purpose}): {code}")
        return {"provider": "console", "message_id": None}


class TwilioSmsBackend(SmsBackend):
    def send_otp(self, *, mobile, code, purpose):
        raise NotImplementedError("Configure Twilio credentials before enabling this backend.")


class SemaphoreSmsBackend(SmsBackend):
    def send_otp(self, *, mobile, code, purpose):
        if not settings.SEMAPHORE_API_KEY:
            raise ImproperlyConfigured("SEMAPHORE_API_KEY is required for Semaphore SMS.")
        message = settings.SEMAPHORE_OTP_TEMPLATE.format(code=code, purpose=purpose)
        payload = {
            "apikey": settings.SEMAPHORE_API_KEY,
            "number": mobile,
            "message": message,
        }
        if settings.SEMAPHORE_SENDER_NAME:
            payload["sendername"] = settings.SEMAPHORE_SENDER_NAME
        response = post_form(settings.SEMAPHORE_MESSAGES_URL, payload, timeout=settings.SMS_TIMEOUT_SECONDS)
        message_id = None
        if isinstance(response, list) and response:
            message_id = response[0].get("message_id") or response[0].get("id")
        elif isinstance(response, dict):
            message_id = response.get("message_id") or response.get("id")
        return {"provider": "semaphore", "message_id": message_id}


def post_form(url, payload, *, timeout=10):
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            import json

            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except Exception as exc:
        raise SuspiciousOperation(f"SMS provider request failed: {exc}") from exc


def get_sms_backend(path):
    backend_class = import_string(path)
    return backend_class()
