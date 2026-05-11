from decimal import Decimal

from django.db.models import Avg
from django.utils import timezone

from core.utils import calculate_earnings

from .models import BalanceSnapshot, DailyEarning, EarningTransaction


class EarningsService:
    def record_solve(self, *, account, job_execution, captcha_type, cost_usd):
        earned_usd = Decimal(str(calculate_earnings(captcha_type, 1)))
        spent_usd = Decimal(str(cost_usd or 0))
        EarningTransaction.objects.create(
            account=account,
            job_execution=job_execution,
            transaction_type=EarningTransaction.TransactionType.EARN,
            amount_usd=earned_usd,
            captcha_type=captcha_type,
            description=f"Solve recorded for {captcha_type}",
            balance_before_usd=account.balance_usd,
            balance_after_usd=account.balance_usd,
        )

        daily, _ = DailyEarning.objects.get_or_create(
            account=account,
            date=timezone.localdate(),
            defaults={"by_captcha_type": {}},
        )
        daily.total_solved += 1
        daily.earned_usd += earned_usd
        daily.spent_usd += spent_usd
        breakdown = dict(daily.by_captcha_type)
        breakdown[captcha_type] = breakdown.get(captcha_type, 0) + 1
        daily.by_captcha_type = breakdown
        average = (
            account.jobs.filter(executions__duration_ms__isnull=False)
            .values_list("executions__duration_ms", flat=True)
        )
        durations = [value for value in average if value is not None]
        if durations:
            daily.average_solve_time_ms = int(sum(durations) / len(durations))
        daily.save()

    def snapshot_balance(self, *, account, source="api"):
        return BalanceSnapshot.objects.create(
            account=account,
            balance_usd=account.balance_usd,
            source=source,
        )
