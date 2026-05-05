"""
Celery tasks for CAPTCHA job execution
"""
import logging
from celery import shared_task, chain, group
from celery.result import AsyncResult
from django.utils import timezone
from django.db import transaction

from .models import CaptchaJob, CaptchaLog, JobStatus
from accounts.models import CaptchaAccount

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def start_job(self, job_id: int):
    """
    Start a CAPTCHA solving job
    
    Args:
        job_id: ID of the CaptchaJob to start
    """
    try:
        job = CaptchaJob.objects.select_related('account', 'website').get(id=job_id)
    except CaptchaJob.DoesNotExist:
        logger.error(f"Job {job_id} not found")
        return {'error': 'Job not found'}
    
    # Validate job can be started
    if not job.can_start:
        logger.warning(f"Job {job.id} cannot be started (status: {job.status})")
        return {'error': f'Job cannot be started (status: {job.status})'}
    
    # Check account availability
    if not job.account.is_available():
        logger.error(f"Account {job.account.id} not available for job {job.id}")
        job.status = JobStatus.FAILED
        job.save(update_fields=['status'])
        return {'error': 'Account not available (inactive or no balance)'}
    
    # Update job status
    job.status = JobStatus.RUNNING
    job.started_at = timezone.now()
    job.celery_task_id = self.request.id
    job.save(update_fields=['status', 'started_at', 'celery_task_id'])
    
    logger.info(f"Job {job.id} started: {job.name}")
    
    # Execute based on execution mode
    if job.execution_mode == 'continuous':
        return run_continuous_job.delay(job_id)
    elif job.execution_mode == 'once':
        return run_single_iteration.delay(job_id)
    elif job.execution_mode == 'scheduled':
        return schedule_job.delay(job_id)
    else:
        return run_single_iteration.delay(job_id)


@shared_task(bind=True, max_retries=3)
def stop_job(self, job_id: int):
    """
    Stop a running job
    
    Args:
        job_id: ID of the CaptchaJob to stop
    """
    try:
        job = CaptchaJob.objects.get(id=job_id)
    except CaptchaJob.DoesNotExist:
        return {'error': 'Job not found'}
    
    if not job.can_stop:
        return {'error': f'Job cannot be stopped (status: {job.status})'}
    
    # Revoke the Celery task if it exists
    if job.celery_task_id:
        try:
            AsyncResult(job.celery_task_id).revoke(terminate=True, signal='SIGTERM')
        except Exception as e:
            logger.warning(f"Failed to revoke task {job.celery_task_id}: {e}")
    
    # Update job status
    old_status = job.status
    job.status = JobStatus.STOPPED
    job.celery_task_id = ''
    job.save(update_fields=['status', 'celery_task_id'])
    
    logger.info(f"Job {job.id} stopped (was {old_status})")
    return {'status': 'stopped', 'job_id': job.id}


@shared_task(bind=True, max_retries=3)
def pause_job(self, job_id: int):
    """
    Pause a running job
    
    Args:
        job_id: ID of the CaptchaJob to pause
    """
    try:
        job = CaptchaJob.objects.get(id=job_id)
    except CaptchaJob.DoesNotExist:
        return {'error': 'Job not found'}
    
    if not job.can_pause:
        return {'error': f'Job cannot be paused (status: {job.status})'}
    
    # Revoke the Celery task (but don't terminate)
    if job.celery_task_id:
        try:
            AsyncResult(job.celery_task_id).revoke(terminate=False)
        except Exception as e:
            logger.warning(f"Failed to revoke task {job.celery_task_id}: {e}")
    
    job.status = JobStatus.PAUSED
    job.celery_task_id = ''
    job.save(update_fields=['status', 'celery_task_id'])
    
    logger.info(f"Job {job.id} paused")
    return {'status': 'paused', 'job_id': job.id}


@shared_task(bind=True, max_retries=3)
def restart_job(self, job_id: int):
    """
    Restart a stopped/failed job
    
    Args:
        job_id: ID of the CaptchaJob to restart
    """
    try:
        job = CaptchaJob.objects.get(id=job_id)
    except CaptchaJob.DoesNotExist:
        return {'error': 'Job not found'}
    
    if not job.can_restart:
        return {'error': f'Job cannot be restarted (status: {job.status})'}
    
    # Reset to pending status
    job.status = JobStatus.PENDING
    job.started_at = None
    job.completed_at = None
    job.celery_task_id = ''
    job.save(update_fields=['status', 'started_at', 'completed_at', 'celery_task_id'])
    
    # Start the job
    return start_job.delay(job_id)


