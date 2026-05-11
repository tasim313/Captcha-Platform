from django.contrib import admin

from .models import ProxyConfiguration, TargetWebsite


@admin.register(TargetWebsite)
class TargetWebsiteAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "captcha_type", "is_active")
    list_filter = ("captcha_type", "is_active")
    search_fields = ("name", "url")


@admin.register(ProxyConfiguration)
class ProxyConfigurationAdmin(admin.ModelAdmin):
    list_display = ("name", "proxy_type", "rotation_strategy", "is_active")
    list_filter = ("proxy_type", "rotation_strategy", "is_active")
