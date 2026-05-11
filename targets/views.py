from rest_framework import permissions, viewsets

from .models import ProxyConfiguration, TargetWebsite
from .serializers import ProxyConfigurationSerializer, TargetWebsiteSerializer


class TargetWebsiteViewSet(viewsets.ModelViewSet):
    queryset = TargetWebsite.objects.all()
    serializer_class = TargetWebsiteSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["captcha_type", "is_active"]
    search_fields = ["name", "url"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ProxyConfigurationViewSet(viewsets.ModelViewSet):
    queryset = ProxyConfiguration.objects.all()
    serializer_class = ProxyConfigurationSerializer
    permission_classes = [permissions.IsAdminUser]