@shared_task(bind=True)
def run_continuous_job(self, job_id: int):
    """
    Run a job in continuous mode until stopped or max iterations reached
    
    Args:
        job_id: ID of the CaptchaJob to run
    """
    try:
        job = CaptchaJob.objects.select_related('account', 'website').get(id=job_id)
    except CaptchaJob.DoesNotExist:
        return
    
    from automation.rate_limiter import RateLimiter
    from automation.proxy_manager import ProxyManager
    from solver_engine.two_captcha import TwoCaptchaSolver
    
    # Initialize components
    rate_limiter = RateLimiter(requests_per_minute=job.rate_limit_per_minute)
    proxy_manager = ProxyManager(job) if job.proxy_type != 'none' else None
    solver = TwoCaptchaSolver(job.account)
    
    logger.info(f"Starting continuous job {job.id}: {job.name}")
    
    iteration = 0
    while True:
        # Check if job should stop
        job.refresh_from_db()
        
        if job.status != JobStatus.RUNNING:
            logger.info(f"Job {job.id} no longer running, stopping")
            break
        
        if job.check_completion():
            job.status = JobStatus.COMPLETED
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'completed_at'])
            logger.info(f"Job {job.id} completed (max iterations reached)")
            break
        
        # Rate limiting
        rate_limiter.wait()
        
        # Get proxy if configured
        proxy = proxy_manager.get_proxy() if proxy_manager else None
        
        # Solve CAPTCHA
        try:
            result = solve_single_captcha(
                job=job,
                solver=solver,
                proxy=proxy,
            )
            
            # Update job stats
            job.update_stats(
                solve_time=result.get('solve_time', 0),
                success=result.get('success', False),
                earnings=result.get('cost', 0),
            )
            
            # Update account stats
            job.account.increment_solved_count(result.get('success', False))
            
        except Exception as e:
            logger.error(f"Error in job {job.id} iteration: {e}")
            # Log the error
            CaptchaLog.objects.create(
                job=job,
                account=job.account,
                website=job.website,
                captcha_type=job.website.captcha_type,
                is_success=False,
                error_message=str(e),
            )
            job.update_stats(solve_time=0, success=False)
            job.total_failed += 1
            job.save(update_fields=['total_failed'])
        
        # Update last run time
        job.last_run_at = timezone.now()
        job.celery_task_id = self.request.id
        job.save(update_fields=['last_run_at', 'celery_task_id', 'total_solved', 'total_failed', 
                                'total_earnings', 'avg_solve_time', 'current_iteration'])
        
        iteration += 1
    
    return {'job_id': job_id, 'iterations': iteration}


@shared_task(bind=True)
def run_single_iteration(self, job_id: int):
    """
    Run a single iteration of a job
    
    Args:
        job_id: ID of the CaptchaJob to run
    """
    try:
        job = CaptchaJob.objects.select_related('account', 'website').get(id=job_id)
    except CaptchaJob.DoesNotExist:
        return {'error': 'Job not found'}
    
    from automation.proxy_manager import ProxyManager
    from solver_engine.two_captcha import TwoCaptchaSolver
    
    proxy_manager = ProxyManager(job) if job.proxy_type != 'none' else None
    proxy = proxy_manager.get_proxy() if proxy_manager else None
    solver = TwoCaptchaSolver(job.account)
    
    try:
        result = solve_single_captcha(
            job=job,
            solver=solver,
            proxy=proxy,
        )
        
        job.update_stats(
            solve_time=result.get('solve_time', 0),
            success=result.get('success', False),
            earnings=result.get('cost', 0),
        )
        job.account.increment_solved_count(result.get('success', False))
        
    except Exception as e:
        logger.error(f"Single iteration error for job {job.id}: {e}")
        CaptchaLog.objects.create(
            job=job,
            account=job.account,
            website=job.website,
            captcha_type=job.website.captcha_type,
            is_success=False,
            error_message=str(e),
        )
        job.update_stats(solve_time=0, success=False)
    
    job.last_run_at = timezone.now()
    
    if job.execution_mode == 'once':
        job.status = JobStatus.COMPLETED
        job.completed_at = timezone.now()
    
    job.save()
    
    return {'job_id': job_id, 'success': result.get('success', False) if 'result' in dir() else False}


