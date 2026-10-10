from datetime import UTC, datetime, timedelta

import factory
from django.utils import timezone

from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory
from apps.reports.models import Report, ReportReason, ReportStatus

# A fixed "now" for the tests that control time: services take `now`, so nothing depends on the
# clock and every boundary is exact.
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def aged_user(hours=48, now=NOW, **fields):
    """A verified user whose account is `hours` old at `now` (the default is past the 24 h
    minimum, so their report counts)."""
    return VerifiedUserFactory(created_at=now - timedelta(hours=hours), **fields)


class ReportFactory(factory.django.DjangoModelFactory):
    """An open, counting report by a verified user. `created_at` defaults to the real now: pass
    `created_at=NOW - …` in a test that works at `NOW`."""

    class Meta:
        model = Report

    post = factory.SubFactory(PostFactory)
    reporter = factory.SubFactory(VerifiedUserFactory)
    reason = ReportReason.INACCURATE
    details = ""
    counts_toward_threshold = True
    created_at = factory.LazyFunction(timezone.now)

    class Params:
        dismissed = factory.Trait(
            status=ReportStatus.DISMISSED, resolved_at=factory.LazyFunction(timezone.now)
        )
        actioned = factory.Trait(
            status=ReportStatus.ACTIONED, resolved_at=factory.LazyFunction(timezone.now)
        )
        not_counting = factory.Trait(counts_toward_threshold=False)


__all__ = ["NOW", "ReportFactory", "UserFactory", "VerifiedUserFactory", "aged_user"]
