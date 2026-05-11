from django.db import models
from django.utils.translation import gettext_lazy as _


class JobStatus(models.TextChoices):
    IDLE = "idle", _("Idle")
    PENDING = "pending", _("Pending")
    RUNNING = "running", _("Running")
    PAUSED = "paused", _("Paused")
    STOPPED = "stopped", _("Stopped")
    COMPLETED = "completed", _("Completed")
    FAILED = "failed", _("Failed")
    CANCELLED = "cancelled", _("Cancelled")


class ExecutionMode(models.TextChoices):
    CONTINUOUS = "continuous", _("Continuous")
    SCHEDULED = "scheduled", _("Scheduled")
    ONE_TIME = "one_time", _("One Time")


class JobPriority(models.TextChoices):
    CRITICAL = "critical", _("Critical")
    HIGH = "high", _("High")
    NORMAL = "normal", _("Normal")
    LOW = "low", _("Low")
