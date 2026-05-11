from decimal import Decimal

from django.utils import timezone

from logs.services import create_api_call_log, create_platform_log
from solver_engine.services import solver_service

from .models import AccountAuditLog, CaptchaAccount


class AccountService:
    def update_balance(self, account: CaptchaAccount) -> Decimal:
        balance_info = solver_service.check_balance_sync(account)
        previous_balance = account.balance_usd
        account.balance_usd = Decimal(str(balance_info.balance_usd))
        account.balance_updated_at = timezone.now()
        account.save(update_fields=["balance_usd", "balance_updated_at", "updated_at"])

        AccountAuditLog.objects.create(
            account=account,
            action=AccountAuditLog.Action.BALANCE_UPDATED,
            old_value=str(previous_balance),
            new_value=str(account.balance_usd),
        )
        create_api_call_log(
            account=account,
            service_name=account.service_provider.name,
            endpoint="get_balance",
            method="POST",
            status_code=200,
            response_body={"balance": float(account.balance_usd)},
            duration_ms=0,
        )
        return account.balance_usd


def log_account_change(account, action, performed_by=None, metadata=None, request=None):
    AccountAuditLog.objects.create(
        account=account,
        action=action,
        performed_by=performed_by,
        ip_address=_get_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else ""),
        metadata=metadata or {},
    )
    create_platform_log(
        source="account",
        level="INFO",
        account=account,
        message=f"Account event: {action}",
        extra_data=metadata or {},
    )


def _get_ip(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
