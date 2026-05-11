import random

from django.utils import timezone

from logs.services import create_platform_log

from .enums import ExecutionMode, JobStatus
from .models import CaptchaJob


class JobControlService:
    def start(self, job):
        job.status = JobStatus.RUNNING
        job.last_started_at = timezone.now()
        job.last_error_message = ""
        job.save(update_fields=["status", "last_started_at", "last_error_message", "updated_at"])
        create_platform_log(source="job", level="INFO", job=job, account=job.account, message="Job started")
        return job

    def pause(self, job):
        job.status = JobStatus.PAUSED
        job.last_stopped_at = timezone.now()
        job.save(update_fields=["status", "last_stopped_at", "updated_at"])
        create_platform_log(source="job", level="INFO", job=job, account=job.account, message="Job paused")
        return job

    def stop(self, job, reason="manual"):
        job.status = JobStatus.STOPPED
        job.last_stopped_at = timezone.now()
        job.metadata = {**job.metadata, "stop_reason": reason}
        job.save(update_fields=["status", "last_stopped_at", "metadata", "updated_at"])
        create_platform_log(source="job", level="WARNING", job=job, account=job.account, message=f"Job stopped: {reason}")
        return job

    def restart(self, job):
        job.iteration_count = 0
        job.status = JobStatus.IDLE
        job.celery_task_id = ""
        job.last_error_message = ""
        job.save(update_fields=["iteration_count", "status", "celery_task_id", "last_error_message", "updated_at"])
        return self.start(job)

    def next_delay_seconds(self, job):
        if job.requests_per_minute <= 0:
            return max(1, job.retry_delay_seconds)
        base_delay = 60 / job.requests_per_minute
        randomized = random.uniform(job.min_delay_ms / 1000, job.max_delay_ms / 1000)
        return max(base_delay, randomized)
