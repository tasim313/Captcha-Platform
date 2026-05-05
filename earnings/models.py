"""
Earnings tracking models.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class DailyEarning(models.Model):
    """
    Aggregated daily earnings per account.
    """
    
    account = models.ForeignKey(
        'accounts.CaptchaAccount',
        on_delete=models.CASCADE,
        related_name='daily_earnings',
        verbose_name=_('Account')
    )
    date = models.DateField(
        verbose_name=_('Date'),
        db_index=True
    )
    
    # Solve Statistics
    total_solved = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Total Solved')
    )
    total_failed = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Total Failed')
    )
    by_captcha_type = models.JSONField(
        default=dict,
        verbose_name=_('Solves by CAPTCHA Type'),
        help_text=_('Dict of {captcha_type: count}')
    )
    
    # Financial
    earned_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.0000,
        verbose_name=_('Earned (USD)'),
        help_text=_('Estimated earnings based on solve count')
    )
    spent_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.0000,
        verbose_name=_('Spent (USD)'),
        help_text=_('Actual API costs')
    )
    profit_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0.0000,
        verbose_name=_('Profit (USD)')
    )
    
    # Performance
    average_solve_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Average Solve Time (ms)')
    )
    success_rate = models.FloatField(
        default=0.0,
        verbose_name=_('Success Rate (%)')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Metadata')
    )
    
    class Meta:
        verbose_name = _('Daily Earning')
        verbose_name_plural = _('Daily Earnings')
        ordering = ['-date']
        unique_together = [['account', 'date']]
        indexes = [
            models.Index(fields=['date']),
        ]
    
    def __str__(self) -> str:
        return f"{self.account.name} - {self.date}: ${self.earned_usd}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate profit
        self.profit_usd = self.earned_usd - self.spent_usd
        
        # Auto-calculate success rate
        total = self.total_solved + self.total_failed
        if total > 0:
            self.success_rate = (self.total_solved / total) * 100
        
        super().save(*args, **kwargs)


class EarningTransaction(models.Model):
    """
    Individual earning transaction from a solve.
    """
    
    class TransactionType(models.TextChoices):
        EARN = 'earn', _('Earning')
        SPEND = 'spend', _('Spending')
        REFUND = 'refund', _('Refund')
        BONUS = 'bonus', _('Bonus')
    
    uuid = models.UUIDField(
        unique=True,
        editable=False,
        verbose_name=_('UUID')
    )
    account = models.ForeignKey(
        'accounts.CaptchaAccount',
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name=_('Account')
    )
    job_execution = models.ForeignKey(
        'captcha_jobs.JobExecution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='earning_transactions',
        verbose_name=_('Job Execution')
    )
    
    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
        verbose_name=_('Transaction Type')
    )
    amount_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        verbose_name=_('Amount (USD)')
    )
    captcha_type = models.CharField(
        max_length=30,
        verbose_name=_('CAPTCHA Type')
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Description')
    )
    
    # Balance snapshot
    balance_before_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name=_('Balance Before (USD)')
    )
    balance_after_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name=_('Balance After (USD)')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Metadata')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    
    class Meta:
        verbose_name = _('Earning Transaction')
        verbose_name_plural = _('Earning Transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'created_at']),
            models.Index(fields=['transaction_type']),
        ]
    
    def __str__(self) -> str:
        return f"{self.account.name}: {self.get_transaction_type_display()} ${self.amount_usd}"
    
    def save(self, *args, **kwargs):
        if not self.uuid:
            import uuid
            self.uuid = uuid.uuid4()
        super().save(*args, **kwargs)


class BalanceSnapshot(models.Model):
    """
    Periodic balance snapshots for trend analysis.
    """
    
    account = models.ForeignKey(
        'accounts.CaptchaAccount',
        on_delete=models.CASCADE,
        related_name='balance_snapshots',
        verbose_name=_('Account')
    )
    balance_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name=_('Balance (USD)')
    )
    source = models.CharField(
        max_length=20,
        default='api',
        verbose_name=_('Source'),
        help_text=_('api = from API, calculated = from transactions')
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Metadata')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    
    class Meta:
        verbose_name = _('Balance Snapshot')
        verbose_name_plural = _('Balance Snapshots')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'created_at']),
        ]
    
    def __str__(self) -> str:
        return f"{self.account.name}: ${self.balance_usd} at {self.created_at}"