from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SolveResult:
    success: bool
    token: str = ""
    request_id: str = ""
    error: str = ""
    solve_time: float = 0
    cost: float = 0
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "success": self.success,
            "token": self.token,
            "request_id": self.request_id,
            "error": self.error,
            "solve_time": self.solve_time,
            "cost": self.cost,
            "extra_data": self.extra_data,
        }


class BaseCaptchaSolver(ABC):
    def __init__(self, api_key: str, timeout: int = 120):
        self.api_key = api_key
        self.timeout = timeout

    @abstractmethod
    async def solve(self, *args, **kwargs):
        raise NotImplementedError
