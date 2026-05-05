"""
Admin configuration for CAPTCHA jobs
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import CaptchaJob, CaptchaLog


@admin.register(CaptchaJob)
class CaptchaJobAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'account',
        'website',
        'status_badge',
        'execution_mode',
        'progress_display',
        'stats_display',
        'is_enabled',
        'last_run_at',
    ]
    
    list_filter = [
        'status',
        'execution_mode',
        'is_enabled',
        'proxy_type',
    ]
    
    search_fields = [
        'name',
        'description',
        'account__name',
        'website__name',
    ]
    
    readonly_fields = [
        'status',
        'current_iteration',
        'last_run_at',
        'next_run_at',
        'started_at',
        'completed_at',
        'celery_task_id',
        'total_solved',
        'total_failed',
        'total_earnings',
        'avg_solve_time',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'description', 'is_enabled')
        }),
        (_('Configuration'), {
            'fields': ('account', 'website', 'execution_mode', 'cron_expression')
        }),
        (_('Execution Settings'), {
            'fields': (
                'max_iterations',
                'rate_limit_per_minute',
                'retry_count',
                'retry_delay_seconds',
                'timeout_seconds',
            )
        }),
        (_('Status'), {
            'fields': (
                'status',
                'current_iteration',
                'started_at',
                'last_run_at',
                'next_run_at',
                'completed_at',
                'celery_task_id',
            )
        }),
        (_('Statistics'), {
            'fields': (
                'total_solved',
                'total_failed',
                'success_rate_display',
                'total_earnings',
                'avg_solve_time',
            )
        }),
        (_('Proxy Configuration'), {
            'fields': ('proxy_type', 'proxy_url', 'proxy_rotation_list'),
            'classes': ('collapse',),
        }),
        (_('Browser Automation'), {
            'fields': ('use_browser', 'browser_headless', 'browser_timeout'),
            'classes': ('collapse',),
        }),
        (_('Advanced'), {
            'fields': ('extra_config',),
            'classes': ('collapse',),
        }),
        (_('Audit'), {
            'fields': ('created_by', 'modified_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    actions = [
        'start_jobs',
        'stop_jobs',
        'pause_jobs',
        'enable_jobs',
        'disable_jobs',
        'reset_stats',
    ]
    
    def status_badge(self, obj):
        colors = {
            'pending': '#6c757d',
            'running': '#28a745',
            'paused': '#ffc107',
            'stopped': '#17a2b8',
            'completed': '#28a745',
            'failed': '#dc3545',
            'scheduled': '#6f42c1',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 12px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def progress_display(self, obj):
        if obj.max_iterations:
            pct = (obj.current_iteration / obj.max_iterations) * 100
            return format_html(
                '<div style="width: 100px; background-color: #e9ecef; border-radius: 4px;">'
                '<div style="width: {}%; background-color: #28a745; height: 20px; '
                'border-radius: 4px; text-align: center; color: white; font-size: 11px;">'
                '{}/{}</div></div>',
                min(pct, 100), obj.current_iteration, obj.max_iterations
            )
        return f"{obj.current_iteration} (unlimited)"
    progress_display.short_description = _('Progress')
    
    def stats_display(self, obj):
        return format_html(
            '<span title="Solved">✓ {}</span> / <span title="Failed">✗ {}</span> / '
            '<span title="Earnings">${:.4f}</span>',
            obj.total_solved, obj.total_failed, obj.total_earnings
        )
    stats_display.short_description = _('Stats')
    
    def success_rate_display(self, obj):
        return f"{obj.success_rate:.1f}%"
    success_rate_display.short_description = _('Success Rate')
    
    @admin.action(description='Start selected jobs')
    def start_jobs(self, request, queryset):
        from .tasks import start_job
        started = 0
        for job in queryset.filter(can_start=True):
            start_job.delay(job.id)
            started += 1
        self.message_user(request, f"Started {started} jobs.")
    
    @admin.action(description='Stop selected jobs')
    def stop_jobs(self, request, queryset):
        from .tasks import stop_job
        stopped = 0
        for job in queryset.filter(can_stop=True):
            stop_job.delay(job.id)
            stopped += 1
        self.message_user(request, f"Stopped {stopped} jobs.")
    
    @admin.action(description='Pause selected jobs')
    def pause_jobs(self, request, queryset):
        from .tasks import pause_job
        paused = 0
        for job in queryset.filter(can_pause=True):
            pause_job.delay(job.id)
            paused += 1
        self.message_user(request, f"Paused {paused} jobs.")
    
    @admin.action(description='Enable selected jobs')
    def enable_jobs(self, request, queryset):
        updated = queryset.update(is_enabled=True)
        self.message_user(request, f"Enabled {updated} jobs.")
    
    @admin.action(description='Disable selected jobs')
    def disable_jobs(self, request, queryset):
        updated = queryset.update(is_enabled=False)
        self.message_user(request, f"Disabled {updated} jobs.")
    
    @admin.action(description='Reset statistics for selected jobs')
    def reset_stats(self, request, queryset):
        updated = queryset.update(
            total_solved=0,
            total_failed=0,
            total_earnings=0,
            avg_solve_time=0,
            current_iteration=0,
        )
        self.message_user(request, f"Reset statistics for {updated} jobs.")


@admin.register(CaptchaLog)
class CaptchaLogAdmin(admin.ModelAdmin):
    list_display = [
        'status_icon',
        'captcha_type',
        'account',
        'website',
        'solve_time_display',
        'cost_display',
        'created_at',
    ]
    
    list_filter = [
        'is_success',
        'captcha_type',
        'account',
        'website',
    ]
    
    search_fields = [
        'error_message',
        'token',
        'api_request_id',
    ]
    
    readonly_fields = fields = [
        'job',
        'account',
        'website',
        'captcha_type',
        'is_success',
        'solve_time',
        'token',
        'error_message',
        'api_request_id',
        'cost',
        'ip_address',
        'proxy_used',
        'extra_data',
        'created_at',
    ]
    
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def status_icon(self, obj):
        if obj.is_success:
            return format_html('<span style="color: #28a745; font-size: 18px;">✓</span>')
        return format_html('<span style="color: #dc3545; font-size: 18px;">✗</span>')
    status_icon.short_description = _('Status')
    
    def solve_time_display(self, obj):
        color = '#28a745' if obj.solve_time < 30 else ('#ffc107' if obj.solve_time < 60 else '#dc3545')
        return format_html('<span style="color: {};">{:.1f}s</span>', color, obj.solve_time)
    solve_time_display.short_description = _('Solve Time')
    
    def cost_display(self, obj):
        return f"${obj.cost:.4f}"
    cost_display.short_description = _('Cost')