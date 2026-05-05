"""
Admin configuration for target websites
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import TargetWebsite


@admin.register(TargetWebsite)
class TargetWebsiteAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'url_short',
        'captcha_type_badge',
        'status_badge',
        'success_rate_display',
        'avg_solve_time_display',
        'total_attempts',
        'created_at',
    ]
    
    list_filter = [
        'captcha_type',
        'status',
        'difficulty',
    ]
    
    search_fields = [
        'name',
        'url',
        'site_key',
    ]
    
    readonly_fields = [
        'avg_solve_time',
        'success_rate',
        'total_attempts',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'url', 'page_url', 'status', 'difficulty')
        }),
        (_('CAPTCHA Configuration'), {
            'fields': (
                'captcha_type',
                'site_key',
                'selector',
                'submit_selector',
            )
        }),
        (_('Statistics'), {
            'fields': (
                'avg_solve_time',
                'success_rate',
                'total_attempts',
            ),
            'classes': ('collapse',),
        }),
        (_('Advanced'), {
            'fields': ('custom_headers', 'extra_data', 'notes'),
            'classes': ('collapse',),
        }),
    )
    
    def url_short(self, obj):
        if len(obj.url) > 50:
            return obj.url[:47] + '...'
        return obj.url
    url_short.short_description = _('URL')
    
    def captcha_type_badge(self, obj):
        colors = {
            'recaptcha_v2': '#4285F4',
            'recaptcha_v3': '#4285F4',
            'hcaptcha': '#1251D3',
            'image_captcha': '#28a745',
            'turnstile': '#F6821F',
            'funcaptcha': '#6C3483',
            'geetest': '#E74C3C',
        }
        color = colors.get(obj.captcha_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            obj.get_captcha_type_display()
        )
    captcha_type_badge.short_description = _('CAPTCHA Type')
    
    def status_badge(self, obj):
        colors = {
            'active': '#28a745',
            'inactive': '#6c757d',
            'blocked': '#dc3545',
            'maintenance': '#ffc107',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def success_rate_display(self, obj):
        color = '#28a745' if obj.success_rate > 90 else ('#ffc107' if obj.success_rate > 70 else '#dc3545')
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            obj.success_rate
        )
    success_rate_display.short_description = _('Success Rate')
    
    def avg_solve_time_display(self, obj):
        return f"{obj.avg_solve_time:.1f}s" if obj.avg_solve_time > 0 else "-"
    avg_solve_time_display.short_description = _('Avg Time')