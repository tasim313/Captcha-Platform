"""
Base CAPTCHA solving client interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class CaptchaType(Enum):
    """Supported CAPTCHA types."""
    IMAGE = 'image'
    RECAPTCHA_V2 = 'recaptcha_v2'
    RECAPTCHA_V3 = 'recaptcha_v3'
    RECAPTCHA_ENTERPRISE = 'recaptcha_enterprise'
    HCAPTCHA = 'hcaptcha'
    TURNSTILE = 'turnstile'
    FUNCAPTCHA = 'funcaptcha'
    GEETEST = 'geetest'
    TEXT_CAPTCHA = 'text_captcha'
    GEECAPTCHA = 'geecaptcha'


class SolveStatus(Enum):
    """CAPTCHA solving status."""
    PENDING = 'pending'
    PROCESSING = 'processing'
    SOLVED = 'solved'
    FAILED = 'failed'
    TIMEOUT = 'timeout'
    REPORTED = 'reported'


@dataclass
class CaptchaTask:
    """Represents a CAPTCHA solving task."""
    task_id: str
    captcha_type: CaptchaType
    status: SolveStatus = SolveStatus.PENDING
    solution: Optional[str] = None
    token: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    cost_usd: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SolveRequest:
    """Request to solve a CAPTCHA."""
    captcha_type: CaptchaType
    site_url: str
    site_key: Optional[str] = None
    image_data: Optional[str] = None
    image_url: Optional[str] = None
    proxy: Optional[str] = None
    user_agent: Optional[str] = None
    invisible: bool = False
    enterprise: bool = False
    action: Optional[str] = None
    min_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BalanceInfo:
    """API account balance information."""
    balance_usd: float
    currency: str = 'USD'


class BaseCaptchaClient(ABC):
    """
    Abstract base class for CAPTCHA solving service clients.
    
    All CAPTCHA service integrations should inherit from this class
    and implement the required methods.
    """
    
    def __init__(self, api_key: str, timeout: int = 120, polling_interval: int = 5):
        self.api_key = api_key
        self.timeout = timeout
        self.polling_interval = polling_interval
    
    @abstractmethod
    async def submit(self, request: SolveRequest) -> CaptchaTask:
        """
        Submit a CAPTCHA solving request.
        
        Args:
            request: The CAPTCHA solving request
            
        Returns:
            CaptchaTask with pending status and task_id
        """
        pass
    
    @abstractmethod
    async def get_result(self, task_id: str) -> CaptchaTask:
        """
        Get the result of a submitted task.
        
        Args:
            task_id: The task ID from submit()
            
        Returns:
            CaptchaTask with current status and solution (if solved)
        """
        pass
    
    @abstractmethod
    async def solve(self, request: SolveRequest) -> CaptchaTask:
        """
        Submit and wait for CAPTCHA solution.
        
        Args:
            request: The CAPTCHA solving request
            
        Returns:
            CaptchaTask with final status and solution
        """
        pass
    
    @abstractmethod
    async def get_balance(self) -> BalanceInfo:
        """
        Get current account balance.
        
        Returns:
            BalanceInfo with current balance
        """
        pass
    
    @abstractmethod
    async def report_bad(self, task_id: str) -> bool:
        """
        Report a incorrectly solved CAPTCHA.
        
        Args:
            task_id: The task ID to report
            
        Returns:
            True if report was accepted
        """
        pass
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """Name of the CAPTCHA service."""
        pass
    
    @property
    @abstractmethod
    def supported_types(self) -> list[CaptchaType]:
        """List of supported CAPTCHA types."""
        pass