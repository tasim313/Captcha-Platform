"""
Admin configuration for CAPTCHA accounts
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import CaptchaAccount, AccountAuditLog


@admin.register(CaptchaAccount)
class CaptchaAccountAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'service',
        'status_badge',
        'masked_api_key_display',
        'balance_display',
        'total_solved',
        'success_rate_display',
        'is_default',
        'created_at',
    ]
    
    list_filter = [
        'service',
        'status',
        'is_default',
    ]
    
    search_fields = [
        'name',
        'email_encrypted',  # Encrypted but can search for pattern
        'notes',
    ]
    
    readonly_fields = [
        'balance_last_checked',
        'total_spent',
        'total_solved',
        'success_rate',
        'created_at',
        'updated_at',
        'masked_api_key_display',
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'service', 'status', 'is_default')
        }),
        (_('Credentials (Encrypted)'), {
            'fields': (
                'api_key_input',
                'email_input',
                'password_input',
                'masked_api_key_display',
            ),
            'description': _('Credentials are encrypted at rest. Enter new values to update.')
        }),
        (_('Usage Statistics'), {
            'fields': (
                'balance',
                'balance_last_checked',
                'total_spent',
                'total_solved',
                'success_rate',
                'rate_limit_per_minute',
            ),
            'classes': ('collapse',),
        }),
        (_('Additional'), {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
        (_('Audit'), {
            'fields': ('created_by', 'modified_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    actions = [
        'check_balances',
        'activate_accounts',
        'deactivate_accounts',
    ]
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form to handle encrypted fields"""
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['api_key_input'] = forms.CharField(
            required=False,
            widget=forms.PasswordInput,
            label=_('API Key'),
            help_text=_('Leave blank to keep current value')
        )
        form.base_fields['email_input'] = forms.EmailField(
            required=False,
            label=_('Email'),
            help_text=_('Leave blank to keep current value')
        )
        form.base_fields['password_input'] = forms.CharField(
            required=False,
            widget=forms.PasswordInput,
            label=_('Password'),
            help_text=_('Leave blank to keep current value')
        )
        return form
    
    def save_model(self, request, obj, form, change):
        """Handle encryption on save"""
        from core.encryption import encryption_service
        from core.utils import mask_sensitive_data
        from .services import log_account_change
        
        old_values = {}
        new_values = {}
        
        if change:
            # Track changes for audit
            if hasattr(form, 'cleaned_data'):
                if form.cleaned_data.get('api_key_input'):
                    old_values['api_key'] = obj.masked_api_key
                    obj.api_key = form.cleaned_data['api_key_input']
                    new_values['api_key'] = mask_sensitive_data(obj.api_key)
                
                if form.cleaned_data.get('password_input'):
                    old_values['password'] = '****'
                    obj.password = form.cleaned_data['password_input']
                    new_values['password'] = '****'
                
                if form.cleaned_data.get('email_input'):
                    old_values['email'] = mask_sensitive_data(obj.email) if obj.email else ''
                    obj.email = form.cleaned_data['email_input']
                    new_values['email'] = mask_sensitive_data(obj.email)
        
        # Set created/modified by
        if not change:
            obj.created_by = request.user
        obj.modified_by = request.user
        
        super().save_model(request, obj, form, change)
        
        # Log changes
        if old_values or new_values:
            log_account_change(
                account=obj,
                action='api_key_changed' if 'api_key' in new_values else 'updated',
                old_values=old_values,
                new_values=new_values,
                user=request.user,
                ip_address=self._get_client_ip(request)
            )
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'active': '#28a745',
            'inactive': '#6c757d',
            'suspended': '#ffc107',
            'banned': '#dc3545',
            'error': '#17a2b8',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def masked_api_key_display(self, obj):
        return obj.masked_api_key
    masked_api_key_display.short_description = _('API Key (Masked)')
    
    def balance_display(self, obj):
        color = '#28a745' if obj.balance > 5 else ('#ffc107' if obj.balance > 1 else '#dc3545')
        return format_html(
            '<span style="color: {}; font-weight: bold;">${:.2f}</span>',
            color,
            obj.balance
        )
    balance_display.short_description = _('Balance')
    
    def success_rate_display(self, obj):
        color = '#28a745' if obj.success_rate > 90 else ('#ffc107' if obj.success_rate > 70 else '#dc3545')
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            obj.success_rate
        )
    success_rate_display.short_description = _('Success Rate')
    
    @admin.action(description='Check balances for selected accounts')
    def check_balances(self, request, queryset):
        from .services import AccountService
        service = AccountService()
        updated = 0
        for account in queryset:
            try:
                service.update_balance(account)
                updated += 1
            except Exception as e:
                self.message_user(request, f"Error checking {account.name}: {str(e)}", level='ERROR')
        self.message_user(request, f"Balance checked for {updated} accounts.")
    
    @admin.action(description='Activate selected accounts')
    def activate_accounts(self, request, queryset):
        from accounts.models import AccountStatus
        updated = queryset.update(status=AccountStatus.ACTIVE)
        self.message_user(request, f"{updated} accounts activated.")
    
    @admin.action(description='Deactivate selected accounts')
    def deactivate_accounts(self, request, queryset):
        from accounts.models import AccountStatus
        updated = queryset.update(status=AccountStatus.INACTIVE)
        self.message_user(request, f"{updated} accounts deactivated.")
    
    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


@admin.register(AccountAuditLog)
class AccountAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'account',
        'action',
        'changed_by',
        'ip_address',
        'created_at',
    ]
    
    list_filter = [
        'action',
    ]
    
    search_fields = [
        'account__name',
        'changed_by__username',
        'details',
    ]
    
    readonly_fields = [
        'account',
        'action',
        'old_values',
        'new_values',
        'changed_by',
        'ip_address',
        'details',
        'created_at',
    ]
    
    fieldsets = (
        (_('Change Details'), {
            'fields': ('account', 'action', 'changed_by', 'ip_address', 'created_at')
        }),
        (_('Value Changes'), {
            'fields': ('old_values', 'new_values', 'details')
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# Import forms at the end to avoid circular imports
from django import forms