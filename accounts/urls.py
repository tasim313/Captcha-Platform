from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AccountAuditLogViewSet, CaptchaAccountViewSet, CaptchaServiceProviderViewSet

router = DefaultRouter()
router.register("providers", CaptchaServiceProviderViewSet, basename="provider")
router.register("", CaptchaAccountViewSet, basename="account")
router.register("audit-logs", AccountAuditLogViewSet, basename="account-audit-log")

urlpatterns = [path("", include(router.urls))]
