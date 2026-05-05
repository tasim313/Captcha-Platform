"""
URL configuration for CAPTCHA Automation Platform
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),
    
    # API Authentication
    path('api/auth/token/', obtain_auth_token, name='api_token_auth'),
    
    # API Endpoints
    path('api/accounts/', include('accounts.urls')),
    path('api/websites/', include('websites.urls')),
    path('api/jobs/', include('captcha_jobs.urls')),
    path('api/earnings/', include('earnings.urls')),
    path('api/withdrawals/', include('withdrawals.urls')),
    
    # Dashboard
    path('dashboard/', include('dashboard.urls')),
    
    # Health Check
    path('api/health/', health_check, name='health_check'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


from django.http import JsonResponse
def health_check(request):
    """Health check endpoint for monitoring"""
    from django.core.cache import cache
    from django.db import connection
    
    health_status = {
        'status': 'healthy',
        'checks': {}
    }
    
    # Check database
    try:
        connection.ensure_connection()
        health_status['checks']['database'] = {'status': 'healthy'}
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['checks']['database'] = {'status': 'unhealthy', 'error': str(e)}
    
    # Check Redis/Cache
    try:
        cache.set('_health_check', 'ok', 10)
        cache.get('_health_check')
        health_status['checks']['cache'] = {'status': 'healthy'}
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['checks']['cache'] = {'status': 'unhealthy', 'error': str(e)}
    
    # Check Celery
    try:
        from config.celery import app as celery_app
        celery_app.control.inspect().ping()
        health_status['checks']['celery'] = {'status': 'healthy'}
    except Exception as e:
        health_status['status'] = 'degraded'
        health_status['checks']['celery'] = {'status': 'degraded', 'error': str(e)}
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return JsonResponse(health_status, status=status_code)