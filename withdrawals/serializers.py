from rest_framework import serializers

from .models import Withdrawal, WithdrawalMethod


class WithdrawalMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithdrawalMethod
        fields = "__all__"


class WithdrawalSerializer(serializers.ModelSerializer):
    destination_identifier = serializers.CharField(write_only=True)
    decrypted_destination = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Withdrawal
        fields = "__all__"
        read_only_fields = ("uuid", "fee_usd", "net_amount_usd", "created_at", "updated_at", "processed_at")

    def get_decrypted_destination(self, obj):
        return obj.get_destination_identifier()
