"""
Enums for CAPTCHA job system.
"""

from enum import Enum


class JobStatus(str, Enum):
    """Job execution status."""
    IDLE = 'idle'
    PENDING = 'pending'
    RUNNING = 'running'
    PAUSED = 'paused'
    STOPPED = 'stopped'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class ExecutionMode(str, Enum):
    """Job execution mode."""
    CONTINUOUS = 'continuous'
    SCHEDULED = 'scheduled'
    ONE_TIME = 'one_time'


class JobPriority(str, Enum):
    """Job priority level."""
    CRITICAL = 'critical'
    HIGH = 'high'
    NORMAL = 'normal'
    LOW = 'low'


class StopReason(str, Enum):
    """Reason for job stopping."""
    MANUAL = 'manual'
    MAX_ITERATIONS = 'max_iterations'
    ERROR = 'error'
    SCHEDULE = 'schedule'
    BALANCE_EXHAUSTED = 'balance_exhausted'
    ACCOUNT_SUSPENDED = 'account_suspended'
    SYSTEM = 'system'