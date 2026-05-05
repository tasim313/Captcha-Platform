"""
Withdrawal tracking models.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class WithdrawalMethod(models.Model):
    """
    Supported withdrawal methods.
    """
    
    class MethodType(models.TextChoices):
        AIRTM = 'airtm', _('Airtm')
        BINANCE = 'binance', _('Binance')
        CRYPTO_WALLET = 'crypto_wallet', _('Crypto Wallet')
        BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
        PAYPAL = 'paypal', _('PayPal')
        OTHER = 'other', _('Other')
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Method Name')
    )
    method_type = models.CharField(
        max_length=20,
        choices=MethodType.choices,
        verbose_name=_('Method Type')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    min_withdrawal_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1.00,
        verbose_name=_('Minimum Withdrawal (USD)')
    )
    fee_percentage = models.FloatField(
        default=0.0,
        verbose_name=_('Fee Percentage'),
        help_text=_('Percentage fee charged by the method')
    )
    processing_time_hours = models.PositiveIntegerField(
        default=24,
        verbose_name=_('Processing Time (hours)')
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Configuration')
    )
    
    class Meta:
        verbose_name = _('Withdrawal Method')
        verbose_name_plural = _('Withdrawal Methods')
        ordering = ['name']
    
    def __str__(self) -> str:
        return self.name


class Withdrawal(models.Model):
    """
    Withdrawal request tracking.
    """
    
    class WithdrawalStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        CANCELLED = 'cancelled', _('Cancelled')
        REJECTED = 'rejected', _('Rejected')
    
    uuid = models.UUIDField(
        unique=True,
        editable=False,
        verbose_name=_('UUID')
    )
    account = models.ForeignKey(
        'accounts.CaptchaAccount',
        on_delete=models.CASCADE,
        related_name='withdrawals',
        verbose_name=_('Account')
    )
    method = models.ForeignKey(
        WithdrawalMethod,
        on_delete=models.PROTECT,
        related_name='withdrawals',
        verbose_name=_('Withdrawal Method')
    )
    
    # Amounts
    amount_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name=_('Amount (USD)')
    )
    fee_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.0000,
        verbose_name=_('Fee (USD)')
    )
    net_amount_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name=_('Net Amount (USD)')
    )
    
    # Destination
    destination_identifier = models.CharField(
        max_length=255,
        verbose_name=_('Destination Identifier'),
        help_text=_('e.g., email address, wallet address, account ID')
    )
    destination_identifier_encrypted = models.BinaryField(
        verbose_name=_('Destination Identifier (Encrypted)')
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=WithdrawalStatus.choices,
        default=WithdrawalStatus.PENDING,
        verbose_name=_('Status'),
        db_index=True
    )
    
    # External tracking
    external_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('External Transaction ID')
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        verbose_name=_('Internal Notes')
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name=_('Rejection Reason')
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
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Processed At')
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_withdrawals',
        verbose_name=_('Created By')
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_withdrawals',
        verbose_name=_('Processed By')
    )
    
    class Meta:
        verbose_name = _('Withdrawal')
        verbose_name_plural = _('Withdrawals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.account.name} - ${self.amount_usd} via {self.method.name}"
    
    def save(self, *args, **kwargs):
        if not self.uuid:
            import uuid
            self.uuid = uuid.uuid4()
        
        # Auto-calculate fee and net amount
        fee = self.amount_usd * (self.method.fee_percentage / 100)
        self.fee_usd = fee
        self.net_amount_usd = self.amount_usd - fee
        
        # Encrypt destination identifier
        if self.destination_identifier:
            from common.services.encryption import encrypt_value
            self.destination_identifier_encrypted = encrypt_value(self.destination_identifier).encode('utf-8')
        
        super().save(*args, **kwargs)
    
    def get_destination_identifier(self) -> str:
        """Decrypt and return the destination identifier."""
        if self.destination_identifier_encrypted:
            from common.services.encryption import decrypt_value
            return decrypt_value(self.destination_identifier_encrypted.tobytes().decode('utf-8'))
        return self.destination_identifier