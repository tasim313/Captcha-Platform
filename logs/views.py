from rest_framework import permissions, viewsets

from .models import ApiCallLog, LogEntry
from .serializers import ApiCallLogSerializer, LogEntrySerializer


class LogEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LogEntry.objects.select_related("job", "job_execution", "account").all()
    serializer_class = LogEntrySerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["source", "level", "job", "account"]


class ApiCallLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ApiCallLog.objects.select_related("account").all()
    serializer_class = ApiCallLogSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["service_name", "account", "is_success"]
