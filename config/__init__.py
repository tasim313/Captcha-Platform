try:
    from .celery import app as celery_app
except Exception:  # pragma: no cover - fallback for partial local environments
    celery_app = None

__all__ = ("celery_app",)
