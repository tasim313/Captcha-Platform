from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ApiCallLogViewSet, LogEntryViewSet

router = DefaultRouter()
router.register("", LogEntryViewSet, basename="log-entry")
router.register("api-calls", ApiCallLogViewSet, basename="api-call-log")

urlpatterns = [path("", include(router.urls))]
