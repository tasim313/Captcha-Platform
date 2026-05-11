from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from automation.tasks import pause_job, restart_job, start_job, stop_job

from .models import CaptchaJob, JobExecution
from .serializers import CaptchaJobSerializer, JobExecutionSerializer


class CaptchaJobViewSet(viewsets.ModelViewSet):
    queryset = CaptchaJob.objects.select_related("account", "target", "proxy_config").all()
    serializer_class = CaptchaJobSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["status", "execution_mode", "priority", "account"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at", "last_started_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def start(self, _request, pk=None):
        job = self.get_object()
        async_result = start_job.delay(job.id)
        return Response({"queued": True, "task_id": async_result.id})

    @action(detail=True, methods=["post"])
    def pause(self, _request, pk=None):
        job = self.get_object()
        async_result = pause_job.delay(job.id)
        return Response({"queued": True, "task_id": async_result.id})

    @action(detail=True, methods=["post"])
    def stop(self, _request, pk=None):
        job = self.get_object()
        async_result = stop_job.delay(job.id)
        return Response({"queued": True, "task_id": async_result.id})

    @action(detail=True, methods=["post"])
    def restart(self, _request, pk=None):
        job = self.get_object()
        async_result = restart_job.delay(job.id)
        return Response({"queued": True, "task_id": async_result.id})


class JobExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JobExecution.objects.select_related("job").all()
    serializer_class = JobExecutionSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["job", "status"]
