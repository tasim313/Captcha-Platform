"""
Playwright browser manager for CAPTCHA automation.
"""

import asyncio
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
)
from structlog import get_logger

from django.conf import settings

logger = get_logger(__name__)


@dataclass
class BrowserConfig:
    """Configuration for browser instance."""
    headless: bool = True
    slow_mo: int = 0
    timeout: int = 30000
    executable_path: Optional[str] = None
    proxy: Optional[Dict[str, Any]] = None
    user_agent: Optional[str] = None
    viewport: Dict[str, int] = field(default_factory=lambda: {'width': 1920, 'height': 1080})
    locale: str = 'en-US'
    timezone: str = 'America/New_York'
    geolocation: Optional[Dict[str, float]] = None
    permissions: List[str] = field(default_factory=list)
    extra_headers: Dict[str, str] = field(default_factory=dict)
    ignore_https_errors: bool = True
    java_script_enabled: bool = True


class BrowserManager:
    """
    Manages Playwright browser instances for CAPTCHA automation.
    
    Features:
    - Context isolation per job
    - Proxy support
    - Stealth mode
    - Resource management
    - Automatic cleanup
    """
    
    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: Dict[str, BrowserContext] = {}
        self._config = settings.PLATFORM_CONFIG.get('playwright', {})
    
    async def initialize(self) -> None:
        """Initialize Playwright and browser."""
        if self._playwright is None:
            self._playwright = await async_playwright().start()
            
            launch_options = {
                'headless': self._config.get('headless', True),
                'slow_mo': self._config.get('slow_mo', 0),
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1920,1080',
                    '--disable-web-security',
                ],
            }
            
            executable = self._config.get('executable_path')
            if executable:
                launch_options['executable_path'] = executable
            
            self._browser = await self._playwright.chromium.launch(**launch_options)
            logger.info("browser_initialized", headless=launch_options['headless'])
    
    async def close(self) -> None:
        """Close all contexts and browser."""
        # Close all contexts
        for context_id, context in list(self._contexts.items()):
            try:
                await context.close()
            except Exception as e:
                logger.warning("context_close_error", context_id=context_id, error=str(e))
        self._contexts.clear()
        
        # Close browser
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning("browser_close_error", error=str(e))
            self._browser = None
        
        # Stop Playwright
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning("playwright_stop_error", error=str(e))
            self._playwright = None
        
        logger.info("browser_closed")
    
    @asynccontextmanager
    async def create_context(
        self,
        context_id: str,
        config: Optional[BrowserConfig] = None
    ):
        """
        Create and yield a browser context.
        
        Args:
            context_id: Unique identifier for the context
            config: Browser configuration
            
        Yields:
            BrowserContext instance
        """
        if self._browser is None:
            await self.initialize()
        
        config = config or BrowserConfig(
            headless=self._config.get('headless', True),
            slow_mo=self._config.get('slow_mo', 0),
            timeout=self._config.get('timeout', 30000),
        )
        
        context_options = {
            'viewport': config.viewport,
            'locale': config.locale,
            'timezone_id': config.timezone,
            'java_script_enabled': config.java_script_enabled,
            'ignore_https_errors': config.ignore_https_errors,
            'extra_http_headers': config.extra_headers,
        }
        
        if config.proxy:
            context_options['proxy'] = config.proxy
        
        if config.user_agent:
            context_options['user_agent'] = config.user_agent
        
        if config.geolocation:
            context_options['geolocation'] = config.geolocation
            context_options['permissions'] = ['geolocation']
        
        context = await self._browser.new_context(**context_options)
        self._contexts[context_id] = context
        
        # Apply stealth scripts
        await self._apply_stealth(context)
        
        try:
            yield context
        finally:
            try:
                await context.close()
            except Exception as e:
                logger.warning("context_cleanup_error", context_id=context_id, error=str(e))
            finally:
                self._contexts.pop(context_id, None)
    
    async def create_page(
        self,
        context_id: str,
        config: Optional[BrowserConfig] = None
    ) -> Page:
        """Create a new page in an existing or new context."""
        if context_id in self._contexts:
            context = self._contexts[context_id]
        else:
            cm = self.create_context(context_id, config)
            context = await cm.__aenter__()
        
        page = await context.new_page()
        page.set_default_timeout(config.timeout if config else self._config.get('timeout', 30000))
        
        return page
    
    async def _apply_stealth(self, context: BrowserContext) -> None:
        """Apply stealth techniques to avoid detection."""
        stealth_js = """
        // Override navigator properties
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        
        // Override plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        
        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Chrome runtime
        window.chrome = {
            runtime: {},
        };
        
        // Override toString for modified functions
        const nativeToString = Function.prototype.toString;
        Function.prototype.toString = function() {
            if (this === Function.prototype.toString) {
                return 'function toString() { [native code] }';
            }
            return nativeToString.call(this);
        };
        """
        
        await context.add_init_script(stealth_js)
    
    @property
    def is_initialized(self) -> bool:
        return self._playwright is not None and self._browser is not None
    
    @property
    def active_contexts_count(self) -> int:
        return len(self._contexts)


# Global browser manager instance
browser_manager = BrowserManager()