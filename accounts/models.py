"""
Account models for managing CAPTCHA service credentials.
"""

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.services.encryption import encrypt_value, decrypt_value, mask_sensitive


class CaptchaServiceProvider(models.Model):
    """
    Supported CAPTCHA solving service providers.
    """
    
    class ServiceType(models.TextChoices):
        TWOCAPTCHA = 'twocaptcha', _('2Captcha')
        ANTICAPTCHA = 'anticaptcha', _('Anti-Captcha')
        DEATHBYCAPTCHA = 'deathbycaptcha', _('Death by Captcha')
        CAPMONSTER = 'capmonster', _('CapMonster')
        CUSTOM = 'custom', _('Custom')
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Service Name')
    )
    service_type = models.CharField(
        max_length=50,
        choices=ServiceType.choices,
        verbose_name=_('Service Type')
    )
    api_base_url = models.URLField(
        verbose_name=_('API Base URL'),
        help_text=_('Base URL for the service API')
    )
    documentation_url = models.URLField(
        blank=True,
        verbose_name=_('Documentation URL')
    )
    supported_captcha_types = models.JSONField(
        default=list,
        verbose_name=_('Supported CAPTCHA Types'),
        help_text=_('List of supported CAPTCHA type identifiers')
    )
    pricing_per_1000 = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0.00,
        verbose_name=_('Price per 1000 solves (USD)'),
        help_text=_('Approximate cost per 1000 CAPTCHA solves')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Metadata')
    )
    
    class Meta:
        verbose_name = _('CAPTCHA Service Provider')
        verbose_name_plural = _('CAPTCHA Service Providers')
        ordering = ['name']
    
    def __str__(self) -> str:
        return self.name


class CaptchaAccount(models.Model):
    """
    Account credentials for CAPTCHA solving services.
    
    Sensitive fields (api_key, password) are encrypted at rest.
    """
    
    class AccountStatus(models.TextChoices):
        ACTIVE = 'active', _('Active')
        INACTIVE = 'inactive', _('Inactive')
        SUSPENDED = 'suspended', _('Suspended')
        BANNED = 'banned', _('Banned')
        EXHAUSTED = 'exhausted', _('Balance Exhausted')
    
    # Identification
    uuid = models.UUIDField(
        unique=True,
        editable=False,
        verbose_name=_('UUID')
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Account Name'),
        help_text=_('Internal name for this account')
    )
    service_provider = models.ForeignKey(
        CaptchaServiceProvider,
        on_delete=models.PROTECT,
        related_name='accounts',
        verbose_name=_('Service Provider')
    )
    
    # Credentials (encrypted at rest)
    api_key_encrypted = models.BinaryField(
        verbose_name=_('API Key (Encrypted)')
    )
    email_encrypted = models.BinaryField(
        blank=True,
        null=True,
        verbose_name=_('Email (Encrypted)')
    )
    password_encrypted = models.BinaryField(
        blank=True,
        null=True,
        verbose_name=_('Password (Encrypted)')
    )
    
    # Status & Limits
    status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.INACTIVE,
        verbose_name=_('Status'),
        db_index=True
    )
    max_concurrent_tasks = models.PositiveIntegerField(
        default=5,
        verbose_name=_('Max Concurrent Tasks'),
        help_text=_('Maximum number of simultaneous solving tasks')
    )
    daily_limit = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Daily Solve Limit'),
        help_text=_('0 = unlimited')
    )
    
    # Balance Tracking (cached from API)
    balance_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.0000,
        verbose_name=_('Current Balance (USD)')
    )
    balance_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Balance Last Updated')
    )
    
    # Usage Statistics
    total_solved = models.PositiveBigIntegerField(
        default=0,
        verbose_name=_('Total CAPTCHAs Solved')
    )
    total_spent_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.0000,
        verbose_name=_('Total Spent (USD)')
    )
    total_failed = models.PositiveBigIntegerField(
        default=0,
        verbose_name=_('Total Failed Attempts')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Metadata')
    )
    
    # Audit
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_captcha_accounts',
        verbose_name=_('Created By')
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='modified_captcha_accounts',
        verbose_name=_('Last Modified By')
    )
    
    class Meta:
        verbose_name = _('CAPTCHA Account')
        verbose_name_plural = _('CAPTCHA Accounts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'service_provider']),
            models.Index(fields=['balance_usd']),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.service_provider.name})"
    
    def save(self, *args, **kwargs):
        # Generate UUID if not set
        if not self.uuid:
            import uuid
            self.uuid = uuid.uuid4()
        super().save(*args, **kwargs)
    
    # Encryption helpers
    def set_api_key(self, api_key: str) -> None:
        """Encrypt and set the API key."""
        self.api_key_encrypted = encrypt_value(api_key).encode('utf-8')
    
    def get_api_key(self) -> str:
        """Decrypt and return the API key."""
        return decrypt_value(self.api_key_encrypted.tobytes().decode('utf-8'))
    
    def set_email(self, email: str) -> None:
        """Encrypt and set the email."""
        self.email_encrypted = encrypt_value(email).encode('utf-8')
    
    def get_email(self) -> str:
        """Decrypt and return the email."""
        if self.email_encrypted:
            return decrypt_value(self.email_encrypted.tobytes().decode('utf-8'))
        return ''
    
    def set_password(self, password: str) -> None:
        """Encrypt and set the password."""
        self.password_encrypted = encrypt_value(password).encode('utf-8')
    
    def get_password(self) -> str:
        """Decrypt and return the password."""
        if self.password_encrypted:
            return decrypt_value(self.password_encrypted.tobytes().decode('utf-8'))
        return ''
    
    def get_masked_api_key(self) -> str:
        """Get masked API key for display."""
        return mask_sensitive(self.get_api_key())
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self.total_solved + self.total_failed
        if total == 0:
            return 0.0
        return (self.total_solved / total) * 100
    
    @property
    def is_usable(self) -> bool:
        """Check if account can be used for solving."""
        return (
            self.status == self.AccountStatus.ACTIVE and
            self.balance_usd > 0
        )


