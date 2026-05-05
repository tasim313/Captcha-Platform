"""
Celery application configuration for CAPTCHA Automation Platform
"""
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('captcha_platform')

# Load config from Django settings with CELERY prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working"""
    print(f'Request: {self.request!r}')


# Custom signals for task monitoring
from celery.signals import (
    task_prerun,
    task_postrun,
    task_failure,
    task_success,
    task_revoked,
    task_retry,
)


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Handle task start event"""
    from activity_logs.services import log_task_event
    log_task_event(
        task_id=task_id,
        task_name=task.name,
        event='started',
        status='info'
    )


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, retval=None, state=None, **kwargs):
    """Handle task completion event"""
    from activity_logs.services import log_task_event
    log_task_event(
        task_id=task_id,
        task_name=task.name,
        event='completed',
        status='success' if state == 'SUCCESS' else state,
        result=str(retval)[:500] if retval else None
    )


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Handle task failure event"""
    from activity_logs.services import log_task_event
    log_task_event(
        task_id=task_id,
        task_name=sender.name if sender else 'unknown',
        event='failed',
        status='error',
        error_message=str(exception)[:500] if exception else None
    )


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, **kwargs):
    """Handle task retry event"""
    from activity_logs.services import log_task_event
    log_task_event(
        task_id=task_id,
        task_name=sender.name if sender else 'unknown',
        event='retrying',
        status='warning'
    )


@task_revoked.connect
def task_revoked_handler(sender=None, task_id=None, **kwargs):
    """Handle task revocation event"""
    from activity_logs.services import log_task_event
    log_task_event(
        task_id=task_id,
        task_name=sender.name if sender else 'unknown',
        event='revoked',
        status='warning'
    )