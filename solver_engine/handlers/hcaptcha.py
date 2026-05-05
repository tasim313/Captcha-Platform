"""
hCaptcha handler.
"""

from typing import Optional, Dict, Any
from structlog import get_logger

from .base import BaseCaptchaHandler, SolveContext, SolveResult

logger = get_logger(__name__)


class HcaptchaHandler(BaseCaptchaHandler):
    """Handler for hCaptcha."""
    
    @property
    def captcha_type(self) -> str:
        return 'hcaptcha'
    
    async def solve(self, context: SolveContext) -> SolveResult:
        """Solve hCaptcha using the solver service."""
        from solver_engine.services import solver_service
        from common.services.captcha_clients.base import CaptchaType, SolveRequest
        from accounts.models import CaptchaAccount
        
        request = SolveRequest(
            captcha_type=CaptchaType.HCAPTCHA,
            site_url=context.target_url,
            site_key=context.site_key,
            proxy=context.proxy_url,
            user_agent=context.user_agent,
            invisible=context.metadata.get('is_invisible', False),
            metadata={
                'hcaptcha_metadata': context.metadata.get('hcaptcha_metadata', {}),
            }
        )
        
        try:
            account = await CaptchaAccount.objects.aget(uuid=context.account_id)
            client = solver_service._get_client(account)
            result = await client.solve(request)
            
            if result.status.value == 'solved':
                return SolveResult(
                    success=True,
                    token=result.token,
                    solution=result.solution,
                    duration_ms=int((result.completed_at - result.created_at).total_seconds() * 1000) if result.completed_at else 0,
                    api_task_id=result.task_id,
                    cost_usd=result.cost_usd,
                )
            else:
                return SolveResult(
                    success=False,
                    error=result.error or 'Solve failed',
                    duration_ms=int(result.duration_seconds * 1000) if result.duration_seconds else 0,
                    api_task_id=result.task_id,
                )
                
        except Exception as e:
            logger.error("hcaptcha_solve_error", error=str(e))
            return SolveResult(success=False, error=str(e))
    
    async def validate_solution(self, token: str, context: SolveContext) -> bool:
        """Validate hCaptcha token."""
        if not token or len(token) < 100:
            return False
        return True
    
    def get_injection_script(self, token: str, context: SolveContext) -> str:
        """Get JavaScript to inject hCaptcha token."""
        return f"""
        (function() {{
            // Set h-captcha-response textarea
            var textareas = document.querySelectorAll('textarea[name="h-captcha-response"]');
            textareas.forEach(function(el) {{
                el.value = '{token}';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }});
            
            // Also try setting in iframe
            var iframes = document.querySelectorAll('iframe[src*="hcaptcha"]');
            iframes.forEach(function(iframe) {{
                try {{
                    var doc = iframe.contentDocument || iframe.contentWindow.document;
                    var ta = doc.querySelector('textarea[name="h-captcha-response"]');
                    if (ta) ta.value = '{token}';
                }} catch(e) {{}}
            }});
            
            // Trigger callback
            if (typeof window.hcaptcha === 'object' && window.hcaptcha.execute) {{
                // Already handled
            }}
            
            document.dispatchEvent(new CustomEvent('hcaptcha-token', {{
                detail: {{ token: '{token}' }}
            }}));
        }})();
        """