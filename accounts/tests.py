from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from accounts.sms import SemaphoreSmsBackend


class SemaphoreSmsBackendTests(SimpleTestCase):
    @override_settings(
        SEMAPHORE_API_KEY="sem-key",
        SEMAPHORE_SENDER_NAME="AyosNow",
        SEMAPHORE_MESSAGES_URL="https://api.semaphore.co/api/v4/messages",
        SEMAPHORE_OTP_TEMPLATE="Your AyosNow OTP is {code}.",
        SMS_TIMEOUT_SECONDS=6,
    )
    @patch("accounts.sms.post_form")
    def test_semaphore_sends_otp_with_api_key_and_sender(self, post_form):
        post_form.return_value = [{"message_id": "msg-123"}]

        result = SemaphoreSmsBackend().send_otp(mobile="+639170000100", code="123456", purpose="login")

        self.assertEqual(result, {"provider": "semaphore", "message_id": "msg-123"})
        url, payload = post_form.call_args.args
        self.assertEqual(url, "https://api.semaphore.co/api/v4/messages")
        self.assertEqual(payload["apikey"], "sem-key")
        self.assertEqual(payload["number"], "+639170000100")
        self.assertEqual(payload["message"], "Your AyosNow OTP is 123456.")
        self.assertEqual(payload["sendername"], "AyosNow")
        self.assertEqual(post_form.call_args.kwargs["timeout"], 6)

    @override_settings(SEMAPHORE_API_KEY="")
    def test_semaphore_requires_api_key(self):
        with self.assertRaises(ImproperlyConfigured):
            SemaphoreSmsBackend().send_otp(mobile="+639170000100", code="123456", purpose="login")
