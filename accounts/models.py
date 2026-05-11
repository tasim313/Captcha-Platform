import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.services.encryption import decrypt_value, encrypt_value, mask_sensitive


class CaptchaServiceProvider(models.Model):
    class ServiceType(models.TextChoices):
        TWOCAPTCHA = "twocaptcha", _("2Captcha")
        ANTICAPTCHA = "anticaptcha", _("Anti-Captcha")
        CAPMONSTER = "capmonster", _("CapMonster")
        CUSTOM = "custom", _("Custom")

    name = models.CharField(max_length=100, unique=True)
    service_type = models.CharField(max_length=32, choices=ServiceType.choices)
    api_base_url = models.URLField()
    documentation_url = models.URLField(blank=True)
    supported_captcha_types = models.JSONField(default=list, blank=True)
    pricing_per_1000 = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CaptchaAccount(models.Model):
    class AccountStatus(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")
        SUSPENDED = "suspended", _("Suspended")
        BANNED = "banned", _("Banned")
        EXHAUSTED = "exhausted", _("Balance Exhausted")

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    service_provider = models.ForeignKey(
        CaptchaServiceProvider,
        on_delete=models.PROTECT,
        related_name="accounts",
    )
    api_key_encrypted = models.BinaryField()
    email_encrypted = models.BinaryField(blank=True, null=True)
    password_encrypted = models.BinaryField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.INACTIVE,
        db_index=True,
    )
    max_concurrent_tasks = models.PositiveIntegerField(default=5)
    daily_limit = models.PositiveIntegerField(default=0)
    balance_usd = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    balance_updated_at = models.DateTimeField(blank=True, null=True)
    total_solved = models.PositiveBigIntegerField(default=0)
    total_failed = models.PositiveBigIntegerField(default=0)
    total_spent_usd = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_captcha_accounts",
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="modified_captcha_accounts",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.service_provider.name})"

    def set_api_key(self, api_key):
        self.api_key_encrypted = encrypt_value(api_key).encode("utf-8")

    def get_api_key(self):
        return decrypt_value(self.api_key_encrypted.tobytes().decode("utf-8"))

    def set_email(self, email):
        self.email_encrypted = encrypt_value(email).encode("utf-8")

    def get_email(self):
        if not self.email_encrypted:
            return ""
        return decrypt_value(self.email_encrypted.tobytes().decode("utf-8"))

    def set_password(self, password):
        self.password_encrypted = encrypt_value(password).encode("utf-8")

    def get_password(self):
        if not self.password_encrypted:
            return ""
        return decrypt_value(self.password_encrypted.tobytes().decode("utf-8"))

    def get_masked_api_key(self):
        return mask_sensitive(self.get_api_key())

    @property
    def success_rate(self):
        total = self.total_solved + self.total_failed
        if total == 0:
            return 0.0
        return round((self.total_solved / total) * 100, 2)

    @property
    def is_usable(self):
        return self.status == self.AccountStatus.ACTIVE and self.balance_usd > 0


class AccountAuditLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", _("Created")
        UPDATED = "updated", _("Updated")
        API_KEY_CHANGED = "api_key_changed", _("API Key Changed")
        PASSWORD_CHANGED = "password_changed", _("Password Changed")
        STATUS_CHANGED = "status_changed", _("Status Changed")
        BALANCE_UPDATED = "balance_updated", _("Balance Updated")

    account = models.ForeignKey(
        CaptchaAccount,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account.name} {self.action}"
