"""
Production settings - hardened for production use.
"""

from .base import *  # noqa: F401, F403

# =============================================================================
# Production Overrides
# =============================================================================
DEBUG = False

# =============================================================================
# Security - Hardened
# =============================================================================
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 86400  # 24 hours

# =============================================================================
# Database - Connection pooling
# =============================================================================
DATABASES['default']['CONN_MAX_AGE'] = 60
DATABASES['default']['OPTIONS']['connect_timeout'] = 10

# =============================================================================
# Static files - Whitenoise
# =============================================================================
INSTALLED_APPS.insert(0, 'whitenoise.runserver_nostatic')
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# =============================================================================
# Logging - File + Sentry
# =============================================================================
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration

SENTRY_DSN = os.getenv('SENTRY_DSN')

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment='production',
    )

# =============================================================================
# Email
# =============================================================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@captcha-platform.com')

# =============================================================================
# Admins
# =============================================================================
ADMINS = [
    ('Admin', os.getenv('ADMIN_EMAIL', 'admin@captcha-platform.com')),
]
MANAGERS = ADMINS