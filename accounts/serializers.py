"""
REST API serializers for CAPTCHA accounts
"""
from rest_framework import serializers
from .models import CaptchaAccount, AccountAuditLog


class CaptchaAccountListSerializer(serializers.ModelSerializer):
    """Serializer for listing accounts (no sensitive data)"""
    
    masked_api_key = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    service_display = serializers.CharField(source='get_service_display', read_only=True)
    
    class Meta:
        model = CaptchaAccount
        fields = [
            'id', 'name', 'service', 'service_display', 'status', 'status_display',
            'masked_api_key', 'balance', 'balance_last_checked', 'total_solved',
            'success_rate', 'is_default', 'rate_limit_per_minute', 'created_at',
        ]
        read_only_fields = ['balance', 'total_solved', 'success_rate', 'created_at']
    
    def get_masked_api_key(self, obj):
        return obj.masked_api_key


class CaptchaAccountDetailSerializer(CaptchaAccountListSerializer):
    """Detailed serializer with more fields"""
    
    total_spent = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    notes = serializers.CharField(read_only=True)
    
    class Meta(CaptchaAccountListSerializer.Meta):
        fields = CaptchaAccountListSerializer.Meta.fields + [
            'total_spent', 'notes', 'updated_at',
        ]


class CaptchaAccountCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating accounts"""
    
    api_key = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model = CaptchaAccount
        fields = [
            'name', 'service', 'api_key', 'email', 'password',
            'status', 'rate_limit_per_minute', 'is_default', 'notes',
        ]
    
    def create(self, validated_data):
        api_key = validated_data.pop('api_key')
        email = validated_data.pop('email', None)
        password = validated_data.pop('password', None)
        
        account = CaptchaAccount(**validated_data)
        account.api_key = api_key
        if email:
            account.email = email
        if password:
            account.password = password
        account.save()
        
        # Log creation
        from accounts.services import log_account_change
        log_account_change(
            account=account,
            action='created',
            new_values={'name': account.name, 'service': account.service},
            user=self.context['request'].user
        )
        
        return account


class CaptchaAccountUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating accounts"""
    
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model = CaptchaAccount
        fields = [
            'name', 'service', 'status', 'api_key', 'email', 'password',
            'rate_limit_per_minute', 'is_default', 'notes',
        ]
    
    def update(self, instance, validated_data):
        from core.utils import mask_sensitive_data
        from accounts.services import log_account_change
        
        old_values = {}
        new_values = {}
        
        if 'api_key' in validated_data and validated_data['api_key']:
            old_values['api_key'] = instance.masked_api_key
            instance.api_key = validated_data.pop('api_key')
            new_values['api_key'] = mask_sensitive_data(instance.api_key)
        
        if 'password' in validated_data and validated_data['password']:
            old_values['password'] = '****'
            instance.password = validated_data.pop('password')
            new_values['password'] = '****'
        
        if 'email' in validated_data and validated_data['email']:
            old_values['email'] = mask_sensitive_data(instance.email) if instance.email else ''
            instance.email = validated_data.pop('email')
            new_values['email'] = mask_sensitive_data(instance.email)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Log changes
        if old_values or new_values:
            action = 'api_key_changed' if 'api_key' in new_values else (
                'password_changed' if 'password' in new_values else 'updated'
            )
            log_account_change(
                account=instance,
                action=action,
                old_values=old_values,
                new_values=new_values,
                user=self.context['request'].user
            )
        
        return instance


class AccountAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for account audit logs"""
    
    account_name = serializers.CharField(source='account.name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    changed_by_name = serializers.CharField(source='changed_by.username', read_only=True, default=None)
    
    class Meta:
        model = AccountAuditLog
        fields = [
            'id', 'account', 'account_name', 'action', 'action_display',
            'old_values', 'new_values', 'changed_by', 'changed_by_name',
            'ip_address', 'details', 'created_at',
        ]
        read_only_fields = fields


class BalanceCheckSerializer(serializers.Serializer):
    """Serializer for balance check request"""
    account_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text='List of account IDs to check. If empty, checks all active accounts.'
    )


class BalanceResponseSerializer(serializers.Serializer):
    """Serializer for balance check response"""
    account_id = serializers.IntegerField()
    account_name = serializers.CharField()
    balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(default='USD')