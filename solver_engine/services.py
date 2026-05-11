import asyncio
import time
import traceback
from decimal import Decimal
from typing import Dict, Optional, Type

from django.conf import settings
from django.utils import timezone

from accounts.models import CaptchaAccount
from captcha_jobs.enums import JobStatus
from captcha_jobs.models import CaptchaJob, JobExecution
from common.services.captcha_clients.base import BalanceInfo, CaptchaType, SolveRequest, SolveStatus
from common.services.captcha_clients.base import BaseCaptchaClient
from common.services.captcha_clients.twocaptcha import TwoCaptchaClient
from earnings.services import EarningsService
from logs.services import create_platform_log


class CaptchaTypeMapper:
    MAPPING = {
        "recaptcha_v2": CaptchaType.RECAPTCHA_V2,
        "recaptcha_v3": CaptchaType.RECAPTCHA_V3,
        "recaptcha_enterprise": CaptchaType.RECAPTCHA_ENTERPRISE,
        "hcaptcha": CaptchaType.HCAPTCHA,
        "turnstile": CaptchaType.TURNSTILE,
        "funcaptcha": CaptchaType.FUNCAPTCHA,
        "image": CaptchaType.IMAGE,
        "geetest": CaptchaType.GEETEST,
        "text": CaptchaType.TEXT_CAPTCHA,
    }

    @classmethod
    def to_client_type(cls, platform_type):
        return cls.MAPPING.get(platform_type, CaptchaType.IMAGE)


class SolverService:
    CLIENT_REGISTRY: Dict[str, Type[BaseCaptchaClient]] = {
        "twocaptcha": TwoCaptchaClient,
    }

    def __init__(self):
        self._clients = {}
        self._earnings_service = EarningsService()

    def _get_client(self, account: CaptchaAccount):
        cache_key = str(account.uuid)
        if cache_key not in self._clients:
            client_class = self.CLIENT_REGISTRY[account.service_provider.service_type]
            self._clients[cache_key] = client_class(
                api_key=account.get_api_key(),
                timeout=settings.PLATFORM_CONFIG["twocaptcha"]["default_timeout"],
                polling_interval=settings.PLATFORM_CONFIG["twocaptcha"]["polling_interval"],
            )
        return self._clients[cache_key]

    async def solve_captcha(self, job: CaptchaJob, proxy_url: Optional[str] = None):
        execution = JobExecution.objects.create(
            job=job,
            sequence_number=job.iteration_count + 1,
            status=JobStatus.PENDING,
            proxy_used=proxy_url or "",
        )
        started_at = time.monotonic()
        try:
            client = self._get_client(job.account)
            request = SolveRequest(
                captcha_type=CaptchaTypeMapper.to_client_type(job.target.captcha_type),
                site_url=job.target.url,
                site_key=job.target.site_key,
                proxy=proxy_url,
                user_agent=job.target.custom_user_agent,
                invisible=job.target.is_invisible,
                enterprise=job.target.captcha_type == "recaptcha_enterprise",
                action=job.target.action,
                min_score=job.target.min_score,
                metadata={"enterprise_payload": job.target.enterprise_payload},
            )
            result = await client.solve(request)
            execution.completed_at = timezone.now()
            execution.duration_ms = int((time.monotonic() - started_at) * 1000)
            execution.api_task_id = result.task_id
            if result.status == SolveStatus.SOLVED:
                execution.status = JobStatus.COMPLETED
                execution.captcha_token = result.token or ""
                execution.solution = result.metadata or result.solution
                execution.cost_usd = Decimal(str(result.cost_usd or 0))
                job.account.total_solved += 1
                job.account.total_spent_usd += execution.cost_usd or Decimal("0")
                job.account.save(update_fields=["total_solved", "total_spent_usd", "updated_at"])
                self._earnings_service.record_solve(
                    account=job.account,
                    job_execution=execution,
                    captcha_type=job.target.captcha_type,
                    cost_usd=execution.cost_usd,
                )
                create_platform_log(
                    source=LogEntrySource.SOLVER,
                    level=LogEntryLevel.INFO,
                    message="CAPTCHA solved successfully",
                    job=job,
                    job_execution=execution,
                    account=job.account,
                    extra_data={"duration_ms": execution.duration_ms},
                )
            else:
                execution.status = JobStatus.FAILED
                execution.error_message = result.error or "Unknown solve failure"
                job.account.total_failed += 1
                job.account.save(update_fields=["total_failed", "updated_at"])
                create_platform_log(
                    source=LogEntrySource.SOLVER,
                    level=LogEntryLevel.ERROR,
                    message="CAPTCHA solve failed",
                    job=job,
                    job_execution=execution,
                    account=job.account,
                    exception_message=execution.error_message,
                )
        except Exception as exc:
            execution.completed_at = timezone.now()
            execution.duration_ms = int((time.monotonic() - started_at) * 1000)
            execution.status = JobStatus.FAILED
            execution.error_message = str(exc)
            create_platform_log(
                source=LogEntrySource.SOLVER,
                level=LogEntryLevel.ERROR,
                message="Solver exception",
                job=job,
                job_execution=execution,
                account=job.account,
                exception_type=type(exc).__name__,
                exception_message=traceback.format_exc(),
            )
        execution.save()
        job.iteration_count += 1
        job.save(update_fields=["iteration_count", "updated_at"])
        return execution

    async def check_balance(self, account: CaptchaAccount) -> BalanceInfo:
        client = self._get_client(account)
        return await client.get_balance()

    def check_balance_sync(self, account: CaptchaAccount) -> BalanceInfo:
        return asyncio.run(self.check_balance(account))


class LogEntrySource:
    SOLVER = "solver"


class LogEntryLevel:
    INFO = "INFO"
    ERROR = "ERROR"


solver_service = SolverService()
