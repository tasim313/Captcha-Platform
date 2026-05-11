from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AccountAuditLog, CaptchaAccount, CaptchaServiceProvider
from .serializers import (
    AccountAuditLogSerializer,
    CaptchaAccountSerializer,
    CaptchaServiceProviderSerializer,
)
from .services import AccountService, log_account_change


class CaptchaServiceProviderViewSet(viewsets.ModelViewSet):
    queryset = CaptchaServiceProvider.objects.all()
    serializer_class = CaptchaServiceProviderSerializer
    permission_classes = [permissions.IsAdminUser]


class CaptchaAccountViewSet(viewsets.ModelViewSet):
    queryset = CaptchaAccount.objects.select_related("service_provider").all()
    serializer_class = CaptchaAccountSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["status", "service_provider"]
    search_fields = ["name"]
    ordering_fields = ["created_at", "balance_usd", "total_solved"]

    def perform_create(self, serializer):
        account = serializer.save(created_by=self.request.user, last_modified_by=self.request.user)
        log_account_change(
            account,
            "created",
            performed_by=self.request.user,
            request=self.request,
        )

    def perform_update(self, serializer):
        account = serializer.save(last_modified_by=self.request.user)
        log_account_change(
            account,
            "updated",
            performed_by=self.request.user,
            request=self.request,
        )

    @action(detail=True, methods=["post"])
    def check_balance(self, request, pk=None):
        balance = AccountService().update_balance(self.get_object())
        return Response({"balance_usd": balance})


class AccountAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AccountAuditLog.objects.select_related("account", "performed_by").all()
    serializer_class = AccountAuditLogSerializer
    permission_classes = [permissions.IsAdminUser]
