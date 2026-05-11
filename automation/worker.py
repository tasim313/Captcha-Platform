import asyncio

from captcha_jobs.models import CaptchaJob
from solver_engine.services import solver_service


class JobWorker:
    """
    Minimal async worker abstraction used by higher-level task orchestration.
    """

    def __init__(self, job: CaptchaJob):
        self.job = job
        self._paused = False
        self._stopped = False

    async def start(self):
        if self._stopped:
            return None
        proxy_url = ""
        if self.job.proxy_config:
            proxy_url = self.job.proxy_config.get_proxy_url(self.job.iteration_count)
        return await solver_service.solve_captcha(self.job, proxy_url=proxy_url)

    async def pause(self):
        self._paused = True
        return self._paused

    async def resume(self):
        self._paused = False
        return self._paused

    async def stop(self):
        self._stopped = True
        return self._stopped
