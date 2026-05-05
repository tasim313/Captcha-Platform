"""
Base handler for different CAPTCHA types.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class SolveContext:
    """Context for a CAPTCHA solve operation."""
    job_id: str
    account_id: str
    target_url: str
    captcha_type: str
    site_key: Optional[str] = None
    proxy_url: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SolveResult:
    """Result of a CAPTCHA solve operation."""
    success: bool
    token: Optional[str] = None
    solution: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: int = 0
    api_task_id: Optional[str] = None
    cost_usd: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseCaptchaHandler(ABC):
    """
    Abstract base class for CAPTCHA type handlers.
    
    Each CAPTCHA type (reCAPTCHA, hCaptcha, etc.) should have
    its own handler implementation with type-specific logic.
    """
    
    @property
    @abstractmethod
    def captcha_type(self) -> str:
        """The CAPTCHA type this handler supports."""
        pass
    
    @abstractmethod
    async def solve(self, context: SolveContext) -> SolveResult:
        """
        Solve the CAPTCHA.
        
        Args:
            context: The solve context with all necessary information
            
        Returns:
            SolveResult with the outcome
        """
        pass
    
    @abstractmethod
    async def validate_solution(self, token: str, context: SolveContext) -> bool:
        """
        Validate a CAPTCHA solution (optional).
        
        Args:
            token: The solution token to validate
            context: The original solve context
            
        Returns:
            True if the solution is valid
        """
        pass
    
    def get_injection_script(self, token: str, context: SolveContext) -> str:
        """
        Get JavaScript to inject the token into the page.
        
        Args:
            token: The solution token
            context: The solve context
            
        Returns:
            JavaScript code to execute
        """
        return ''
    
    def cleanup(self) -> None:
        """Clean up any resources."""
        pass