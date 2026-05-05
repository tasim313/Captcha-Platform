"""
URL configuration for accounts API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CaptchaAccountViewSet, AccountAuditLogViewSet

router = DefaultRouter()
router.register(r'accounts', CaptchaAccountViewSet, basename='captcha-account')
router.register(r'audit-logs', AccountAuditLogViewSet, basename='account-audit-log')

urlpatterns = [
    path('', include(router.urls)),
]