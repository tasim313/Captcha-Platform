"""
URL configuration for CAPTCHA jobs API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CaptchaJobViewSet, CaptchaLogViewSet

router = DefaultRouter()
router.register(r'jobs', CaptchaJobViewSet, basename='captcha-job')
router.register(r'logs', CaptchaLogViewSet, basename='captcha-log')

urlpatterns = [
    path('', include(router.urls)),
]