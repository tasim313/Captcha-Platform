"""
Base classes for CAPTCHA solver implementations
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SolveResult:
    """Result of a CAPTCHA solve attempt"""
    success: bool
    token: str = ''
    request_id: str = ''
    error: str = ''
    solve_time: float = 0
    cost: float = 0
    extra_data: Dict = None
    
    def __post_init__(self):
        if self.extra_data is None:
            self.extra_data = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'token': self.token,
            'request_id': self.request_id,
            'error': self.error,
            'solve_time': self.solve_time,
            'cost': self.cost,
            'extra_data': self.extra_data,
        }


class BaseCaptchaSolver(ABC):
    """
    Abstract base class for CAPTCHA solvers
    
    All solver implementations must inherit from this class and implement
    the required methods.
    """
    
    def __init__(self, api_key: str, timeout: int = 120):
        """
        Initialize the solver
        
        Args:
            api_key: API key for the solving service
            timeout: Default timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = ''
    
    @abstractmethod
    def solve_recaptcha_v