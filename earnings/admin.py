from django.contrib import admin

from .models import BalanceSnapshot, DailyEarning, EarningTransaction


admin.site.register(DailyEarning)
admin.site.register(EarningTransaction)
admin.site.register(BalanceSnapshot)
