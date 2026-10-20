"""Shared helpers for the pipeline tests: pinned settings, facts in the queue, fake clients."""

import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.utils import timezone

from apps.core.models import PlatformSettings
from apps.core.services import get_platform_settings
from apps.pipeline.clients import PipelineError, StubPipelineClient
from apps.pipeline.contract import PipelineResult
from apps.posts.models import FlaggedReason, PostStatus
from apps.posts.tests.factories import PostFactory
from conftest import pin_emergency_settings


@pytest.fixture
def pipeline_cfg(db):
    """Pin what the pipeline and the reports read. The seed comes from the developer's own
    `backend/.env`, so tests must not rely on it; the row is saved (`.update()` would skip the
    cache invalidation) and healed with `get_or_create` after a `transaction=True` flush."""

    def set_values(*, confidence_threshold=85, report_threshold=5):
        row, _ = PlatformSettings.objects.get_or_create(
            pk=1, defaults=settings.PLATFORM_SETTINGS_SEED
        )
        row.confidence_threshold = confidence_threshold
        row.report_threshold = report_threshold
        row.report_window_hours = 24
        row.report_min_account_age_hours = 24
        row.save()
        return get_platform_settings()

    set_values()
    return set_values


def fact(content="A claim to check", *, age_seconds=60, **fields):
    """A pending fact in the queue, `age_seconds` old (give each post in a test its own age) unless
    `created_at` is given."""
    fields.setdefault("created_at", timezone.now() - timedelta(seconds=age_seconds))
    return PostFactory(fact=True, content=content, **fields)


def reported_fact(content="A reported claim", **fields):
    """A fact that reports sent to review before the pipeline answered."""
    return fact(
        content,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.PENDING,
        **fields,
    )


class FakeClient:
    """A pipeline client for tests. It answers `answer(request)` (a `PipelineResult`, or it
    raises) and records every request; `during(request)` runs inside the call, while the try is
    in flight (no transaction is open then). Thread-safe enough for the race tests."""

    def __init__(self, answer=None, *, during=None, max_seconds=0):
        self.answer = answer or StubPipelineClient().check
        self.during = during
        self.max_seconds = max_seconds
        self.requests = []
        self._lock = threading.Lock()

    def check(self, request):
        with self._lock:
            self.requests.append(request)
        if self.during:
            self.during(request)
        return self.answer(request)

    @property
    def post_ids(self):
        return [request.post_id for request in self.requests]


def answering(verdict, confidence, **kwargs):
    raw = {"fake": True}
    return FakeClient(
        lambda request: PipelineResult(verdict, Decimal(str(confidence)), raw), **kwargs
    )


def failing(kind="timeout", detail="no answer in time", **kwargs):
    def answer(request):
        raise PipelineError(kind, detail)

    return FakeClient(answer, **kwargs)


@pytest.fixture(autouse=True)
def _pinned_emergency_settings(request):
    """The six emergency settings at their defaults in every database test (Part 11C): the seed
    comes from the developer's own `backend/.env`."""
    pin_emergency_settings(request)
