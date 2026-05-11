from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BalanceSnapshotViewSet, DailyEarningViewSet, EarningTransactionViewSet

router = DefaultRouter()
router.register("daily", DailyEarningViewSet, basename="daily-earning")
router.register("transactions", EarningTransactionViewSet, basename="earning-transaction")
router.register("balances", BalanceSnapshotViewSet, basename="balance-snapshot")

urlpatterns = [path("", include(router.urls))]
