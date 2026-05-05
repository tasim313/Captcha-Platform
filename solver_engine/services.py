"""
Solver engine service - coordinates CAPTCHA solving operations.
"""

import asyncio
import time
from typing import Optional, Dict, Any, Type
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from structlog import get_logger

from common.services.captcha_clients.base import (
    BaseCaptchaClient,
    CaptchaType,
    SolveRequest,
    SolveStatus,
    CaptchaTask,
    BalanceInfo,
)
from common.services.captcha_clients.twocaptcha import TwoCaptchaClient
from common.services.encryption import decrypt_value

from accounts.models import CaptchaAccount
from targets.models import TargetWebsite, ProxyConfiguration
from captcha_jobs.models import CaptchaJob, JobExecution
from logs.models import LogEntry, ApiCallLog
from earnings.models import EarningTransaction
from earnings.services import EarningsService

logger = get_logger(__name__)


class CaptchaTypeMapper:
    """Maps platform captcha types to client captcha types."""
    
    MAPPING = {
        'recaptcha_v2': CaptchaType.RECAPTCHA_V2,
        'recaptcha_v3': CaptchaType.RECAPTCHA_V3,
        'recaptcha_enterprise': CaptchaType.RECAPTCHA_ENTERPRISE,
        'hcaptcha': CaptchaType.HCAPTCHA,
        'turnstile': CaptchaType.TURNSTILE,
        'funcaptcha': CaptchaType.FUNCAPTCHA,
        'image': CaptchaType.IMAGE,
        'geetest': CaptchaType.GEETEST,
        'text': CaptchaType.TEXT_CAPTCHA,
    }
    
    @classmethod
    def to_client_type(cls, platform_type: str) -> CaptchaType:
        """Convert platform type to client type."""
        return cls.MAPPING.get(platform_type, CaptchaType.IMAGE)
    
    @classmethod
    def to_platform_type(cls, client_type: CaptchaType) -> str:
        """Convert client type to platform type."""
        reverse_mapping = {v: k for k, v in cls.MAPPING.items()}
        return reverse_mapping.get(client_type, 'image')


