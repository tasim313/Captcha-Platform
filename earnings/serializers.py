from rest_framework import serializers

from .models import BalanceSnapshot, DailyEarning, EarningTransaction


class DailyEarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyEarning
        fields = "__all__"


class EarningTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EarningTransaction
        fields = "__all__"


class BalanceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalanceSnapshot
        fields = "__all__"
