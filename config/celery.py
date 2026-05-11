import os

try:
    from celery import Celery
except ImportError:  # pragma: no cover - keeps Django importable without Celery installed
    Celery = None

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

if Celery is not None:
    app = Celery("captcha_platform")
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.autodiscover_tasks()
else:
    app = None