class SolverService:
    """
    Main service for executing CAPTCHA solving operations.
    
    Coordinates between:
    - Account management (credentials)
    - CAPTCHA clients (API integration)
    - Job tracking (execution records)
    - Earnings tracking (transaction records)
    - Logging (audit trail)
    """
    
    # Client registry
    CLIENT_REGISTRY: Dict[str, Type[BaseCaptchaClient]] = {
        'twocaptcha': TwoCaptchaClient,
    }
    
    def __init__(self):
        self._clients: Dict[str, BaseCaptchaClient] = {}
        self._earnings_service = EarningsService()
    
    def _get_client(self, account: CaptchaAccount) -> BaseCaptchaClient:
        """Get or create a client for the account."""
        account_id = str(account.uuid)
        
        if account_id not in self._clients:
            service_type = account.service_provider.service_type
            client_class = self.CLIENT_REGISTRY.get(service_type)
            
            if not client_class:
                raise ValueError(f"Unsupported service type: {service_type}")
            
            api_key = account.get_api_key()
            config = settings.PLATFORM_CONFIG.get('twocaptcha', {})
            
            self._clients[account_id] = client_class(
                api_key=api_key,
                timeout=config.get('default_timeout', 120),
                polling_interval=config.get('polling_interval', 5),
            )
        
        return self._clients[account_id]
    
    async def solve_captcha(
        self,
        job: CaptchaJob,
        proxy_url: Optional[str] = None
    ) -> JobExecution:
        """
        Execute a single CAPTCHA solve for a job.
        
        Args:
            job: The job to execute
            proxy_url: Optional proxy URL to use
            
        Returns:
            JobExecution with results
        """
        # Create execution record
        execution = JobExecution(
            job=job,
            sequence_number=job.iteration_count + 1,
            proxy_used=proxy_url or '',
        )
        execution.save()
        
        start_time = time.time()
        
        try:
            # Get client
            client = self._get_client(job.account)
            
            # Build solve request
            captcha_type = CaptchaTypeMapper.to_client_type(job.target.captcha_type)
            request = SolveRequest(
                captcha_type=captcha_type,
                site_url=job.target.url,
                site_key=job.target.site_key,
                proxy=proxy_url,
                user_agent=job.target.custom_user_agent,
                invisible=job.target.is_invisible,
                enterprise=job.target.captcha_type == 'recaptcha_enterprise',
                action=job.target.action,
                min_score=job.target.min_score,
                metadata={
                    'enterprise_payload': job.target.enterprise_payload,
                }
            )
            
            # Execute solve
            result = await client.solve(request)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            execution.duration_ms = duration_ms
            execution.api_task_id = result.task_id
            
            # Process result
            if result.status == SolveStatus.SOLVED:
                execution.status = 'completed'
                execution.captcha_token = result.token or ''
                execution.solution = result.solution
                execution.cost_usd = result.cost_usd
                
                # Update account stats
                job.account.total_solved += 1
                if result.cost_usd:
                    job.account.total_spent_usd += result.cost_usd
                job.account.save(update_fields=['total_solved', 'total_failed', 'total_spent_usd', 'updated_at'])
                
                # Record earning
                self._earnings_service.record_solve(
                    account=job.account,
                    job_execution=execution,
                    captcha_type=job.target.captcha_type,
                    cost_usd=result.cost_usd or 0,
                )
                
                # Log success
                LogEntry.objects.create(
                    source=LogEntry.LogSource.SOLVER,
                    level=LogEntry.LogLevel.INFO,
                    job=job,
                    job_execution=execution,
                    account=job.account,
                    message=f"CAPTCHA solved successfully in {duration_ms}ms",
                    extra_data={
                        'captcha_type': job.target.captcha_type,
                        'task_id': result.task_id,
                        'duration_ms': duration_ms,
                    }
                )
                
            else:
                execution.status = 'failed'
                execution.error_message = result.error or 'Unknown error'
                
                # Update account stats
                job.account.total_failed += 1
                job.account.save(update_fields=['total_failed', 'updated_at'])
                
                # Log failure
                LogEntry.objects.create(
                    source=LogEntry.LogSource.SOLVER,
                    level=LogEntry.LogLevel.ERROR,
                    job=job,
                    job_execution=execution,
                    account=job.account,
                    message=f"CAPTCHA solve failed: {result.error}",
                    exception_message=result.error,
                    extra_data={
                        'captcha_type': job.target.captcha_type,
                        'task_id': result.task_id,
                        'status': result.status.value,
                    }
                )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            execution.duration_ms = duration_ms
            execution.status = 'failed'
            execution.error_message = str(e)
            
            # Log exception
            LogEntry.objects.create(
                source=LogEntry.LogSource.SOLVER,
                level=LogEntry.LogLevel.ERROR,
                job=job,
                job_execution=execution,
                account=job.account,
                message=f"Exception during CAPTCHA solve",
                exception_type=type(e).__name__,
                exception_message=str(e),
                stack_trace=import_traceback(),
                extra_data={
                    'captcha_type': job.target.captcha_type,
                    'duration_ms': duration_ms,
                }
            )
            
            logger.exception(
                "solve_exception",
                job_id=str(job.uuid),
                execution_id=str(execution.uuid),
                error=str(e)
            )
        
        # Update job iteration count
        job.iteration_count += 1
        job.save(update_fields=['iteration_count', 'updated_at'])
        
        return execution
    
    async def check_balance(self, account: CaptchaAccount) -> BalanceInfo:
        """Check and update account balance."""
        try:
            client = self._get_client(account)
            balance = await client.get_balance()
            
            # Update account
            account.balance_usd = balance.balance_usd
            account.balance_updated_at = timezone.now()
            account.save(update_fields=['balance_usd', 'balance_updated_at', 'updated_at'])
            
            # Create snapshot
            from earnings.models import BalanceSnapshot
            BalanceSnapshot.objects.create(
                account=account,
                balance_usd=balance.balance_usd,
                source='api'
            )
            
            # Check for low balance
            if balance.balance_usd < 1.0:
                LogEntry.objects.create(
                    source=LogEntry.LogSource.ACCOUNT,
                    level=LogEntry.LogLevel.WARNING,
                    account=account,
                    message=f"Low balance warning: ${balance.balance_usd:.4f}",
                )
            
            return balance
            
        except Exception as e:
            LogEntry.objects.create(
                source=LogEntry.LogSource.ACCOUNT,
                level=LogEntry.LogLevel.ERROR,
                account=account,
                message=f"Failed to check balance",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )
            raise
    
    def close_all(self) -> None:
        """Close all client connections."""
        for client_id, client in self._clients.items():
            try:
                asyncio.get_event_loop().run_until_complete(client.close())
            except Exception:
                pass
        self._clients.clear()


def import_traceback() -> str:
    """Import traceback and return formatted stack trace."""
    import traceback
    return traceback.format_exc()


# Global solver service instance
solver_service = SolverService()