from rest_framework import serializers

from .models import AccountAuditLog, CaptchaAccount, CaptchaServiceProvider


class CaptchaServiceProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaptchaServiceProvider
        fields = "__all__"


class CaptchaAccountSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=False)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    masked_api_key = serializers.CharField(source="get_masked_api_key", read_only=True)
    success_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = CaptchaAccount
        fields = [
            "id",
            "uuid",
            "name",
            "service_provider",
            "status",
            "max_concurrent_tasks",
            "daily_limit",
            "balance_usd",
            "balance_updated_at",
            "total_solved",
            "total_failed",
            "total_spent_usd",
            "metadata",
            "created_at",
            "updated_at",
            "masked_api_key",
            "success_rate",
            "api_key",
            "email",
            "password",
        ]
        read_only_fields = [
            "uuid",
            "balance_usd",
            "balance_updated_at",
            "total_solved",
            "total_failed",
            "total_spent_usd",
            "created_at",
            "updated_at",
            "masked_api_key",
            "success_rate",
        ]

    def create(self, validated_data):
        api_key = validated_data.pop("api_key", "")
        email = validated_data.pop("email", "")
        password = validated_data.pop("password", "")
        account = CaptchaAccount(**validated_data)
        if api_key:
            account.set_api_key(api_key)
        if email:
            account.set_email(email)
        if password:
            account.set_password(password)
        account.save()
        return account

    def update(self, instance, validated_data):
        api_key = validated_data.pop("api_key", None)
        email = validated_data.pop("email", None)
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if api_key:
            instance.set_api_key(api_key)
        if email:
            instance.set_email(email)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class AccountAuditLogSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = AccountAuditLog
        fields = "__all__"
        read_only_fields = fields
