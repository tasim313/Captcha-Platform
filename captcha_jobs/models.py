"""
CAPTCHA job configuration and execution models.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .enums import JobStatus, ExecutionMode, JobPriority


class CaptchaJob(models.Model):
    """
    Configuration for a CAPTCHA solving job.
    """
    
    # Identification
    uuid = models.UUIDField(
        unique=True,
        editable=False,
        verbose_name=_('UUID')
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Job Name')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    
    # Relationships
    account = models.ForeignKey(
        'accounts.CaptchaAccount',
        on_delete=models.PROTECT,
        related_name='jobs',
        verbose_name=_('CAPTCHA Account')
    )
    target = models.ForeignKey(
        'targets.TargetWebsite',
        on_delete=models.PROTECT,
        related_name='jobs',
        verbose_name=_('Target Website')
    )
    proxy_config = models.ForeignKey(
        'targets.ProxyConfiguration',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs',
        verbose_name=_('Proxy Configuration')
    )
    
    # Execution Configuration
    execution_mode = models.CharField(
        max_length=20,
        choices=ExecutionMode.choices,
        default=ExecutionMode.CONTINUOUS,
        verbose_name=_('Execution Mode')
    )
    cron_expression = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Cron Expression'),
        help_text=_('Cron expression for scheduled jobs (e.g., "*/5 * * * *")')
    )
    max_iterations = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Max Iterations'),
        help_text=_('0 = unlimited for continuous mode')
    )
    iteration_count = models.PositiveBigIntegerField(
        default=0,
        verbose_name=_('Current Iteration Count')
    )
    
    # Rate Limiting
    requests_per_minute = models.PositiveIntegerField(
        default=10,
        verbose_name=_('Requests per Minute'),
        help_text=_('Maximum requests per minute')
    )
    min_delay_ms = models.PositiveIntegerField(
        default=1000,
        verbose_name=_('Minimum Delay (ms)'),
        help_text=_('Minimum delay between requests')
    )
    max_delay_ms = models.PositiveIntegerField(
        default=3000,
        verbose_name=_('Maximum Delay (ms)'),
        help_text=_('Maximum delay between requests (randomized)')
    )
    
    # Retry Configuration
    max_retries = models.PositiveIntegerField(
        default=3,
        verbose_name=_('Max Retries per Task')
    )
    retry_delay_seconds = models.PositiveIntegerField(
        default=5,
        verbose_name=_('Retry Delay (seconds)')
    )
    
    # Priority & Queue
    priority = models.CharField(
        max_length=20,
        choices=JobPriority.choices,
        default=JobPriority.NORMAL,
        verbose_name=_('Priority')
    )
    celery_queue = models.CharField(
        max_length=50,
        default='captcha_solving',
        verbose_name=_('Celery Queue')
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.IDLE,
        verbose_name=_('Status'),
        db_index=True
    )
    
    # Timing
    last_started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Started At')
    )
    last_stopped_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Stopped At')
    )
    last_error_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Error At')
    )
    last_error_message = models.TextField(
        blank=True,
        verbose_name=_('Last Error Message')
    )
    
    # Runtime tracking
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Celery Task ID')
    )
    worker_pid = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Worker PID')
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
        related_name='created_captcha_jobs',
        verbose_name=_('Created By')
    )
    
    class Meta:
        verbose_name = _('CAPTCHA Job')
        verbose_name_plural = _('CAPTCHA Jobs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['account', 'status']),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.uuid:
            import uuid
            self.uuid = uuid.uuid4()
        super().save(*args, **kwargs)
    
    @property
    def is_running(self) -> bool:
        return self.status == JobStatus.RUNNING
    
    @property
    def is_startable(self) -> bool:
        return self.status in [JobStatus.IDLE, JobStatus.STOPPED, JobStatus.FAILED, JobStatus.COMPLETED]
    
    @property
    def is_stoppable(self) -> bool:
        return self.status in [JobStatus.RUNNING, JobStatus.PAUSED]
    
    @property
    def total_duration_seconds(self) -> float:
        """Calculate total running duration."""
        if not self.last_started_at:
            return 0.0
        end = self.last_stopped_at or timezone.now()
        return (end - self.last_started_at).total_seconds()
    
    @property
    def queue_name(self) -> str:
        """Get the Celery queue name based on priority."""
        priority_queue_map = {
            JobPriority.CRITICAL: 'high_priority',
            JobPriority.HIGH: 'high_priority',
            JobPriority.NORMAL: self.celery_queue,
            JobPriority.LOW: 'low_priority',
        }
        return priority_queue_map.get(self.priority, self.celery_queue)


class JobExecution(models.Model):
    """
    Individual execution record for a job.
    Tracks each run/solve attempt.
    """
    
    uuid = models.UUIDField(
        unique=True,
        editable=False,
        verbose_name=_('UUID')
    )
    job = models.ForeignKey(
        CaptchaJob,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name=_('Job')
    )
    
    # Execution Details
    sequence_number = models.PositiveIntegerField(
        verbose_name=_('Sequence Number'),
        help_text=_('Execution number within the job')
    )
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Celery Task ID')
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.RUNNING,
        verbose_name=_('Status')
    )
    
    # Results
    captcha_token = models.TextField(
        blank=True,
        verbose_name=_('CAPTCHA Token')
    )
    solution = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Solution Data')
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error Message')
    )
    
    # Timing
    started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Started At')
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At')
    )
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Duration (ms)')
    )
    
    # Resource Usage
    api_task_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('API Task ID'),
        help_text=_('Task ID from CAPTCHA service API')
    )
    proxy_used = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Proxy Used')
    )
    cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_('Cost (USD)')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Additional Metadata')
    )
    
    class Meta:
        verbose_name = _('Job Execution')
        verbose_name_plural = _('Job Executions')
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['job', 'sequence_number']),
            models.Index(fields=['status', 'started_at']),
        ]
        unique_together = [['job', 'sequence_number']]
    
    def __str__(self) -> str:
        return f"{self.job.name} - #{self.sequence_number}"
    
    def save(self, *args, **kwargs):
        if not self.uuid:
            import uuid
            self.uuid = uuid.uuid4()
        
        # Auto-calculate duration
        if self.completed_at and self.started_at:
            self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        
        super().save(*args, **kwargs)
    
    @property
    def is_successful(self) -> bool:
        return self.status == JobStatus.COMPLETED and bool(self.captcha_token)
    
    @property
    def is_failed(self) -> bool:
        return self.status in [JobStatus.FAILED, JobStatus.STOPPED]
    

"""
Models for CAPTCHA job configuration and execution
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.mixins import TimestampMixin, AuditMixin


