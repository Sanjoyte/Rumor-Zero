import hmac
import logging
import time
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

from apps.pipeline.processor import BATCH_SIZE, process_pending

logger = logging.getLogger(__name__)


# The tick stops taking new posts so it can answer inside cron-job.org's 30 s (ARCHITECTURE §6).
TICK_BUDGET_SECONDS = 25


def _require_cron_secret(request):
    """403 unless `X-RZ-Cron-Secret` matches. Compared as bytes in constant time, so a non-ASCII
    header is a plain 403, not a crash."""
    secret = request.headers.get("X-RZ-Cron-Secret", "")
    if not hmac.compare_digest(secret.encode(), settings.INTERNAL_CRON_SECRET.encode()):
        raise PermissionDenied()


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
        _require_cron_secret(request)

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


@method_decorator(never_cache, name="dispatch")
class TickView(_OpenView):
    """`POST /api/internal/tick/` (needs X-RZ-Cron-Secret): the hourly pipeline sweeper.

    cron-job.org calls it; it checks up to `BATCH_SIZE` fact posts the inline kick missed (one at
    a time, the first always, the next only while the worst case still fits in
    `TICK_BUDGET_SECONDS`) and answers `{"processed": n}`.
    """

    def post(self, request):
        _require_cron_secret(request)
        processed = process_pending(
            limit=BATCH_SIZE, deadline=time.monotonic() + TICK_BUDGET_SECONDS
        )
        return Response({"processed": processed})
