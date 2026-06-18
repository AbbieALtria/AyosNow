import uuid

from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    def _create_user(self, username, email, password, **extra_fields):
        email = email or None
        return super()._create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    class UserType(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        PROVIDER = "provider", "Provider"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    user_type = models.CharField(max_length=30, choices=UserType.choices)
    mobile = models.CharField(max_length=30, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    mobile_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    class Meta:
        db_table = "auth_user"

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.mobile or self.email or str(self.id)
        super().save(*args, **kwargs)


class OtpChallenge(models.Model):
    class Purpose(models.TextChoices):
        REGISTER = "register", "Register"
        LOGIN = "login", "Login"
        PASSWORD_RESET = "password_reset", "Password reset"
        PAYOUT = "payout", "Payout"
        PROFILE_CHANGE = "profile_change", "Profile change"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name="otp_challenges")
    mobile = models.CharField(max_length=30)
    purpose = models.CharField(max_length=40, choices=Purpose.choices)
    otp_hash = models.TextField()
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auth_otp"
        indexes = [models.Index(fields=["mobile", "purpose", "-created_at"])]
