"""
Structured logging models for the platform.
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class LogEntry(models.Model):
    """
    Structured log entries for the platform.
    """
    
    class LogLevel(models.TextChoices):
        DEBUG = 'DEBUG', _('Debug')
        INFO = 'INFO', _('Info')
        WARNING = 'WARNING', _('Warning')
        ERROR = 'ERROR', _('Error')
        CRITICAL = 'CRITICAL', _('Critical')
    
    class LogSource(models.TextChoices):
        SYSTEM = 'system', _('System')
        JOB = 'job', _('Job')
        SOLVER = 'solver', _('Solver')
        BROWSER = 'browser', _('Browser')
        API = 'api', _('API')
        ACCOUNT = 'account', _('Account')
    
    # Identification
    uuid = models.UUIDField(
        unique=True,
        editable=False,
        verbose_name=_('UUID')
    )
    
    # Context
    source = models.CharField(
        max_length=20,
        choices=LogSource.choices,
        verbose_name=_('Source'),
        db_index=True
    )
    level = models.CharField(
        max_length=10,
        choices=LogLevel.choices,
        default=LogLevel.INFO,
        verbose_name=_('Level'),
        db_index=True
    )
    
    # References
    job = models.ForeignKey(
        'captcha_jobs.CaptchaJob',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='log_entries',
        verbose_name=_('Job')
    )
    job_execution = models.ForeignKey(
        'captcha_jobs.JobExecution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='log_entries',
        verbose_name=_('Job Execution')
    )
    account = models.ForeignKey(
        'accounts.CaptchaAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='log_entries',
        verbose_name=_('Account')
    )
    
    # Content
    message = models.TextField(
        verbose_name=_('Message')
    )
    exception_type = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Exception Type')
    )
    exception_message = models.TextField(
        blank=True,
        verbose_name=_('Exception Message')
    )
    stack_trace = models.TextField(
        blank=True,
        verbose_name=_('Stack Trace')
    )
    
    # Additional Data
    request_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Request Data')
    )
    response_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Response Data')
    )
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Extra Data')
    )
    
    # Runtime Context
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Celery Task ID')
    )
    worker_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Worker Name')
    )
    process_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Process ID')
    )
    thread_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Thread Name')
    )
    
    # Request Context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address')
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User Agent')
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('User')
    )
    
    # Timing
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
        db_index=True
    )
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Duration (ms)')
    )
    
    class Meta:
        verbose_name = _('Log Entry')
        verbose_name_plural = _('Log Entries')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', 'level']),
            models.Index(fields=['job', 'created_at']),
            models.Index(fields=['account', 'created_at']),
            models.Index(fields=['level', 'created_at']),
        ]
    
    def __str__(self) -> str:
        return f"[{self.level}] {self.source}: {self.message[:100]}"
    
    def save(self, *args, **kwargs):
        if not self.uuid:
            import uuid
            self.uuid = uuid.uuid4()
        super().save(*args, **kwargs)
    
    @property
    def is_error(self) -> bool:
        return self.level in [self.LogLevel.ERROR, self.LogLevel.CRITICAL]
    
    @property
    def has_exception(self) -> bool:
        return bool(self.exception_type)


class ApiCallLog(models.Model):
    """
    Logs for external API calls (CAPTCHA service APIs).
    """
    
    uuid = models.UUIDField(
        unique=True,
        editable=False,
        verbose_name=_('UUID')
    )
    account = models.ForeignKey(
        'accounts.CaptchaAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_call_logs',
        verbose_name=_('Account')
    )
    
    service_name = models.CharField(
        max_length=50,
        verbose_name=_('Service Name'),
        help_text=_('e.g., 2Captcha, Anti-Captcha')
    )
    endpoint = models.CharField(
        max_length=255,
        verbose_name=_('API Endpoint')
    )
    method = models.CharField(
        max_length=10,
        verbose_name=_('HTTP Method')
    )
    
    # Request
    request_headers = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Request Headers')
    )
    request_body = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Request Body')
    )
    
    # Response
    status_code = models.PositiveIntegerField(
        verbose_name=_('Status Code')
    )
    response_body = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Response Body')
    )
    
    # Timing
    duration_ms = models.PositiveIntegerField(
        verbose_name=_('Duration (ms)')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    
    # Result
    is_success = models.BooleanField(
        default=False,
        verbose_name=_('Is Success')
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error Message')
    )
    
    class Meta:
        verbose_name = _('API Call Log')
        verbose_name_plural = _('API Call Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'created_at']),
            models.Index(fields=['service_name', 'created_at']),
            models.Index(fields=['is_success']),
        ]
    
    def __str__(self) -> str:
        return f"{self.service_name} - {self.method} {self.endpoint} - {self.status_code}"
    
    def save(self, *args, **kwargs):
        if not self.uuid:
            import uuid
            self.uuid = uuid.uuid4()
        self.is_success = 200 <= self.status_code < 300
        super().save(*args, **kwargs)