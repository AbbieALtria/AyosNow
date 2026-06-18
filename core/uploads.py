import hashlib
import hmac
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone


def sign_upload_key(storage_key, expires_at):
    message = f"{storage_key}:{int(expires_at.timestamp())}".encode("utf-8")
    digest = hmac.new(settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def build_upload_url(upload):
    params = urlencode(
        {
            "key": upload.storage_key,
            "expires": int(upload.upload_expires_at.timestamp()),
            "signature": sign_upload_key(upload.storage_key, upload.upload_expires_at),
        }
    )
    return f"https://uploads.example.test/ayosnow/dev-put?{params}"


def build_public_url(storage_key):
    return f"https://uploads.example.test/ayosnow/private/{storage_key}"


def upload_is_expired(upload):
    return upload.upload_expires_at < timezone.now()
