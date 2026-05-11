from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .services import build_dashboard_snapshot


def dashboard_home(request):
    return render(request, "dashboard/main.html", {"snapshot": build_dashboard_snapshot()})


@api_view(["GET"])
@permission_classes([IsAdminUser])
def dashboard_metrics(_request):
    return Response(build_dashboard_snapshot())
