"""
2Captcha API client implementation.
"""

import time
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx
from structlog import get_logger

from .base import (
    BaseCaptchaClient,
    CaptchaType,
    SolveStatus,
    CaptchaTask,
    SolveRequest,
    BalanceInfo,
)

logger = get_logger(__name__)


class TwoCaptchaClient(BaseCaptchaClient):
    """
    2Captcha API client implementation.
    
    API Documentation: https://2captcha.com/2captcha-api
    """
    
    BASE_URL = "https://api.2captcha.com"
    
    # CAPTCHA type mappings for 2Captcha API
    TYPE_MAPPING = {
        CaptchaType.IMAGE: 'ImageToTextTask',
        CaptchaType.RECAPTCHA_V2: 'RecaptchaV2TaskProxyless',
        CaptchaType.RECAPTCHA_V3: 'RecaptchaV3TaskProxyless',
        CaptchaType.RECAPTCHA_ENTERPRISE: 'RecaptchaV2EnterpriseTaskProxyless',
        CaptchaType.HCAPTCHA: 'HCaptchaTaskProxyless',
        CaptchaType.TURNSTILE: 'TurnstileTaskProxyless',
        CaptchaType.FUNCAPTCHA: 'FunCaptchaTaskProxyless',
        CaptchaType.GEETEST: 'GeeTestTaskProxyless',
        CaptchaType.TEXT_CAPTCHA: 'AntiGateTask',
    }
    
    # With proxy variants
    TYPE_MAPPING_PROXY = {
        CaptchaType.RECAPTCHA_V2: 'RecaptchaV2Task',
        CaptchaType.RECAPTCHA_V3: 'RecaptchaV3Task',
        CaptchaType.RECAPTCHA_ENTERPRISE: 'RecaptchaV2EnterpriseTask',
        CaptchaType.HCAPTCHA: 'HCaptchaTask',
        CaptchaType.TURNSTILE: 'TurnstileTask',
    }
    
    def __init__(
        self,
        api_key: str,
        timeout: int = 120,
        polling_interval: int = 5,
        base_url: Optional[str] = None
    ):
        super().__init__(api_key, timeout, polling_interval)
        self.base_url = base_url or self.BASE_URL
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    'Content-Type': 'application/json',
                }
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _get_task_type(self, captcha_type: CaptchaType, has_proxy: bool = False) -> str:
        """Get the 2Captcha task type string."""
        if has_proxy and captcha_type in self.TYPE_MAPPING_PROXY:
            return self.TYPE_MAPPING_PROXY[captcha_type]
        return self.TYPE_MAPPING.get(captcha_type, 'ImageToTextTask')
    
    def _build_task_params(self, request: SolveRequest) -> Dict[str, Any]:
        """Build task parameters based on CAPTCHA type."""
        has_proxy = bool(request.proxy)
        task_type = self._get_task_type(request.captcha_type, has_proxy)
        
        params: Dict[str, Any] = {
            'type': task_type,
        }
        
        # Common parameters
        if request.websiteURL:
            params['websiteURL'] = request.site_url
        
        # Type-specific parameters
        if request.captcha_type == CaptchaType.IMAGE:
            if request.image_data:
                params['body'] = request.image_data
            elif request.image_url:
                params['imageURL'] = request.image_url
            params['phrase'] = False
            params['case'] = False
            params['numeric'] = 0
            params['math'] = False
            params['minLength'] = 0
            params['maxLength'] = 0
        
        elif request.captcha_type in (CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_ENTERPRISE):
            params['websiteKey'] = request.site_key
            if request.enterprise:
                params['enterprisePayload'] = request.metadata.get('enterprise_payload', {})
        
        elif request.captcha_type == CaptchaType.RECAPTCHA_V3:
            params['websiteKey'] = request.site_key
            if request.action:
                params['pageAction'] = request.action
            if request.min_score is not None:
                params['minScore'] = request.min_score
        
        elif request.captcha_type == CaptchaType.HCAPTCHA:
            params['websiteKey'] = request.site_key
            if request.invisible:
                params['isInvisible'] = True
            params['metadata'] = request.metadata.get('hcaptcha_metadata', {})
        
        elif request.captcha_type == CaptchaType.TURNSTILE:
            params['websiteKey'] = request.site_key
            params['metadata'] = request.metadata.get('turnstile_metadata', {})
        
        # Proxy parameters
        if has_proxy:
            proxy_parts = request.proxy.split('://')[-1]
            if '@' in proxy_parts:
                auth, address = proxy_parts.split('@')
                username, password = auth.split(':')
                host, port = address.split(':')
            else:
                username = None
                password = None
                host, port = proxy_parts.split(':')
            
            params['proxyType'] = request.proxy.split('://')[0]
            params['proxyAddress'] = host
            params['proxyPort'] = int(port)
            if username:
                params['proxyLogin'] = username
            if password:
                params['proxyPassword'] = password
        
        if request.user_agent:
            params['userAgent'] = request.user_agent
        
        return params
    
    async def submit(self, request: SolveRequest) -> CaptchaTask:
        """Submit a CAPTCHA solving request to 2Captcha."""
        client = await self._get_client()
        start_time = datetime.utcnow()
        
        params = self._build_task_params(request)
        
        payload = {
            'clientKey': self.api_key,
            'task': params,
        }
        
        try:
            logger.info(
                "twocaptcha_submit_start",
                captcha_type=request.captcha_type.value,
                site_url=request.site_url
            )
            
            response = await client.post('/createTask', json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data.get('errorId', 0) != 0:
                error_code = data.get('errorCode', 'unknown')
                error_desc = data.get('errorDescription', 'Unknown error')
                logger.error(
                    "twocaptcha_submit_error",
                    error_code=error_code,
                    error_desc=error_desc
                )
                return CaptchaTask(
                    task_id='',
                    captcha_type=request.captcha_type,
                    status=SolveStatus.FAILED,
                    error=f"[{error_code}] {error_desc}",
                    created_at=start_time,
                    completed_at=datetime.utcnow(),
                    metadata={'api_response': data}
                )
            
            task_id = str(data.get('taskId', ''))
            
            logger.info(
                "twocaptcha_submit_success",
                task_id=task_id,
                captcha_type=request.captcha_type.value
            )
            
            return CaptchaTask(
                task_id=task_id,
                captcha_type=request.captcha_type,
                status=SolveStatus.PROCESSING,
                created_at=start_time,
                metadata={'api_response': data}
            )
            
        except httpx.HTTPError as e:
            logger.error("twocaptcha_http_error", error=str(e))
            return CaptchaTask(
                task_id='',
                captcha_type=request.captcha_type,
                status=SolveStatus.FAILED,
                error=f"HTTP error: {e}",
                created_at=start_time,
                completed_at=datetime.utcnow()
            )
        except Exception as e:
            logger.exception("twocaptcha_submit_exception")
            return CaptchaTask(
                task_id='',
                captcha_type=request.captcha_type,
                status=SolveStatus.FAILED,
                error=f"Unexpected error: {e}",
                created_at=start_time,
                completed_at=datetime.utcnow()
            )
    
    async def get_result(self, task_id: str) -> CaptchaTask:
        """Get the result of a submitted task."""
        client = await self._get_client()
        
        payload = {
            'clientKey': self.api_key,
            'taskId': int(task_id),
        }
        
        try:
            response = await client.post('/getTaskResult', json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data.get('errorId', 0) != 0:
                error_code = data.get('errorCode', 'unknown')
                error_desc = data.get('errorDescription', 'Unknown error')
                return CaptchaTask(
                    task_id=task_id,
                    captcha_type=CaptchaType.IMAGE,  # Unknown at this point
                    status=SolveStatus.FAILED,
                    error=f"[{error_code}] {error_desc}",
                    metadata={'api_response': data}
                )
            
            status_str = data.get('status', '')
            
            if status_str == 'ready':
                solution = data.get('solution', {})
                token = solution.get('gRecaptchaResponse') or \
                        solution.get('token') or \
                        solution.get('text') or \
                        None
                
                return CaptchaTask(
                    task_id=task_id,
                    captcha_type=CaptchaType.IMAGE,
                    status=SolveStatus.SOLVED,
                    solution=solution,
                    token=token,
                    cost_usd=solution.get('cost'),
                    metadata={'api_response': data}
                )
            else:
                return CaptchaTask(
                    task_id=task_id,
                    captcha_type=CaptchaType.IMAGE,
                    status=SolveStatus.PROCESSING,
                    metadata={'api_response': data}
                )
                
        except Exception as e:
            logger.error("twocaptcha_result_error", task_id=task_id, error=str(e))
            return CaptchaTask(
                task_id=task_id,
                captcha_type=CaptchaType.IMAGE,
                status=SolveStatus.FAILED,
                error=str(e)
            )
    
    async def solve(self, request: SolveRequest) -> CaptchaTask:
        """Submit and poll for CAPTCHA solution."""
        # Submit the task
        task = await self.submit(request)
        
        if task.status == SolveStatus.FAILED:
            return task
        
        # Poll for result
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            await asyncio.sleep(self.polling_interval)
            
            result = await self.get_result(task.task_id)
            
            if result.status == SolveStatus.SOLVED:
                result.created_at = task.created_at
                result.completed_at = datetime.utcnow()
                result.duration_seconds = (result.completed_at - result.created_at).total_seconds()
                result.captcha_type = request.captcha_type
                return result
            
            if result.status == SolveStatus.FAILED:
                result.created_at = task.created_at
                result.completed_at = datetime.utcnow()
                result.duration_seconds = (result.completed_at - result.created_at).total_seconds()
                result.captcha_type = request.captcha_type
                return result
        
        # Timeout
        return CaptchaTask(
            task_id=task.task_id,
            captcha_type=request.captcha_type,
            status=SolveStatus.TIMEOUT,
            error=f"Solution timeout after {self.timeout} seconds",
            created_at=task.created_at,
            completed_at=datetime.utcnow(),
            duration_seconds=self.timeout
        )
    
    async def get_balance(self) -> BalanceInfo:
        """Get current 2Captcha account balance."""
        client = await self._get_client()
        
        payload = {
            'clientKey': self.api_key,
        }
        
        try:
            response = await client.post('/getBalance', json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data.get('errorId', 0) != 0:
                raise Exception(f"API error: {data.get('errorDescription')}")
            
            balance = float(data.get('balance', 0))
            
            return BalanceInfo(
                balance_usd=balance,
                currency='USD'
            )
            
        except Exception as e:
            logger.error("twocaptcha_balance_error", error=str(e))
            raise
    
    async def report_bad(self, task_id: str) -> bool:
        """Report an incorrectly solved CAPTCHA."""
        client = await self._get_client()
        
        payload = {
            'clientKey': self.api_key,
            'taskId': int(task_id),
        }
        
        try:
            response = await client.post('/reportIncorrectRecaptcha', json=payload)
            response.raise_for_status()
            data = response.json()
            
            return data.get('errorId', 0) == 0
            
        except Exception as e:
            logger.error("twocaptcha_report_error", task_id=task_id, error=str(e))
            return False
    
    @property
    def service_name(self) -> str:
        return "2Captcha"
    
    @property
    def supported_types(self) -> List[CaptchaType]:
        return [
            CaptchaType.IMAGE,
            CaptchaType.RECAPTCHA_V2,
            CaptchaType.RECAPTCHA_V3,
            CaptchaType.RECAPTCHA_ENTERPRISE,
            CaptchaType.HCAPTCHA,
            CaptchaType.TURNSTILE,
            CaptchaType.FUNCAPTCHA,
            CaptchaType.GEETEST,
            CaptchaType.TEXT_CAPTCHA,
        ]