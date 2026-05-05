"""
REST API views for CAPTCHA jobs
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django_filters.rest_framework import FilterSet, filters
from django.db.models import Q

from .models import CaptchaJob, CaptchaLog
from .serializers import (
    CaptchaJobListSerializer,
    CaptchaJobDetailSerializer,
    CaptchaJobCreateSerializer,
    CaptchaJobUpdateSerializer,
    CaptchaLogListSerializer,
    JobControlSerializer,
    JobBulkControlSerializer,
)
from .tasks import start_job, stop_job, pause_job, restart_job


class CaptchaJobFilter(FilterSet):
    """Filter set for CAPTCHA jobs"""
    
    status = filters.CharFilter(field_name='status')
    execution_mode = filters.CharFilter(field_name='execution_mode')
    is_enabled = filters.BooleanFilter(field_name='is_enabled')
    account = filters.NumberFilter(field_name='account')
    website = filters.NumberFilter(field_name='website')
    has_active_task = filters.BooleanFilter(method='filter_has_active_task')
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = CaptchaJob
        fields = ['status', 'execution_mode', 'is_enabled', 'account', 'website']
    
    def filter_has_active_task(self, queryset, name, value):
        if value:
            return queryset.exclude(celery_task_id='').exclude(celery_task_id__isnull=True)
        return queryset.filter(Q(celery_task_id='') | Q(celery_task_id__isnull=True))
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(account__name__icontains=value) |
            Q(website__name__icontains=value)
        )


class CaptchaJobViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing CAPTCHA jobs
    
    Provides CRUD operations plus custom actions for:
    - Job control (start, stop, pause, restart)
    - Bulk operations
    - Job statistics
    """
    
    queryset = CaptchaJob.objects.all()
    permission_classes = [IsAdminUser]
    filterset_class = CaptchaJobFilter
    search_fields = ['name', 'description']
    ordering_fields = [
        'name', 'status', 'total_solved', 'total_earnings',
        'success_rate', 'last_run_at', 'created_at'
    ]
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CaptchaJobListSerializer
        elif self.action == 'retrieve':
            return CaptchaJobDetailSerializer
        elif self.action == 'create':
            return CaptchaJobCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CaptchaJobUpdateSerializer
        return CaptchaJobDetailSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(modified_by=self.request.user)
    
    @action(detail=True, methods=['post'], url_path='control')
    def control(self, request, pk=None):
        """
        Control a single job (start, stop, pause, restart)
        
        POST /api/jobs/{id}/control/
        Body: {"action": "start|stop|pause|restart"}
        """
        job = self.get_object()
        serializer = JobControlSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action = serializer.validated_data['action']
        
        action_map = {
            'start': start_job,
            'stop': stop_job,
            'pause': pause_job,
            'restart': restart_job,
        }
        
        task = action_map[action]
        result = task.delay(job.id)
        
        return Response({
            'job_id': job.id,
            'job_name': job.name,
            'action': action,
            'celery_task_id': result.id,
            'message': f"Job {action} initiated"
        })
    
    @action(detail=False, methods=['post'], url_path='bulk-control')
    def bulk_control(self, request):
        """
        Control multiple jobs at once
        
        POST /api/jobs/bulk-control/
        Body: {"action": "start|stop|pause|restart", "job_ids": [1, 2, 3]}
        """
        serializer = JobBulkControlSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action = serializer.validated_data['action']
        job_ids = serializer.validated_data['job_ids']
        
        action_map = {
            'start': start_job,
            'stop': stop_job,
            'pause': pause_job,
            'restart': restart_job,
        }
        
        task = action_map[action]
        results = []
        
        for job_id in job_ids:
            try:
                result = task.delay(job_id)
                results.append({
                    'job_id': job_id,
                    'celery_task_id': result.id,
                    'status': 'queued'
                })
            except Exception as e:
                results.append({
                    'job_id': job_id,
                    'error': str(e),
                    'status': 'failed'
                })
        
        return Response({
            'action': action,
            'results': results,
            'total': len(job_ids),
            'queued': sum(1 for r in results if r['status'] == 'queued'),
        })
    
    @action(detail=False, methods=['get'], url_path='running')
    def running(self, request):
        """Get all currently running jobs"""
        jobs = CaptchaJob.objects.filter(status='running')
        serializer = CaptchaJobListSerializer(jobs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='logs')
    def logs(self, request, pk=None):
        """Get logs for a specific job"""
        job = self.get_object()
        logs = CaptchaLog.objects.filter(job=job).select_related('account', 'website')
        
        # Apply filters from query params
        is_success = request.query_params.get('is_success')
        if is_success is not None:
            logs = logs.filter(is_success=is_success.lower() == 'true')
        
        limit = int(request.query_params.get('limit', 100))
        logs = logs[:limit]
        
        serializer = CaptchaLogListSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='statistics')
    def statistics(self, request, pk=None):
        """Get detailed statistics for a job"""
        job = self.get_object()
        
        from django.db.models import Count, Avg, Sum, Q
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        
        stats = {
            'total_solved': job.total_solved,
            'total_failed': job.total_failed,
            'success_rate': job.success_rate,
            'total_earnings': float(job.total_earnings),
            'avg_solve_time': job.avg_solve_time,
            'current_iteration': job.current_iteration,
        }
        
        # Time-based statistics
        for period, days in [('today', 1), ('week', 7), ('month', 30)]:
            start = now - timedelta(days=days)
            logs = CaptchaLog.objects.filter(job=job, created_at__gte=start)
            
            stats[period] = {
                'solved': logs.filter(is_success=True).count(),
                'failed': logs.filter(is_success=False).count(),
                'avg_time': logs.filter(is_success=True).aggregate(
                    avg=Avg('solve_time')
                )['avg'] or 0,
                'earnings': logs.filter(is_success=True).aggregate(
                    total=Sum('cost')
                )['total'] or 0,
            }
        
        # Error breakdown
        error_logs = CaptchaLog.objects.filter(
            job=job,
            is_success=False
        ).values('error_message').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        stats['top_errors'] = list(error_logs)
        
        return Response(stats)


class CaptchaLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing CAPTCHA logs (read-only)
    """
    
    queryset = CaptchaLog.objects.select_related('account', 'website', 'job')
    serializer_class = CaptchaLogListSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['job', 'account', 'website', 'is_success', 'captcha_type']
    search_fields = ['error_message', 'token', 'api_request_id']
    ordering_fields = ['created_at', 'solve_time', 'cost']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Optimize queryset with select_related"""
        return super().get_queryset()