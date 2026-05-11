from django.db.models import Count, Sum

from accounts.models import CaptchaAccount
from captcha_jobs.models import CaptchaJob, JobExecution
from earnings.models import DailyEarning
from logs.models import LogEntry


def build_dashboard_snapshot():
    earnings = DailyEarning.objects.aggregate(
        earned=Sum("earned_usd"),
        spent=Sum("spent_usd"),
        solved=Sum("total_solved"),
        failed=Sum("total_failed"),
    )
    return {
        "accounts": {
            "total": CaptchaAccount.objects.count(),
            "active": CaptchaAccount.objects.filter(status="active").count(),
        },
        "jobs": {
            "total": CaptchaJob.objects.count(),
            "running": CaptchaJob.objects.filter(status="running").count(),
            "failed": CaptchaJob.objects.filter(status="failed").count(),
        },
        "solves": {
            "total": JobExecution.objects.filter(status="completed").count(),
            "success_by_type": list(
                JobExecution.objects.filter(status="completed", job__target__captcha_type__isnull=False)
                .values("job__target__captcha_type")
                .annotate(total=Count("id"))
                .order_by("-total")
            ),
        },
        "earnings": earnings,
        "logs": {
            "errors": LogEntry.objects.filter(level__in=["ERROR", "CRITICAL"]).count(),
        },
    }
