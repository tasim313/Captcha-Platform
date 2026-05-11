from django.contrib import admin

from .models import AccountAuditLog, CaptchaAccount, CaptchaServiceProvider


@admin.register(CaptchaServiceProvider)
class CaptchaServiceProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "service_type", "api_base_url", "is_active")
    search_fields = ("name", "service_type")


@admin.register(CaptchaAccount)
class CaptchaAccountAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "service_provider",
        "status",
        "balance_usd",
        "total_solved",
        "total_failed",
        "success_rate",
    )
    list_filter = ("status", "service_provider")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at", "balance_updated_at")


@admin.register(AccountAuditLog)
class AccountAuditLogAdmin(admin.ModelAdmin):
    list_display = ("account", "action", "performed_by", "created_at")
    list_filter = ("action",)
    search_fields = ("account__name",)
