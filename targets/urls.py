from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProxyConfigurationViewSet, TargetWebsiteViewSet

router = DefaultRouter()
router.register("websites", TargetWebsiteViewSet, basename="target-website")
router.register("proxies", ProxyConfigurationViewSet, basename="proxy-config")

urlpatterns = [path("", include(router.urls))]
