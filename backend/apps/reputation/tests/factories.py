"""Helpers for the credibility tests. Most tests drive the real services (the pipeline's write,
the moderator actions, reposts, reports); `EventFactory` writes ledger rows directly for the read
endpoints, the admin and the audit command."""

from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.models import User
from apps.moderation.tests.factories import moderator_user, senior_user
from apps.pipeline.contract import PipelineResult
from apps.posts import services as post_services
from apps.posts.models import FlaggedReason, Post, PostStatus, PostType
from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory
from apps.reports.tests.factories import ReportFactory
from apps.reputation.models import EventKind, ReputationEvent
from apps.reputation.scoring import WEIGHTS
from apps.social.models import Repost

TRUE_95 = PipelineResult("true", Decimal("95"), {"stub": True, "rule": "#true"})
FALSE_95 = PipelineResult("false", Decimal("95"), {"stub": True, "rule": "#false"})
LOW_40 = PipelineResult("true", Decimal("40"), {"stub": True, "rule": "low"})


class EventFactory(factory.django.DjangoModelFactory):
    """One ledger row with the table's weights for its kind. It doesn't touch the user's stored
    score: tests that need both go through the services or `recompute_reputation`."""

    class Meta:
        model = ReputationEvent

    user = factory.SubFactory(VerifiedUserFactory)
    kind = EventKind.FACT_TRUE
    positive = factory.LazyAttribute(lambda row: WEIGHTS[row.kind][0])
    negative = factory.LazyAttribute(lambda row: WEIGHTS[row.kind][1])
    post = None
    score_after = 55
    created_at = factory.LazyFunction(timezone.now)


def reversal_of(row, **fields):
    """The reversal of `row`, as the service writes it."""
    values = {
        "user": row.user,
        "kind": EventKind.REVERSAL,
        "positive": -row.positive,
        "negative": -row.negative,
        "reverses": row,
        "post": row.post,
        "created_at": row.created_at + timedelta(seconds=1),
        **fields,
    }
    return EventFactory(**values)


def pending_fact(author=None, **fields):
    fields.setdefault("author", author or VerifiedUserFactory())
    fields.setdefault("status", PostStatus.PENDING)
    return PostFactory(post_type=PostType.FACT, **fields)


def reported_fact(author=None, *, pre=PostStatus.PENDING, flag=FlaggedReason.REPORTS, **fields):
    """A fact under review for reports, coming from `pre`."""
    fields.setdefault("author", author or VerifiedUserFactory())
    return PostFactory(
        post_type=PostType.FACT,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=flag,
        pre_review_status=pre,
        **fields,
    )


def reported_opinion(author=None, **fields):
    fields.setdefault("author", author or VerifiedUserFactory())
    return PostFactory(
        post_type=PostType.OPINION,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.PUBLISHED,
        **fields,
    )


def open_reports(post, n=1, **fields):
    """`n` open reports of `post` by fresh users; returns the reporters."""
    return [ReportFactory(post=post, **fields).reporter for _ in range(n)]


def reposted(post, user=None, *, status=None):
    """A repost of `post` made while it was `status` (its current status by default)."""
    return Repost.objects.create(
        user=user or VerifiedUserFactory(),
        post=post,
        status_at_repost=status or post.status,
    ).user


def label_by_pipeline(post, result=TRUE_95, now=None):
    """Run the pipeline's write for `post`, as if its first try had been claimed."""
    Post.objects.filter(pk=post.pk).update(
        pipeline_attempts=1, pipeline_next_attempt_at=timezone.now() + timedelta(minutes=5)
    )
    return post_services.record_pipeline_result(
        post.pk, result, claimed_attempts=1, now=now or timezone.now()
    )


def stored(user):
    """The user's stored (score, sample)."""
    return tuple(
        User.objects.filter(pk=user.pk).values_list("reputation_score", "reputation_sample").get()
    )


def kinds(user, *, include_reversed=True):
    """The user's ledger kinds, oldest first; with `include_reversed=False`, only the rows still
    standing (no reversal rows, nothing reversed)."""
    rows = ReputationEvent.objects.filter(user=user).order_by("created_at", "id")
    if not include_reversed:
        rows = rows.filter(reversed_by__isnull=True).exclude(kind=EventKind.REVERSAL)
    return list(rows.values_list("kind", flat=True))


__all__ = [
    "FALSE_95",
    "LOW_40",
    "TRUE_95",
    "EventFactory",
    "PostFactory",
    "ReportFactory",
    "UserFactory",
    "VerifiedUserFactory",
    "kinds",
    "label_by_pipeline",
    "moderator_user",
    "open_reports",
    "pending_fact",
    "reported_fact",
    "reported_opinion",
    "reposted",
    "reversal_of",
    "senior_user",
    "stored",
]