@shared_task(bind=True)
def schedule_job(self, job_id: int):
    """
    Schedule a job based on its cron expression
    
    Args:
        job_id: ID of the CaptchaJob to schedule
    """
    try:
        job = CaptchaJob.objects.get(id=job_id)
    except CaptchaJob.DoesNotExist:
        return {'error': 'Job not found'}
    
    from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
    
    # Parse cron expression
    parts = job.cron_expression.strip().split()
    if len(parts) != 5:
        job.status = JobStatus.FAILED
        job.save(update_fields=['status'])
        return {'error': 'Invalid cron expression'}
    
    minute, hour, day_of_month, month_of_month, day_of_week = parts
    
    # Create or get crontab schedule
    schedule, created = CrontabSchedule.objects.get_or_create(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_month,
        day_of_week=day_of_week,
    )
    
    # Create periodic task
    task_name = f"captcha_job_{job.id}"
    
    # Delete existing if any
    PeriodicTask.objects.filter(name=task_name).delete()
    
    PeriodicTask.objects.create(
        name=task_name,
        task='captcha_jobs.tasks.run_single_iteration',
        crontab=schedule,
        args=[job.id],
        enabled=True,
    )
    
    job.status = JobStatus.SCHEDULED
    job.save(update_fields=['status'])
    
    logger.info(f"Job {job.id} scheduled with cron: {job.cron_expression}")
    return {'status': 'scheduled', 'job_id': job_id}


@shared_task(bind=True)
def solve_single_captcha(job, solver, proxy=None):
    """
    Solve a single CAPTCHA
    
    Args:
        job: CaptchaJob instance
        solver: Solver instance
        proxy: Optional proxy URL
        
    Returns:
        Dictionary with solve results
    """
    import time
    from core.utils import calculate_earnings
    
    start_time = time.time()
    result = {'success': False, 'solve_time': 0, 'cost': 0, 'token': ''}
    
    try:
        # Solve based on CAPTCHA type
        captcha_type = job.website.captcha_type
        
        if captcha_type == 'recaptcha_v2':
            solve_result = solver.solve_recaptcha_v2(
                site_key=job.website.site_key,
                page_url=job.website.page_url or job.website.url,
                proxy=proxy,
            )
        elif captcha_type == 'recaptcha_v3':
            solve_result = solver.solve_recaptcha_v3(
                site_key=job.website.site_key,
                page_url=job.website.page_url or job.website.url,
                action=job.extra_config.get('recaptcha_action', 'submit'),
                proxy=proxy,
            )
        elif captcha_type == 'hcaptcha':
            solve_result = solver.solve_hcaptcha(
                site_key=job.website.site_key,
                page_url=job.website.page_url or job.website.url,
                proxy=proxy,
            )
        elif captcha_type == 'turnstile':
            solve_result = solver.solve_turnstile(
                site_key=job.website.site_key,
                page_url=job.website.page_url or job.website.url,
                proxy=proxy,
            )
        elif captcha_type == 'image_captcha':
            # For image CAPTCHA, we might need to fetch the image first
            # This is a simplified version
            solve_result = solver.solve_image(
                image_url=job.extra_config.get('image_url', ''),
                proxy=proxy,
            )
        else:
            raise ValueError(f"Unsupported CAPTCHA type: {captcha_type}")
        
        solve_time = time.time() - start_time
        
        if solve_result.get('success'):
            result = {
                'success': True,
                'solve_time': solve_time,
                'token': solve_result.get('token', ''),
                'request_id': solve_result.get('request_id', ''),
                'cost': calculate_earnings(captcha_type, 1),
            }
        else:
            result = {
                'success': False,
                'solve_time': solve_time,
                'error': solve_result.get('error', 'Unknown error'),
            }
        
    except Exception as e:
        solve_time = time.time() - start_time
        result = {
            'success': False,
            'solve_time': solve_time,
            'error': str(e),
        }
    
    # Log the attempt
    CaptchaLog.objects.create(
        job=job,
        account=job.account,
        website=job.website,
        captcha_type=job.website.captcha_type,
        is_success=result['success'],
        solve_time=result['solve_time'],
        token=result.get('token', ''),
        error_message=result.get('error', ''),
        api_request_id=result.get('request_id', ''),
        cost=result.get('cost', 0),
        proxy_used=proxy or '',
    )
    
    # Track earnings
    if result['success'] and result.get('cost', 0) > 0:
        from earnings.services import EarningsService
        EarningsService.record_earning(
            account=job.account,
            job=job,
            captcha_type=job.website.captcha_type,
            amount=result['cost'],
            solve_time=result['solve_time'],
        )
    
    return result