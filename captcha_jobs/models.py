import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .enums import ExecutionMode, JobPriority, JobStatus


class CaptchaJob(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    account = models.ForeignKey(
        "accounts.CaptchaAccount",
        on_delete=models.PROTECT,
        related_name="jobs",
    )
    target = models.ForeignKey(
        "targets.TargetWebsite",
        on_delete=models.PROTECT,
        related_name="jobs",
    )
    proxy_config = models.ForeignKey(
        "targets.ProxyConfiguration",
        on_delete=models.SET_NULL,
        related_name="jobs",
        null=True,
        blank=True,
    )
    execution_mode = models.CharField(
        max_length=20,
        choices=ExecutionMode.choices,
        default=ExecutionMode.CONTINUOUS,
    )
    cron_expression = models.CharField(max_length=100, blank=True)
    max_iterations = models.PositiveIntegerField(default=0)
    iteration_count = models.PositiveBigIntegerField(default=0)
    requests_per_minute = models.PositiveIntegerField(default=10)
    min_delay_ms = models.PositiveIntegerField(default=1000)
    max_delay_ms = models.PositiveIntegerField(default=3000)
    max_retries = models.PositiveIntegerField(default=3)
    retry_delay_seconds = models.PositiveIntegerField(default=5)
    priority = models.CharField(
        max_length=20,
        choices=JobPriority.choices,
        default=JobPriority.NORMAL,
    )
    celery_queue = models.CharField(max_length=50, default="captcha_solving")
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.IDLE,
        db_index=True,
    )
    last_started_at = models.DateTimeField(blank=True, null=True)
    last_stopped_at = models.DateTimeField(blank=True, null=True)
    last_error_at = models.DateTimeField(blank=True, null=True)
    last_error_message = models.TextField(blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    worker_pid = models.PositiveIntegerField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_captcha_jobs",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def is_running(self):
        return self.status == JobStatus.RUNNING

    @property
    def is_startable(self):
        return self.status in {
            JobStatus.IDLE,
            JobStatus.STOPPED,
            JobStatus.FAILED,
            JobStatus.COMPLETED,
            JobStatus.PAUSED,
        }

    @property
    def is_stoppable(self):
        return self.status in {JobStatus.RUNNING, JobStatus.PAUSED, JobStatus.PENDING}

    @property
    def total_duration_seconds(self):
        if not self.last_started_at:
            return 0
        end = self.last_stopped_at or timezone.now()
        return (end - self.last_started_at).total_seconds()


class JobExecution(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    job = models.ForeignKey(
        CaptchaJob,
        on_delete=models.CASCADE,
        related_name="executions",
    )
    sequence_number = models.PositiveIntegerField()
    celery_task_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
    )
    captcha_token = models.TextField(blank=True)
    solution = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    duration_ms = models.PositiveIntegerField(blank=True, null=True)
    api_task_id = models.CharField(max_length=255, blank=True)
    proxy_used = models.CharField(max_length=255, blank=True)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        unique_together = [["job", "sequence_number"]]

    def __str__(self):
        return f"{self.job.name} #{self.sequence_number}"

    def save(self, *args, **kwargs):
        if self.completed_at and self.started_at:
            self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        super().save(*args, **kwargs)
