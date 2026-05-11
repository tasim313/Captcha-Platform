from django.contrib import admin

from .models import Withdrawal, WithdrawalMethod


admin.site.register(WithdrawalMethod)
admin.site.register(Withdrawal)
