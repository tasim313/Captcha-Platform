from django.db.models import Sum
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import BalanceSnapshot, DailyEarning, EarningTransaction
from .serializers import BalanceSnapshotSerializer, DailyEarningSerializer, EarningTransactionSerializer


class DailyEarningViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyEarning.objects.select_related("account").all()
    serializer_class = DailyEarningSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["account", "date"]

    @action(detail=False, methods=["get"])
    def summary(self, _request):
        totals = self.get_queryset().aggregate(
            earned=Sum("earned_usd"),
            spent=Sum("spent_usd"),
            solved=Sum("total_solved"),
            failed=Sum("total_failed"),
        )
        return Response(totals)


class EarningTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EarningTransaction.objects.select_related("account", "job_execution").all()
    serializer_class = EarningTransactionSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["account", "transaction_type", "captcha_type"]


class BalanceSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BalanceSnapshot.objects.select_related("account").all()
    serializer_class = BalanceSnapshotSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["account", "source"]
