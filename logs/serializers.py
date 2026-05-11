from rest_framework import serializers

from .models import ApiCallLog, LogEntry


class LogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LogEntry
        fields = "__all__"


class ApiCallLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiCallLog
        fields = "__all__"
