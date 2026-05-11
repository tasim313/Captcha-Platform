from django.contrib import admin

from .models import ApiCallLog, LogEntry


admin.site.register(LogEntry)
admin.site.register(ApiCallLog)
