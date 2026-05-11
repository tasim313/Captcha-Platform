import asyncio

try:
    from celery import shared_task
    from celery.result import AsyncResult
except ImportError:  # pragma: no cover - local fallback when Celery is absent
    class _ImmediateAsyncResult:
        def __init__(self, result=None, task_id="local-task"):
            self.id = task_id
            self.result = result

        def revoke(self, terminate=False):
            return None

    def shared_task(*_args, **_kwargs):
        def decorator(func):
            def delay(*args, **kwargs):
                return _ImmediateAsyncResult(func(*args, **kwargs))

            def apply_async(args=None, kwargs=None, countdown=None, queue=None):
                args = args or []
                kwargs = kwargs or {}
                return _ImmediateAsyncResult(func(*args, **kwargs))

            func.delay = delay
            func.apply_async = apply_async
            return func

        return decorator

    AsyncResult = _ImmediateAsyncResult
from django.utils import timezone

from captcha_jobs.enums import ExecutionMode, JobStatus
from captcha_jobs.models import CaptchaJob
from captcha_jobs.services import JobControlService
from logs.services import create_platform_log
from solver_engine.services import solver_service


@shared_task(bind=True)
def run_job_iteration(self, job_id):
    job = CaptchaJob.objects.select_related("account", "target", "proxy_config").get(pk=job_id)
    if job.status != JobStatus.RUNNING:
        return {"status": job.status}

    if job.max_iterations and job.iteration_count >= job.max_iterations:
        JobControlService().stop(job, reason="max_iterations")
        job.status = JobStatus.COMPLETED
        job.last_stopped_at = timezone.now()
        job.save(update_fields=["status", "last_stopped_at", "updated_at"])
        return {"status": "completed"}

    proxy_url = ""
    if job.proxy_config:
        proxy_url = job.proxy_config.get_proxy_url(job.iteration_count)
    execution = asyncio.run(solver_service.solve_captcha(job, proxy_url=proxy_url))
    job.celery_task_id = self.request.id
    job.save(update_fields=["celery_task_id", "updated_at"])

    if job.execution_mode == ExecutionMode.CONTINUOUS and job.status == JobStatus.RUNNING:
        delay = JobControlService().next_delay_seconds(job)
        next_result = run_job_iteration.apply_async(args=[job.id], countdown=delay, queue=job.celery_queue)
        job.celery_task_id = next_result.id
        job.save(update_fields=["celery_task_id", "updated_at"])

    if job.execution_mode != ExecutionMode.CONTINUOUS:
        job.status = JobStatus.COMPLETED if execution.status == JobStatus.COMPLETED else JobStatus.FAILED
        job.last_stopped_at = timezone.now()
        job.save(update_fields=["status", "last_stopped_at", "updated_at"])

    return {"execution_id": execution.id, "status": execution.status}


@shared_task
def start_job(job_id):
    job = CaptchaJob.objects.select_related("account").get(pk=job_id)
    JobControlService().start(job)
    task = run_job_iteration.apply_async(args=[job.id], queue=job.celery_queue)
    job.celery_task_id = task.id
    job.save(update_fields=["celery_task_id", "updated_at"])
    return {"task_id": task.id}


@shared_task
def pause_job(job_id):
    job = CaptchaJob.objects.get(pk=job_id)
    if job.celery_task_id:
        AsyncResult(job.celery_task_id).revoke(terminate=False)
    JobControlService().pause(job)
    return {"status": "paused"}


@shared_task
def stop_job(job_id):
    job = CaptchaJob.objects.get(pk=job_id)
    if job.celery_task_id:
        AsyncResult(job.celery_task_id).revoke(terminate=True)
    JobControlService().stop(job)
    return {"status": "stopped"}


@shared_task
def restart_job(job_id):
    job = CaptchaJob.objects.get(pk=job_id)
    JobControlService().restart(job)
    return start_job.delay(job.id).id
