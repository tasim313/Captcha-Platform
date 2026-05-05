"""
reCAPTCHA v2/v3/Enterprise handler.
"""

from typing import Optional, Dict, Any
from structlog import get_logger

from .base import BaseCaptchaHandler, SolveContext, SolveResult

logger = get_logger(__name__)


class RecaptchaHandler(BaseCaptchaHandler):
    """Handler for reCAPTCHA v2, v3, and Enterprise."""
    
    @property
    def captcha_type(self) -> str:
        return 'recaptcha'
    
    async def solve(self, context: SolveContext) -> SolveResult:
        """Solve reCAPTCHA using the solver service."""
        from solver_engine.services import solver_service, CaptchaTypeMapper
        from common.services.captcha_clients.base import CaptchaType, SolveRequest
        
        # Determine exact type
        type_map = {
            'recaptcha_v2': CaptchaType.RECAPTCHA_V2,
            'recaptcha_v3': CaptchaType.RECAPTCHA_V3,
            'recaptcha_enterprise': CaptchaType.RECAPTCHA_ENTERPRISE,
        }
        captcha_type = type_map.get(context.captcha_type, CaptchaType.RECAPTCHA_V2)
        
        request = SolveRequest(
            captcha_type=captcha_type,
            site_url=context.target_url,
            site_key=context.site_key,
            proxy=context.proxy_url,
            user_agent=context.user_agent,
            enterprise=context.captcha_type == 'recaptcha_enterprise',
            action=context.metadata.get('action'),
            min_score=context.metadata.get('min_score'),
            metadata={
                'enterprise_payload': context.metadata.get('enterprise_payload', {}),
            }
        )
        
        try:
            from accounts.models import CaptchaAccount
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
            logger.error("recaptcha_solve_error", error=str(e))
            return SolveResult(success=False, error=str(e))
    
    async def validate_solution(self, token: str, context: SolveContext) -> bool:
        """Validate reCAPTCHA token by checking format."""
        if not token:
            return False
        
        # reCAPTCHA tokens are typically long strings
        if len(token) < 100:
            return False
        
        return True
    
    def get_injection_script(self, token: str, context: SolveContext) -> str:
        """Get JavaScript to inject reCAPTCHA token."""
        if context.captcha_type == 'recaptcha_v3':
            return f"""
            (function() {{
                // Set callback for reCAPTCHA v3
                if (typeof window.___grecaptcha_cfg !== 'undefined') {{
                    window.___grecaptcha_cfg.clients.forEach(function(client) {{
                        if (client && client.Va && client.Va.callback) {{
                            client.Va.callback('{token}');
                        }}
                    }});
                }}
                
                // Alternative: dispatch event
                document.dispatchEvent(new CustomEvent('recaptcha-token', {{
                    detail: {{ token: '{token}' }}
                }}));
            }})();
            """
        else:
            # reCAPTCHA v2
            return f"""
            (function() {{
                // Find textarea and set value
                var textareas = document.querySelectorAll('textarea[name="g-recaptcha-response"]');
                textareas.forEach(function(el) {{
                    el.value = '{token}';
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }});
                
                // Also set in iframe if exists
                var iframes = document.querySelectorAll('iframe[src*="recaptcha"]');
                iframes.forEach(function(iframe) {{
                    try {{
                        var doc = iframe.contentDocument || iframe.contentWindow.document;
                        var ta = doc.querySelector('textarea[name="g-recaptcha-response"]');
                        if (ta) ta.value = '{token}';
                    }} catch(e) {{}}
                }});
                
                // Call callback if defined
                if (typeof window.onSubmit === 'function') {{
                    window.onSubmit('{token}');
                }}
            }})();
            """