class ExecutionMode(models.TextChoices):
    """Job execution modes"""
    CONTINUOUS = 'continuous', _('Continuous')
    SCHEDULED = 'scheduled', _('Scheduled')
    ONCE = 'once', _('Run Once')
    MANUAL = 'manual', _('Manual')


class JobStatus(models.TextChoices):
    """Job status options"""
    PENDING = 'pending', _('Pending')
    RUNNING = 'running', _('Running')
    PAUSED = 'paused', _('Paused')
    STOPPED = 'stopped', _('Stopped')
    COMPLETED = 'completed', _('Completed')
    FAILED = 'failed', _('Failed')
    SCHEDULED = 'scheduled', _('Scheduled')


class ProxyType(models.TextChoices):
    """Proxy configuration types"""
    NONE = 'none', _('No Proxy')
    HTTP = 'http', _('HTTP Proxy')
    HTTPS = 'https', _('HTTPS Proxy')
    SOCKS4 = 'socks4', _('SOCKS4 Proxy')
    SOCKS5 = 'socks5', _('SOCKS5 Proxy')
    ROTATING = 'rotating', _('Rotating Proxy Pool')


class CaptchaJob(TimestampMixin, AuditMixin):
    """
    Model representing a CAPTCHA solving job configuration
    """
    
    name = models.CharField(
        max_length=200,
        verbose_name=_('Job Name'),
        help_text=_('Descriptive name for this job')
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Detailed description of what this job does')
    )
    
    # Relationships
    account = models.ForeignKey(
        'accounts.CaptchaAccount',
        on_delete=models.PROTECT,
        related_name='jobs',
        verbose_name=_('Account'),
        help_text=_('CAPTCHA solving account to use')
    )
    
    website = models.ForeignKey(
        'websites.TargetWebsite',
        on_delete=models.PROTECT,
        related_name='jobs',
        verbose_name=_('Target Website'),
        help_text=_('Website to solve CAPTCHAs on')
    )
    
    # Execution Configuration
    execution_mode = models.CharField(
        max_length=20,
        choices=ExecutionMode.choices,
        default=ExecutionMode.MANUAL,
        verbose_name=_('Execution Mode'),
        help_text=_('How this job should be executed')
    )
    
    cron_expression = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Cron Expression'),
        help_text=_('Cron expression for scheduled execution (e.g., "*/5 * * * *")')
    )
    
    max_iterations = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Max Iterations'),
        help_text=_('Maximum number of iterations (null for unlimited)')
    )
    
    rate_limit_per_minute = models.PositiveIntegerField(
        default=10,
        verbose_name=_('Rate Limit (req/min)'),
        help_text=_('Maximum CAPTCHA solve requests per minute')
    )
    
    retry_count = models.PositiveIntegerField(
        default=3,
        verbose_name=_('Retry Count'),
        help_text=_('Number of retry attempts on failure')
    )
    
    retry_delay_seconds = models.PositiveIntegerField(
        default=5,
        verbose_name=_('Retry Delay (s)'),
        help_text=_('Delay between retry attempts in seconds')
    )
    
    timeout_seconds = models.PositiveIntegerField(
        default=120,
        verbose_name=_('Timeout (s)'),
        help_text=_('Maximum time to wait for CAPTCHA solve')
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
        verbose_name=_('Status'),
        db_index=True
    )
    
    current_iteration = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Current Iteration'),
        help_text=_('Number of iterations completed')
    )
    
    last_run_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Run At')
    )
    
    next_run_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Next Run At')
    )
    
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Started At')
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At')
    )
    
    # Celery Task ID for tracking
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Celery Task ID'),
        help_text=_('ID of the current Celery task executing this job')
    )
    
    # Statistics
    total_solved = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Total Solved'),
        help_text=_('Total CAPTCHAs solved by this job')
    )
    
    total_failed = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Total Failed'),
        help_text=_('Total failed attempts by this job')
    )
    
    total_earnings = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name=_('Total Earnings (USD)')
    )
    
    avg_solve_time = models.FloatField(
        default=0,
        verbose_name=_('Avg Solve Time (s)')
    )
    
    # Proxy Configuration
    proxy_type = models.CharField(
        max_length=20,
        choices=ProxyType.choices,
        default=ProxyType.NONE,
        verbose_name=_('Proxy Type')
    )
    
    proxy_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Proxy URL'),
        help_text=_('Proxy URL (e.g., http://user:pass@host:port)')
    )
    
    proxy_rotation_list = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Proxy Rotation List'),
        help_text=_('List of proxy URLs for rotation')
    )
    
    # Browser Automation
    use_browser = models.BooleanField(
        default=False,
        verbose_name=_('Use Browser Automation'),
        help_text=_('Use Playwright for browser-based solving')
    )
    
    browser_headless = models.BooleanField(
        default=True,
        verbose_name=_('Headless Browser'),
        help_text=_('Run browser in headless mode')
    )
    
    browser_timeout = models.PositiveIntegerField(
        default=60,
        verbose_name=_('Browser Timeout (s)')
    )
    
    # Extra configuration
    extra_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Extra Configuration'),
        help_text=_('Additional job configuration as JSON')
    )
    
    is_enabled = models.BooleanField(
        default=True,
        verbose_name=_('Enabled'),
        help_text=_('Whether this job is enabled for execution')
    )
    
    class Meta:
        verbose_name = _('CAPTCHA Job')
        verbose_name_plural = _('CAPTCHA Jobs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_enabled']),
            models.Index(fields=['execution_mode', 'status']),
            models.Index(fields=['account', 'status']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        total = self.total_solved + self.total_failed
        if total == 0:
            return 0.0
        return (self.total_solved / total) * 100
    
    @property
    def is_running(self) -> bool:
        """Check if job is currently running"""
        return self.status == JobStatus.RUNNING
    
    @property
    def can_start(self) -> bool:
        """Check if job can be started"""
        return self.status in [JobStatus.PENDING, JobStatus.STOPPED, JobStatus.COMPLETED, JobStatus.FAILED]
    
    @property
    def can_pause(self) -> bool:
        """Check if job can be paused"""
        return self.status == JobStatus.RUNNING
    
    @property
    def can_stop(self) -> bool:
        """Check if job can be stopped"""
        return self.status in [JobStatus.RUNNING, JobStatus.PAUSED]
    
    @property
    def can_restart(self) -> bool:
        """Check if job can be restarted"""
        return self.status in [JobStatus.STOPPED, JobStatus.COMPLETED, JobStatus.FAILED]
    
    def update_stats(self, solve_time: float, success: bool, earnings: float = 0):
        """Update job statistics after a solve attempt"""
        if success:
            self.total_solved += 1
            self.total_earnings += earnings
            # Update average solve time
            if solve_time > 0:
                self.avg_solve_time = (
                    (self.avg_solve_time * (self.total_solved - 1) + solve_time)
                    / self.total_solved
                )
        else:
            self.total_failed += 1
        
        self.current_iteration += 1
        self.save(update_fields=[
            'total_solved', 'total_failed', 'total_earnings',
            'avg_solve_time', 'current_iteration'
        ])
    
    def check_completion(self) -> bool:
        """Check if job should be completed"""
        if self.max_iterations and self.current_iteration >= self.max_iterations:
            return True
        return False


class CaptchaLog(TimestampMixin):
    """
    Log of individual CAPTCHA solve attempts
    """
    
    job = models.ForeignKey(
        CaptchaJob,
        on_delete=models.CASCADE,
        related_name='logs',
        null=True,
        blank=True,
        verbose_name=_('Job')
    )
    
    account = models.ForeignKey(
        'accounts.CaptchaAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='captcha_logs',
        verbose_name=_('Account')
    )
    
    website = models.ForeignKey(
        'websites.TargetWebsite',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='captcha_logs',
        verbose_name=_('Website')
    )
    
    captcha_type = models.CharField(
        max_length=20,
        choices=websites.models.CaptchaType.choices,
        verbose_name=_('CAPTCHA Type')
    )
    
    is_success = models.BooleanField(
        default=False,
        verbose_name=_('Success'),
        db_index=True
    )
    
    solve_time = models.FloatField(
        default=0,
        verbose_name=_('Solve Time (s)'),
        help_text=_('Time taken to solve the CAPTCHA')
    )
    
    token = models.TextField(
        blank=True,
        verbose_name=_('Response Token'),
        help_text=_('Token received from CAPTCHA service')
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name=_('Error Message')
    )
    
    api_request_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('API Request ID'),
        help_text=_('Request ID from CAPTCHA service')
    )
    
    cost = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=0,
        verbose_name=_('Cost (USD)')
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address Used')
    )
    
    proxy_used = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Proxy Used')
    )
    
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Extra Data')
    )
    
    class Meta:
        verbose_name = _('CAPTCHA Log')
        verbose_name_plural = _('CAPTCHA Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_success', 'created_at']),
            models.Index(fields=['captcha_type', 'is_success']),
            models.Index(fields=['account', 'created_at']),
            models.Index(fields=['job', 'created_at']),
        ]
    
    def __str__(self):
        status = "✓" if self.is_success else "✗"
        return f"{status} {self.get_captcha_type_display()} - {self.created_at}"