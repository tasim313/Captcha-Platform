from rest_framework import serializers

from .models import CaptchaJob, JobExecution


class JobExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobExecution
        fields = "__all__"
        read_only_fields = fields


class CaptchaJobSerializer(serializers.ModelSerializer):
    executions_count = serializers.SerializerMethodField()

    class Meta:
        model = CaptchaJob
        fields = "__all__"
        read_only_fields = (
            "uuid",
            "iteration_count",
            "last_started_at",
            "last_stopped_at",
            "last_error_at",
            "last_error_message",
            "celery_task_id",
            "worker_pid",
            "created_at",
            "updated_at",
            "executions_count",
        )

    def get_executions_count(self, obj):
        return obj.executions.count()
