from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/accounts/", include("accounts.urls")),
    path("api/targets/", include("targets.urls")),
    path("api/jobs/", include("captcha_jobs.urls")),
    path("api/earnings/", include("earnings.urls")),
    path("api/logs/", include("logs.urls")),
    path("api/withdrawals/", include("withdrawals.urls")),
    path("dashboard/", include("dashboard.urls")),
]
