"""
Custom middleware for the platform
"""
import time
import uuid
from django.utils.deprecation import MiddlewareMixin


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log request/response details for API calls
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Generate request ID
        request.request_id = str(uuid.uuid4())[:8]
        
        # Start timer
        start_time = time.time()
        
        # Process request
        response = self.get_response(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log API requests
        if request.path.startswith('/api/'):
            from activity_logs.services import log_request
            
            log_request(
                request_id=request.request_id,
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                duration=duration,
                user=request.user if request.user.is_authenticated else None,
                ip_address=self._get_client_ip(request)
            )
        
        return response
    
    def _get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class TimezoneMiddleware(MiddlewareMixin):
    """
    Middleware to handle user timezone preferences
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Set timezone from user preference or default to UTC
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Could extend User model to have timezone field
            pass
        return self.get_response(request)