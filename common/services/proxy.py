"""
Proxy management service for rotating proxies and pool management.
"""

import random
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Iterator
from enum import Enum

import httpx
from django.conf import settings
from django.core.cache import cache
from structlog import get_logger

logger = get_logger(__name__)


class ProxyProtocol(Enum):
    HTTP = 'http'
    HTTPS = 'https'
    SOCKS4 = 'socks4'
    SOCKS5 = 'socks5'


@dataclass
class ProxyConfig:
    """Configuration for a single proxy."""
    id: str
    host: str
    port: int
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    max_requests: int = 100
    timeout: int = 30
    country: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    @property
    def url(self) -> str:
        """Get the full proxy URL."""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        else:
            auth = ""
        return f"{self.protocol.value}://{auth}{self.host}:{self.port}"
    
    @property
    def cache_key(self) -> str:
        return f"proxy_usage:{self.id}"


@dataclass
class ProxyStats:
    """Statistics for a proxy."""
    proxy_id: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_used: Optional[float] = None
    last_error: Optional[str] = None
    is_banned: bool = False
    ban_expires: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100


class ProxyPool:
    """
    Manages a pool of proxies with rotation, health tracking, and rate limiting.
    
    Features:
    - Round-robin and random rotation strategies
    - Per-proxy request counting
    - Automatic ban detection and cooldown
    - Proxy health scoring
    - Country/protocol filtering
    """
    
    def __init__(self):
        self._proxies: Dict[str, ProxyConfig] = {}
        self._stats: Dict[str, ProxyStats] = {}
        self._rotation_index = 0
        self._enabled = settings.PLATFORM_CONFIG.get('proxy', {}).get('enabled', False)
        self._default_timeout = settings.PLATFORM_CONFIG.get('proxy', {}).get('default_timeout', 30)
    
    def add_proxy(self, proxy: ProxyConfig) -> None:
        """Add a proxy to the pool."""
        self._proxies[proxy.id] = proxy
        self._stats[proxy.id] = ProxyStats(proxy_id=proxy.id)
        logger.info("proxy_added", proxy_id=proxy.id, host=proxy.host)
    
    def remove_proxy(self, proxy_id: str) -> None:
        """Remove a proxy from the pool."""
        if proxy_id in self._proxies:
            del self._proxies[proxy_id]
            del self._stats[proxy_id]
            cache.delete(f"proxy_usage:{proxy_id}")
            logger.info("proxy_removed", proxy_id=proxy_id)
    
    def get_proxy(
        self,
        protocol: Optional[ProxyProtocol] = None,
        country: Optional[str] = None,
        tags: Optional[List[str]] = None,
        strategy: str = 'round_robin'
    ) -> Optional[ProxyConfig]:
        """
        Get a proxy from the pool based on criteria.
        
        Args:
            protocol: Filter by protocol
            country: Filter by country code
            tags: Filter by tags
            strategy: Rotation strategy ('round_robin', 'random', 'least_used', 'healthiest')
            
        Returns:
            ProxyConfig or None if no suitable proxy available
        """
        if not self._enabled:
            return None
        
        available = self._get_available_proxies(protocol, country, tags)
        
        if not available:
            logger.warning("no_available_proxies", protocol=protocol, country=country)
            return None
        
        if strategy == 'random':
            return random.choice(available)
        elif strategy == 'least_used':
            return min(available, key=lambda p: self._stats[p.id].total_requests)
        elif strategy == 'healthiest':
            return max(available, key=lambda p: self._stats[p.id].success_rate)
        else:  # round_robin
            proxy = available[self._rotation_index % len(available)]
            self._rotation_index += 1
            return proxy
    
    def _get_available_proxies(
        self,
        protocol: Optional[ProxyProtocol],
        country: Optional[str],
        tags: Optional[List[str]]
    ) -> List[ProxyConfig]:
        """Get list of available (not banned) proxies matching criteria."""
        available = []
        
        for proxy in self._proxies.values():
            stats = self._stats[proxy.id]
            
            # Skip banned proxies (unless ban expired)
            if stats.is_banned:
                if stats.ban_expires and time.time() > stats.ban_expires:
                    self._unban_proxy(proxy.id)
                else:
                    continue
            
            # Skip if max requests reached
            if stats.total_requests >= proxy.max_requests:
                continue
            
            # Apply filters
            if protocol and proxy.protocol != protocol:
                continue
            if country and proxy.country != country:
                continue
            if tags and not any(t in proxy.tags for t in tags):
                continue
            
            available.append(proxy)
        
        return available
    
    def record_success(self, proxy_id: str) -> None:
        """Record a successful request through a proxy."""
        if proxy_id in self._stats:
            self._stats[proxy_id].successful_requests += 1
            self._stats[proxy_id].total_requests += 1
            self._stats[proxy_id].last_used = time.time()
            self._stats[proxy_id].last_error = None
    
    def record_failure(self, proxy_id: str, error: Optional[str] = None) -> None:
        """Record a failed request through a proxy."""
        if proxy_id in self._stats:
            stats = self._stats[proxy_id]
            stats.failed_requests += 1
            stats.total_requests += 1
            stats.last_used = time.time()
            stats.last_error = error
            
            # Auto-ban after too many consecutive failures
            if stats.failed_requests >= 10 and stats.success_rate < 20:
                self._ban_proxy(proxy_id, duration=300)  # 5 minute ban
    
    def _ban_proxy(self, proxy_id: str, duration: int = 300) -> None:
        """Ban a proxy for a specified duration."""
        if proxy_id in self._stats:
            self._stats[proxy_id].is_banned = True
            self._stats[proxy_id].ban_expires = time.time() + duration
            logger.warning("proxy_banned", proxy_id=proxy_id, duration=duration)
    
    def _unban_proxy(self, proxy_id: str) -> None:
        """Remove ban from a proxy."""
        if proxy_id in self._stats:
            stats = self._stats[proxy_id]
            stats.is_banned = False
            stats.ban_expires = None
            stats.failed_requests = 0  # Reset failure count
            logger.info("proxy_unbanned", proxy_id=proxy_id)
    
    def get_stats(self, proxy_id: str) -> Optional[ProxyStats]:
        """Get statistics for a specific proxy."""
        return self._stats.get(proxy_id)
    
    def get_all_stats(self) -> Dict[str, ProxyStats]:
        """Get statistics for all proxies."""
        return self._stats.copy()
    
    def get_proxy_count(self) -> int:
        """Get total number of proxies in pool."""
        return len(self._proxies)
    
    def get_available_count(self) -> int:
        """Get number of available proxies."""
        return len(self._get_available_proxies(None, None, None))
    
    def reset_proxy(self, proxy_id: str) -> None:
        """Reset statistics for a proxy."""
        if proxy_id in self._stats:
            self._stats[proxy_id] = ProxyStats(proxy_id=proxy_id)
            cache.delete(f"proxy_usage:{proxy_id}")


# Global proxy pool instance
proxy_pool = ProxyPool()


def get_httpx_client(
    proxy: Optional[ProxyConfig] = None,
    timeout: Optional[int] = None,
    **kwargs
) -> httpx.AsyncClient:
    """
    Create an httpx client with optional proxy configuration.
    
    Args:
        proxy: Proxy configuration to use
        timeout: Request timeout in seconds
        **kwargs: Additional httpx client arguments
        
    Returns:
        Configured httpx.AsyncClient
    """
    timeout = timeout or (proxy.timeout if proxy else proxy_pool._default_timeout)
    
    client_kwargs = {
        'timeout': httpx.Timeout(timeout, connect=10.0),
        'follow_redirects': True,
        'http2': True,
        **kwargs
    }
    
    if proxy:
        client_kwargs['proxy'] = proxy.url
    
    return httpx.AsyncClient(**client_kwargs)