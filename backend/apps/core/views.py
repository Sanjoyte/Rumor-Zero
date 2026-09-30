import hmac
import logging
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class _OpenView(APIView):
    """No authentication, permission or throttle classes: these views never touch the session."""

    authentication_classes = []
    permission_classes = []
    throttle_classes = []


@method_decorator(never_cache, name="dispatch")
class HealthView(_OpenView):
    """Liveness probe for UptimeRobot/Render. Touches neither the database nor the session."""

    def get(self, request):
        return Response({"status": "ok"})


def _check_database():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _check_cache():
    key = f"health:{uuid.uuid4().hex}"
    cache.set(key, "ok", 10)
    try:
        if cache.get(key) != "ok":
            raise RuntimeError("cache round trip failed")
    finally:
        cache.delete(key)


@method_decorator(never_cache, name="dispatch")
class DeepHealthView(_OpenView):
    """Database + cache check for the daily GitHub Actions ping. Needs X-RZ-Cron-Secret."""

    def get(self, request):
        secret = request.headers.get("X-RZ-Cron-Secret", "")
        if not hmac.compare_digest(secret.encode(), settings.INTERNAL_CRON_SECRET.encode()):
            raise PermissionDenied()

        results = {}
        for component, check in (("database", _check_database), ("cache", _check_cache)):
            try:
                check()
                results[component] = "ok"
            except Exception as exc:
                # Log only the class name: messages can contain connection strings.
                logger.warning("Deep health check failed: %s (%s)", component, type(exc).__name__)
                results[component] = "error"

        healthy = all(value == "ok" for value in results.values())
        return Response(
            {"status": "ok" if healthy else "error", **results},
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
