from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import WithdrawalMethodViewSet, WithdrawalViewSet

router = DefaultRouter()
router.register("methods", WithdrawalMethodViewSet, basename="withdrawal-method")
router.register("", WithdrawalViewSet, basename="withdrawal")

urlpatterns = [path("", include(router.urls))]
