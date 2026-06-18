from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Validate that production deployment settings are not using development defaults."

    def handle(self, *args, **options):
        errors = []
        warnings = []

        if settings.DEBUG:
            warnings.append("DJANGO_DEBUG is true. This is acceptable for local development only.")
        else:
            self._require_production_settings(errors, warnings)

        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))

        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(f"ERROR: {error}"))
            raise CommandError("Deployment environment validation failed.")

        self.stdout.write(self.style.SUCCESS("Deployment environment validation passed."))

    def _require_production_settings(self, errors, warnings):
        secret = settings.SECRET_KEY or ""
        if secret == "dev-only-change-me" or len(secret) < 50:
            errors.append("DJANGO_SECRET_KEY must be unique and at least 50 characters when DJANGO_DEBUG=false.")

        allowed_hosts = set(settings.ALLOWED_HOSTS)
        if not allowed_hosts or "*" in allowed_hosts:
            errors.append("DJANGO_ALLOWED_HOSTS must list explicit production hostnames.")

        database_engine = settings.DATABASES["default"]["ENGINE"]
        if database_engine == "django.db.backends.sqlite3":
            errors.append("DATABASE_URL must point to PostgreSQL for production.")

        if settings.PAYMENT_WEBHOOK_SECRET in {"", "change-me", "dev-webhook-secret"}:
            errors.append("PAYMENT_WEBHOOK_SECRET must be changed from the development default.")
        elif len(settings.PAYMENT_WEBHOOK_SECRET) < 32:
            errors.append("PAYMENT_WEBHOOK_SECRET must be at least 32 characters.")

        if settings.AYOSNOW_PAYMENT_GATEWAY_BACKEND.endswith("DevelopmentPaymentGateway"):
            errors.append("AYOSNOW_PAYMENT_GATEWAY_BACKEND must use a real payment gateway adapter.")
        if settings.AYOSNOW_PAYMENT_GATEWAY_BACKEND.endswith("PayMongoPaymentGateway"):
            if not settings.PAYMONGO_SECRET_KEY:
                errors.append("PAYMONGO_SECRET_KEY is required when using PayMongoPaymentGateway.")
            if not settings.PAYMONGO_WEBHOOK_SECRET:
                errors.append("PAYMONGO_WEBHOOK_SECRET is required when using PayMongoPaymentGateway.")
            if "127.0.0.1" in settings.PAYMONGO_SUCCESS_URL or "localhost" in settings.PAYMONGO_SUCCESS_URL:
                errors.append("PAYMONGO_SUCCESS_URL must point to the production customer portal.")
            if "127.0.0.1" in settings.PAYMONGO_CANCEL_URL or "localhost" in settings.PAYMONGO_CANCEL_URL:
                errors.append("PAYMONGO_CANCEL_URL must point to the production customer portal.")

        if settings.AYOSNOW_SMS_BACKEND.endswith("ConsoleSmsBackend"):
            errors.append("AYOSNOW_SMS_BACKEND must use a real SMS backend.")
        if settings.AYOSNOW_SMS_BACKEND.endswith("SemaphoreSmsBackend") and not settings.SEMAPHORE_API_KEY:
            errors.append("SEMAPHORE_API_KEY is required when using SemaphoreSmsBackend.")

        if not settings.CSRF_TRUSTED_ORIGINS:
            warnings.append("DJANGO_CSRF_TRUSTED_ORIGINS is empty; admin/session POSTs may fail behind HTTPS domains.")

        if not settings.SECURE_SSL_REDIRECT:
            errors.append("DJANGO_SECURE_SSL_REDIRECT must be true.")

        if not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
            errors.append("DJANGO_SESSION_COOKIE_SECURE and DJANGO_CSRF_COOKIE_SECURE must be true.")

        if settings.SECURE_HSTS_SECONDS < 31536000:
            warnings.append("DJANGO_SECURE_HSTS_SECONDS is below one year.")

        if settings.AYOSNOW_UPLOAD_MAX_BYTES <= 0:
            errors.append("AYOSNOW_UPLOAD_MAX_BYTES must be greater than zero.")

        if not settings.AYOSNOW_UPLOAD_ALLOWED_TYPES:
            errors.append("AYOSNOW_UPLOAD_ALLOWED_TYPES must contain at least one MIME type.")
