from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CaptchaJobViewSet, JobExecutionViewSet

router = DefaultRouter()
router.register("", CaptchaJobViewSet, basename="captcha-job")
router.register("executions", JobExecutionViewSet, basename="job-execution")

urlpatterns = [path("", include(router.urls))]
