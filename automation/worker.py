"""
Job worker - executes CAPTCHA solving jobs.
"""

import asyncio
import random
import time
from typing import Optional
from datetime import datetime, timedelta

from asgiref.sync import sync_to_async
from structlog import get_logger

from django.conf import settings
from django.utils import timezone

from captcha_jobs.models import CaptchaJob, JobExecution, JobStatus
from captcha_jobs.enums import StopReason
from solver_engine.services import solver_service
from solver_engine.browser.manager import browser_manager, BrowserConfig
from logs.models import LogEntry
from accounts.models import CaptchaAccount

logger = get_logger(__name__)


class JobWorker:
    """
    Executes CAPTCHA solving jobs with proper lifecycle management.
    
    Features:
    - Rate limiting
    - Retry logic
    - Graceful stopping
    - Proxy rotation
    - Error handling
    """
    
    def __init__(self, job: CaptchaJob):
        self.job = job
        self._running = False
        self._paused = False
        self._stop_requested = False
        self._current_execution: Optional[JobExecution] = None
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def is_paused(self) -> bool:
        return self._paused
    
    async def start(self) -> None:
        """Start the job execution."""
        if self._running:
            logger.warning("job_already_running", job_id=str(self.job.uuid))
            return
        
        self._running = True
        self._paused = False
        self._stop_requested = False
        
        # Update job status
        await sync_to_async(self._update_job_status)(JobStatus.RUNNING)
        
        logger.info(
            "job_started",
            job_id=str(self.job.uuid),
            job_name=self.job.name,
            mode=self.job.execution_mode
        )
        
        try:
            if self.job.execution_mode == 'continuous':
                await self._run_continuous()
            elif self.job.execution_mode == 'one_time':
                await self._run_one_time()
            elif self.job.execution_mode == 'scheduled':
                await self._run_one_time()  # Single execution for scheduled triggers
            else:
                logger.error("unknown_execution_mode", mode=self.job.execution_mode)
                
        except Exception as e:
            logger.exception("job_execution_error", job_id=str(self.job.uuid))
            await sync_to_async(self._update_job_status)(
                JobStatus.FAILED,
                error_message=str(e)
            )
        finally:
            self._running = False
    
    async def stop(self, reason: StopReason = StopReason.MANUAL) -> None:
        """Request graceful stop of the job."""
        self._stop_requested = True
        self._paused = False
        
        logger.info(
            "job_stop_requested",
            job_id=str(self.job.uuid),
            reason=reason.value
        )
        
        # Wait for current execution to complete (with timeout)
        timeout = 30
        start = time.time()
        while self._current_execution and (time.time() - start) < timeout:
            await asyncio.sleep(0.5)
        
        await sync_to_async(self._update_job_status)(JobStatus.STOPPED)
    
    async def pause(self) -> None:
        """Pause the job."""
        self._paused = True
        await sync_to_async(self._update_job_status)(JobStatus.PAUSED)
        logger.info("job_paused", job_id=str(self.job.uuid))
    
    async def resume(self) -> None:
        """Resume a paused job."""
        self._paused = False
        await sync_to_async(self._update_job_status)(JobStatus.RUNNING)
        logger.info("job_resumed", job_id=str(self.job.uuid))
    
    async def _run_continuous(self) -> None:
        """Run job in continuous mode."""
        consecutive_failures = 0
        max_consecutive_failures = 10
        
        while not self._stop_requested:
            # Check pause
            if self._paused:
                await asyncio.sleep(1)
                continue
            
            # Check max iterations
            if self.job.max_iterations > 0 and self.job.iteration_count >= self.job.max_iterations:
                logger.info(
                    "job_max_iterations_reached",
                    job_id=str(self.job.uuid),
                    iterations=self.job.iteration_count
                )
                await sync_to_async(self._update_job_status)(JobStatus.COMPLETED)
                break
            
            # Check account status
            account = await sync_to_async(self._get_account)()
            if not account or not account.is_usable:
                logger.warning(
                    "job_account_not_usable",
                    job_id=str(self.job.uuid),
                    account_status=account.status if account else 'not_found