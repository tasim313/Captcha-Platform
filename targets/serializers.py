from rest_framework import serializers

from .models import ProxyConfiguration, TargetWebsite


class TargetWebsiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TargetWebsite
        fields = "__all__"
        read_only_fields = ("uuid", "created_at", "updated_at")


class ProxyConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProxyConfiguration
        fields = "__all__"
