"""
REST API views for CAPTCHA accounts
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django_filters.rest_framework import FilterSet, filters
from django.db.models import Q

from .models import CaptchaAccount, AccountAuditLog
from .serializers import (
    CaptchaAccountListSerializer,
    CaptchaAccountDetailSerializer,
    CaptchaAccountCreateSerializer,
    CaptchaAccountUpdateSerializer,
    AccountAuditLogSerializer,
    BalanceCheckSerializer,
    BalanceResponseSerializer,
)
from .services import AccountService


class CaptchaAccountFilter(FilterSet):
    """Filter set for CAPTCHA accounts"""
    
    status = filters.CharFilter(field_name='status')
    service = filters.CharFilter(field_name='service')
    is_available = filters.BooleanFilter(method='filter_is_available')
    min_balance = filters.NumberFilter(field_name='balance', lookup_expr='gte')
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = CaptchaAccount
        fields = ['status', 'service', 'is_default']
    
    def filter_is_available(self, queryset, name, value):
        if value:
            return queryset.filter(status='active', balance__gt=0)
        return queryset
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(notes__icontains=value)
        )


class CaptchaAccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing CAPTCHA solving accounts
    
    Provides CRUD operations plus custom actions for:
    - Checking balances
    - Getting available accounts
    - Account statistics
    """
    
    queryset = CaptchaAccount.objects.all()
    permission_classes = [IsAdminUser]
    filterset_class = CaptchaAccountFilter
    search_fields = ['name', 'notes']
    ordering_fields = ['name', 'balance', 'total_solved', 'success_rate', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CaptchaAccountListSerializer
        elif self.action == 'retrieve':
            return CaptchaAccountDetailSerializer
        elif self.action in ['create']:
            return CaptchaAccountCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CaptchaAccountUpdateSerializer
        return CaptchaAccountDetailSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(modified_by=self.request.user)
    
    @action(detail=False, methods=['post'], url_path='check-balances')
    def check_balances(self, request):
        """Check balances for specified or all active accounts"""
        serializer = BalanceCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        account_ids = serializer.validated_data.get('account_ids')
        service = AccountService()
        
        if account_ids:
            accounts = CaptchaAccount.objects.filter(id__in=account_ids)
        else:
            accounts = CaptchaAccount.objects.filter(status='active')
        
        results = []
        errors = []
        
        for account in accounts:
            try:
                balance = service.update_balance(account)
                results.append({
                    'account_id': account.id,
                    'account_name': account.name,
                    'balance': balance,
                    'currency': 'USD',
                })
            except Exception as e:
                errors.append({
                    'account_id': account.id,
                    'account_name': account.name,
                    'error': str(e),
                })
        
        response_data = {
            'results': results,
            'errors': errors,
            'total_checked': len(accounts),
            'successful': len(results),
        }
        
        return Response(response_data)
    
    @action(detail=False, methods=['get'], url_path='available')
    def available(self, request):
        """Get all accounts available for use (active with balance)"""
        accounts = CaptchaAccount.objects.filter(
            status='active',
            balance__gt=0
        ).order_by('-balance')
        
        serializer = CaptchaAccountListSerializer(accounts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='statistics')
    def statistics(self, request, pk=None):
        """Get detailed statistics for a specific account"""
        account = self.get_object()
        
        from django.db.models import Count, Avg, Sum
        from earnings.models import EarningRecord
        from captcha_jobs.models import CaptchaLog
        
        # Get recent performance data
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        periods = {
            'today': now - timedelta(days=1),
            'week': now - timedelta(days=7),
            'month': now - timedelta(days=30),
        }
        
        stats = {}
        for period_name, start_date in periods.items():
            logs = CaptchaLog.objects.filter(
                account=account,
                created_at__gte=start_date
            )
            
            stats[period_name] = {
                'total': logs.count(),
                'successful': logs.filter(is_success=True).count(),
                'failed': logs.filter(is_success=False).count(),
                'avg_time': logs.filter(is_success=True).aggregate(
                    avg=Avg('solve_time')
                )['avg'] or 0,
                'earnings': EarningRecord.objects.filter(
                    account=account,
                    created_at__gte=start_date
                ).aggregate(total=Sum('amount'))['total'] or 0,
            }
        
        return Response({
            'account': CaptchaAccountDetailSerializer(account).data,
            'statistics': stats,
        })
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete account instead of hard delete"""
        account = self.get_object()
        
        from accounts.services import log_account_change
        log_account_change(
            account=account,
            action='deleted',
            old_values={'name': account.name},
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        account.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing account audit logs (read-only)
    """
    
    queryset = AccountAuditLog.objects.all()
    serializer_class = AccountAuditLogSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['account', 'action', 'changed_by']
    search_fields = ['details', 'account__name']
    ordering_fields = ['created_at']
    ordering = ['-created_at']