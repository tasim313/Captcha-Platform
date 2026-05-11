from django.contrib import admin

from .models import CaptchaJob, JobExecution


@admin.register(CaptchaJob)
class CaptchaJobAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "account",
        "target",
        "status",
        "execution_mode",
        "iteration_count",
        "last_started_at",
    )
    list_filter = ("status", "execution_mode", "priority")
    search_fields = ("name", "description", "account__name", "target__name")


@admin.register(JobExecution)
class JobExecutionAdmin(admin.ModelAdmin):
    list_display = ("job", "sequence_number", "status", "duration_ms", "cost_usd", "started_at")
    list_filter = ("status",)
    search_fields = ("job__name", "api_task_id")
