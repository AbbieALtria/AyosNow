from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def database_from_url(url):
    parsed = urlparse(url)
    if parsed.scheme == "sqlite":
        db_path = unquote(parsed.path.lstrip("/")) or "db.sqlite3"
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / db_path if not os.path.isabs(db_path) else db_path,
        }
    if parsed.scheme in {"postgres", "postgresql"}:
        query = parse_qs(parsed.query)
        config = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
        }
        sslmode = query.get("sslmode", [""])[0]
        if sslmode:
            config["OPTIONS"] = {"sslmode": sslmode}
        return config
    raise ValueError("DATABASE_URL must use sqlite://, postgres://, or postgresql://")


DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
RAILWAY_HEALTHCHECK_HOST = os.getenv("RAILWAY_HEALTHCHECK_HOST", "healthcheck.railway.app")
if RAILWAY_HEALTHCHECK_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RAILWAY_HEALTHCHECK_HOST)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "core",
    "accounts",
    "geo",
    "customers",
    "providers",
    "services",
    "bookings",
    "finance",
    "complaints",
    "audit",
    "api",
    "customer_portal",
    "provider_portal",
    "ops_portal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ayosnow.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ayosnow.wsgi.application"
ASGI_APPLICATION = "ayosnow.asgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")
DATABASES = {"default": database_from_url(DATABASE_URL)}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = os.getenv("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles")
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SECURE_REDIRECT_EXEMPT = [r"^healthz$", r"^readyz$"]
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", False)
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

AYOSNOW_DEFAULT_CURRENCY = os.getenv("AYOSNOW_DEFAULT_CURRENCY", "PHP")
AYOSNOW_COMMISSION_RATE = float(os.getenv("AYOSNOW_COMMISSION_RATE", "0.20"))
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "dev-webhook-secret")
AYOSNOW_PAYMENT_GATEWAY_BACKEND = os.getenv("AYOSNOW_PAYMENT_GATEWAY_BACKEND", "finance.gateways.DevelopmentPaymentGateway")
PAYMENT_GATEWAY_TIMEOUT_SECONDS = int(os.getenv("PAYMENT_GATEWAY_TIMEOUT_SECONDS", "15"))
PAYMONGO_SECRET_KEY = os.getenv("PAYMONGO_SECRET_KEY", "")
PAYMONGO_WEBHOOK_SECRET = os.getenv("PAYMONGO_WEBHOOK_SECRET", "")
PAYMONGO_CHECKOUT_URL = os.getenv("PAYMONGO_CHECKOUT_URL", "https://api.paymongo.com/v1/checkout_sessions")
PAYMONGO_SUCCESS_URL = os.getenv("PAYMONGO_SUCCESS_URL", "http://127.0.0.1:8000/app/")
PAYMONGO_CANCEL_URL = os.getenv("PAYMONGO_CANCEL_URL", "http://127.0.0.1:8000/app/")
AYOSNOW_SMS_BACKEND = os.getenv("AYOSNOW_SMS_BACKEND", "accounts.sms.ConsoleSmsBackend")
SMS_TIMEOUT_SECONDS = int(os.getenv("SMS_TIMEOUT_SECONDS", "15"))
SEMAPHORE_API_KEY = os.getenv("SEMAPHORE_API_KEY", "")
SEMAPHORE_SENDER_NAME = os.getenv("SEMAPHORE_SENDER_NAME", "")
SEMAPHORE_MESSAGES_URL = os.getenv("SEMAPHORE_MESSAGES_URL", "https://api.semaphore.co/api/v4/messages")
SEMAPHORE_OTP_TEMPLATE = os.getenv("SEMAPHORE_OTP_TEMPLATE", "Your AyosNow OTP is {code}. It expires soon.")
AYOSNOW_OTP_EXPIRY_SECONDS = int(os.getenv("AYOSNOW_OTP_EXPIRY_SECONDS", "600"))
AYOSNOW_OTP_MAX_ATTEMPTS = int(os.getenv("AYOSNOW_OTP_MAX_ATTEMPTS", "5"))
AYOSNOW_OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("AYOSNOW_OTP_RESEND_COOLDOWN_SECONDS", "60"))
AYOSNOW_UPLOAD_MAX_BYTES = int(os.getenv("AYOSNOW_UPLOAD_MAX_BYTES", "5242880"))
AYOSNOW_UPLOAD_URL_TTL_SECONDS = int(os.getenv("AYOSNOW_UPLOAD_URL_TTL_SECONDS", "900"))
AYOSNOW_UPLOAD_ALLOWED_TYPES = env_list("AYOSNOW_UPLOAD_ALLOWED_TYPES", "image/jpeg,image/png,application/pdf")
