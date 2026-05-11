import logging
import time
import uuid

from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        started_at = time.monotonic()
        response = self.get_response(request)
        duration_ms = int((time.monotonic() - started_at) * 1000)

        logger.info(
            "request_completed",
            extra={
                "request_id": request.request_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


class APIThrottlingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        client_ip = self._get_client_ip(request)
        cache_key = f"throttle:{client_ip}:{request.path}:{request.method}"
        window = 60
        limit = 120
        current = cache.get(cache_key, 0)
        if current >= limit:
            return JsonResponse(
                {"detail": "Rate limit exceeded"},
                status=429,
            )

        cache.set(cache_key, current + 1, timeout=window)
        return self.get_response(request)

    def _get_client_ip(self, request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
