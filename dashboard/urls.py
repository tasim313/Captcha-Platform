from django.urls import path

from .views import dashboard_home, dashboard_metrics

urlpatterns = [
    path("", dashboard_home, name="dashboard-home"),
    path("api/metrics/", dashboard_metrics, name="dashboard-metrics"),
]
