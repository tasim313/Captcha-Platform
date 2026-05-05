"""
Utility functions for the platform
"""
import re
import math
from datetime import datetime, timedelta
from typing import Optional, Tuple


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for display purposes
    
    Args:
        data: String to mask
        visible_chars: Number of characters to show at start and end
        
    Returns:
        Masked string like "abcd...wxyz"
    """
    if not data or len(data) <= visible_chars * 2:
        return '****' if data else ''
    
    start = data[:visible_chars]
    end = data[-visible_chars:]
    masked_length = len(data) - (visible_chars * 2)
    
    return f"{start}{'*' * min(masked_length, 8)}{end}"


def calculate_earnings(
    captcha_type: str,
    count: int,
    success_rate: float = 1.0
) -> float:
    """
    Calculate estimated earnings based on CAPTCHA type and count
    
    Args:
        captcha_type: Type of CAPTCHA solved
        count: Number of CAPTCHAs
        success_rate: Success rate (0.0 to 1.0)
        
    Returns:
        Estimated earnings in USD
    """
    # Approximate rates per 1000 CAPTCHAs (adjust based on actual rates)
    RATES_PER_1000 = {
        'recaptcha_v2': 2.99,
        'recaptcha_v3': 2.99,
        'hcaptcha': 2.99,
        'image_captcha': 1.00,
        'turnstile': 2.99,
        'funcaptcha': 2.99,
        'geetest': 2.99,
    }
    
    rate = RATES_PER_1000.get(captcha_type, 1.50)
    earnings = (rate / 1000) * count * success_rate
    
    return round(earnings, 4)


def format_duration(seconds: float) -> str:
    """
    Format seconds into human-readable duration
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string like "1h 30m 45s"
    """
    if not seconds or seconds < 0:
        return "0s"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)


def parse_cron_expression(cron: str) -> Optional[dict]:
    """
    Parse a cron expression into human-readable format
    
    Args:
        cron: Cron expression string (5 parts)
        
    Returns:
        Dictionary with parsed components or None if invalid
    """
    if not cron:
        return None
    
    parts = cron.strip().split()
    if len(parts) != 5:
        return None
    
    field_names = ['minute', 'hour', 'day_of_month', 'month', 'day_of_week']
    return dict(zip(field_names, parts))


def validate_proxy_url(proxy_url: str) -> Tuple[bool, str]:
    """
    Validate proxy URL format
    
    Args:
        proxy_url: Proxy URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not proxy_url:
        return True, ''
    
    # Common proxy patterns
    patterns = [
        r'^https?://[^:]+:\d+$',  # http://host:port
        r'^https?://[^:]+:[^@]+@[^:]+:\d+$',  # http://user:pass@host:port
        r'^socks[45]:\/\/[^:]+:\d+$',
        r'^socks[45]:\/\/[^:]+:[^@]+@[^:]+:\d+$',
    ]
    
    for pattern in patterns:
        if re.match(pattern, proxy_url):
            return True, ''
    
    return False, 'Invalid proxy URL format'


def get_time_range(period: str) -> Tuple[datetime, datetime]:
    """
    Get start and end datetime for a given period
    
    Args:
        period: 'today', 'week', 'month', 'year', or 'all'
        
    Returns:
        Tuple of (start_datetime, end_datetime)
    """
    now = timezone.now()
    
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == 'week':
        start = now - timedelta(days=7)
        end = now
    elif period == 'month':
        start = now - timedelta(days=30)
        end = now
    elif period == 'year':
        start = now - timedelta(days=365)
        end = now
    else:  # 'all'
        start = datetime.min.replace(tzinfo=timezone.utc)
        end = now
    
    return start, end


# Need to import timezone
from django.utils import timezone