class AccountAuditLog(models.Model):
    """
    Audit log for account credential changes.
    """
    
    class Action(models.TextChoices):
        CREATED = 'created', _('Account Created')
        API_KEY_CHANGED = 'api_key_changed', _('API Key Changed')
        PASSWORD_CHANGED = 'password_changed', _('Password Changed')
        STATUS_CHANGED = 'status_changed', _('Status Changed')
        BALANCE_UPDATED = 'balance_updated', _('Balance Updated')
        DEACTIVATED = 'deactivated', _('Account Deactivated')
        REACTIVATED = 'reactivated', _('Account Reactivated')
    
    account = models.ForeignKey(
        CaptchaAccount,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name=_('Account')
    )
    action = models.CharField(
        max_length=30,
        choices=Action.choices,
        verbose_name=_('Action')
    )
    old_value = models.TextField(
        blank=True,
        verbose_name=_('Old Value (Masked)')
    )
    new_value = models.TextField(
        blank=True,
        verbose_name=_('New Value (Masked)')
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address')
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User Agent')
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('Performed By')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Context')
    )
    
    class Meta:
        verbose_name = _('Account Audit Log')
        verbose_name_plural = _('Account Audit Logs')
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.account.name} - {self.get_action_display()} - {self.created_at}"
    

"""
Models for CAPTCHA service account management
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.mixins import TimestampMixin, AuditMixin
from core.encryption import encryption_service


class CaptchaService(models.TextChoices):
    """Supported CAPTCHA solving services"""
    TWOCAPTCHA = '2captcha', _('2Captcha')
    ANTICAPTCHA = 'anticaptcha', _('Anti-Captcha')
    DECAPTCHER = 'decaptcher', _('DeCaptcher')
    MANUAL = 'manual', _('Manual')


class AccountStatus(models.TextChoices):
    """Account status options"""
    ACTIVE = 'active', _('Active')
    INACTIVE = 'inactive', _('Inactive')
    SUSPENDED = 'suspended', _('Suspended')
    BANNED = 'banned', _('Banned')
    ERROR = 'error', _('Error')


class CaptchaAccount(TimestampMixin, AuditMixin):
    """
    Model representing a CAPTCHA solving service account
    Stores encrypted credentials for security
    """
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Account Name'),
        help_text=_('Friendly name to identify this account')
    )
    
    service = models.CharField(
        max_length=20,
        choices=CaptchaService.choices,
        default=CaptchaService.TWOCAPTCHA,
        verbose_name=_('Service'),
        help_text=_('CAPTCHA solving service provider')
    )
    
    api_key_encrypted = models.TextField(
        verbose_name=_('API Key (Encrypted)'),
        blank=True,
        help_text=_('API key stored with encryption')
    )
    
    email_encrypted = models.TextField(
        verbose_name=_('Email (Encrypted)'),
        blank=True,
        help_text=_('Account email stored with encryption')
    )
    
    password_encrypted = models.TextField(
        verbose_name=_('Password (Encrypted)'),
        blank=True,
        help_text=_('Account password stored with encryption')
    )
    
    status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
        verbose_name=_('Status'),
        db_index=True
    )
    
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_('Balance (USD)'),
        help_text=_('Current account balance in USD')
    )
    
    balance_last_checked = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Balance Last Checked')
    )
    
    total_spent = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_('Total Spent (USD)')
    )
    
    total_solved = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Total CAPTCHAs Solved')
    )
    
    success_rate = models.FloatField(
        default=0.0,
        verbose_name=_('Success Rate (%)'),
        help_text=_('Percentage of successfully solved CAPTCHAs')
    )
    
    rate_limit_per_minute = models.PositiveIntegerField(
        default=10,
        verbose_name=_('Rate Limit (req/min)'),
        help_text=_('Maximum requests per minute to avoid API limits')
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes about this account')
    )
    
    is_default = models.BooleanField(
        default=False,
        verbose_name=_('Default Account'),
        help_text=_('Use this account as default when none specified')
    )
    
    class Meta:
        verbose_name = _('CAPTCHA Account')
        verbose_name_plural = _('CAPTCHA Accounts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_default']),
            models.Index(fields=['service', 'status']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_service_display()})"
    
    # Encryption property accessors
    @property
    def api_key(self) -> str:
        """Get decrypted API key"""
        return encryption_service.decrypt(self.api_key_encrypted)
    
    @api_key.setter
    def api_key(self, value: str):
        """Set and encrypt API key"""
        self.api_key_encrypted = encryption_service.encrypt(value)
    
    @property
    def email(self) -> str:
        """Get decrypted email"""
        return encryption_service.decrypt(self.email_encrypted)
    
    @email.setter
    def email(self, value: str):
        """Set and encrypt email"""
        self.email_encrypted = encryption_service.encrypt(value)
    
    @property
    def password(self) -> str:
        """Get decrypted password"""
        return encryption_service.decrypt(self.password_encrypted)
    
    @password.setter
    def password(self, value: str):
        """Set and encrypt password"""
        self.password_encrypted = encryption_service.encrypt(value)
    
    @property
    def masked_api_key(self) -> str:
        """Get masked API key for display"""
        key = self.api_key
        if len(key) > 8:
            return key[:4] + '*' * 24 + key[-4:]
        return '****'
    
    def is_available(self) -> bool:
        """Check if account is available for use"""
        return self.status == AccountStatus.ACTIVE and self.balance > 0
    
    def update_balance(self, new_balance: float):
        """Update account balance and timestamp"""
        old_balance = self.balance
        self.balance = new_balance
        self.balance_last_checked = models.DateTimeField.auto_now
        if new_balance < old_balance:
            self.total_spent += (old_balance - new_balance)
        self.save(update_fields=['balance', 'balance_last_checked', 'total_spent'])
    
    def increment_solved_count(self, success: bool = True):
        """Increment solved count and update success rate"""
        self.total_solved += 1
        if success:
            # Simple moving average for success rate
            self.success_rate = (self.success_rate * (self.total_solved - 1) + 100) / self.total_solved
        else:
            self.success_rate = (self.success_rate * (self.total_solved - 1)) / self.total_solved
        self.save(update_fields=['total_solved', 'success_rate'])


class AccountAuditLog(TimestampMixin):
    """
    Audit log for account credential changes
    Tracks who changed what and when
    """
    
    account = models.ForeignKey(
        CaptchaAccount,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name=_('Account')
    )
    
    action = models.CharField(
        max_length=50,
        verbose_name=_('Action'),
        choices=[
            ('created', _('Created')),
            ('updated', _('Updated')),
            ('api_key_changed', _('API Key Changed')),
            ('password_changed', _('Password Changed')),
            ('status_changed', _('Status Changed')),
            ('deleted', _('Deleted')),
            ('balance_checked', _('Balance Checked')),
        ]
    )
    
    old_values = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Old Values'),
        help_text=_('Previous values (sensitive data masked)')
    )
    
    new_values = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('New Values'),
        help_text=_('New values (sensitive data masked)')
    )
    
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Changed By')
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address')
    )
    
    details = models.TextField(
        blank=True,
        verbose_name=_('Details')
    )
    
    class Meta:
        verbose_name = _('Account Audit Log')
        verbose_name_plural = _('Account Audit Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'action']),
            models.Index(fields=['changed_by']),
        ]
    
    def __str__(self):
        return f"{self.account.name} - {self.get_action_display()} - {self.created_at}"