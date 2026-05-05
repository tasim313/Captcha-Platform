"""
REST API serializers for CAPTCHA jobs
"""
from rest_framework import serializers
from .models import CaptchaJob, CaptchaLog


class CaptchaJobListSerializer(serializers.ModelSerializer):
    """Serializer for listing jobs"""
    
    account_name = serializers.CharField(source='account.name', read_only=True)
    website_name = serializers.CharField(source='website.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    execution_mode_display = serializers.CharField(source='get_execution_mode_display', read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    
    class Meta:
        model = CaptchaJob
        fields = [
            'id', 'name', 'account', 'account_name', 'website', 'website_name',
            'status', 'status_display', 'execution_mode', 'execution_mode_display',
            'current_iteration', 'max_iterations', 'total_solved', 'total_failed',
            'success_rate', 'total_earnings', 'avg_solve_time', 'is_enabled',
            'last_run_at', 'next_run_at',
        ]


class CaptchaJobDetailSerializer(CaptchaJobListSerializer):
    """Detailed serializer for jobs"""
    
    captcha_type = serializers.CharField(source='website.captcha_type', read_only=True)
    
    class Meta(CaptchaJobListSerializer.Meta):
        fields = CaptchaJobListSerializer.Meta.fields + [
            'description', 'cron_expression', 'rate_limit_per_minute',
            'retry_count', 'retry_delay_seconds', 'timeout_seconds',
            'started_at', 'completed_at', 'celery_task_id',
            'proxy_type', 'proxy_url', 'use_browser', 'browser_headless',
            'can_start', 'can_pause', 'can_stop', 'can_restart',
            'extra_config', 'created_at', 'updated_at',
        ]


class CaptchaJobCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating jobs"""
    
    class Meta:
        model = CaptchaJob
        fields = [
            'name', 'description', 'account', 'website', 'execution_mode',
            'cron_expression', 'max_iterations', 'rate_limit_per_minute',
            'retry_count', 'retry_delay_seconds', 'timeout_seconds',
            'proxy_type', 'proxy_url', 'proxy_rotation_list',
            'use_browser', 'browser_headless', 'browser_timeout',
            'extra_config', 'is_enabled',
        ]
    
    def validate(self, attrs):
        # Validate cron expression for scheduled jobs
        if attrs.get('execution_mode') == 'scheduled' and not attrs.get('cron_expression'):
            raise serializers.ValidationError({
                'cron_expression': 'Cron expression is required for scheduled jobs'
            })
        return attrs


class CaptchaJobUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating jobs"""
    
    class Meta:
        model = CaptchaJob
        fields = [
            'name', 'description', 'execution_mode', 'cron_expression',
            'max_iterations', 'rate_limit_per_minute', 'retry_count',
            'retry_delay_seconds', 'timeout_seconds', 'proxy_type',
            'proxy_url', 'proxy_rotation_list', 'use_browser',
            'browser_headless', 'browser_timeout', 'extra_config', 'is_enabled',
        ]
        read_only_fields = ['status', 'account', 'website']


class CaptchaLogListSerializer(serializers.ModelSerializer):
    """Serializer for listing CAPTCHA logs"""
    
    captcha_type_display = serializers.CharField(source='get_captcha_type_display', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True, default=None)
    website_name = serializers.CharField(source='website.name', read_only=True, default=None)
    
    class Meta:
        model = CaptchaLog
        fields = [
            'id', 'job', 'account', 'account_name', 'website', 'website_name',
            'captcha_type', 'captcha_type_display', 'is_success', 'solve_time',
            'cost', 'error_message', 'created_at',
        ]


class JobControlSerializer(serializers.Serializer):
    """Serializer for job control actions"""
    action = serializers.ChoiceField(
        choices=['start', 'stop', 'pause', 'restart'],
        write_only=True
    )


class JobBulkControlSerializer(serializers.Serializer):
    """Serializer for bulk job control"""
    action = serializers.ChoiceField(
        choices=['start', 'stop', 'pause', 'restart'],
        write_only=True
    )
    job_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )