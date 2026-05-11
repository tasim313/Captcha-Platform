from rest_framework import permissions, viewsets

from .models import Withdrawal, WithdrawalMethod
from .serializers import WithdrawalMethodSerializer, WithdrawalSerializer


class WithdrawalMethodViewSet(viewsets.ModelViewSet):
    queryset = WithdrawalMethod.objects.all()
    serializer_class = WithdrawalMethodSerializer
    permission_classes = [permissions.IsAdminUser]


class WithdrawalViewSet(viewsets.ModelViewSet):
    queryset = Withdrawal.objects.select_related("account", "method").all()
    serializer_class = WithdrawalSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["account", "method", "status"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
