"""The five services (ARCHITECTURE §4): each one against each starting state, the audit row, the
reports, and "a refusal writes nothing"."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.core.services import get_platform_settings
from apps.moderation import services
from apps.moderation.models import ActionKind, ModerationAction
from apps.moderation.rules import DELETED
from apps.moderation.tests.factories import moderator_user
from apps.posts.models import FlaggedReason, Post, PostStatus, PostType, VerdictSource
from apps.posts.tests.factories import PostFactory
from apps.reports.models import Report, ReportStatus
from apps.reports.services import counting_reports
from apps.reports.tests.factories import ReportFactory

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
STARTED = NOW - timedelta(hours=5)


def reviewed(
    *,
    post_type=PostType.FACT,
    flag=FlaggedReason.REPORTS,
    pre=PostStatus.PENDING,
    reports=3,
    **fields,
):
    """A post under review with `reports` open reports, as `enter_review` leaves it."""
    fields.setdefault("review_started_at", STARTED)
    post = PostFactory(
        post_type=post_type,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=flag,
        pre_review_status=pre,
        report_count=reports,
        **fields,
    )
    for _ in range(reports):
        ReportFactory(post=post)
    return post


def reload(post):
    return Post.objects.get(pk=post.pk)


def only_row():
    return ModerationAction.objects.get()


def report_states(post):
    return sorted(Report.objects.filter(post=post).values_list("status", flat=True))


# ---------- Mark verified / Mark FALSE ----------


@pytest.mark.parametrize(
    ("service", "status", "kind"),
    [
        (services.mark_verified, PostStatus.VERIFIED_TRUE, ActionKind.VERIFIED),
        (services.mark_false, PostStatus.VERIFIED_FALSE, ActionKind.MARKED_FALSE),
    ],
)
@pytest.mark.parametrize("flag", [FlaggedReason.PIPELINE, FlaggedReason.REPORTS, "both", "appeal"])
@pytest.mark.parametrize(
    "pre", [PostStatus.PENDING, PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE]
)
def test_a_verdict_labels_a_fact_under_review_whatever_flagged_it(service, status, kind, flag, pre):
    post = reviewed(flag=flag, pre=pre, escalated_at=NOW - timedelta(hours=1))
    moderator = moderator_user()
    row = service(
        post.pk, moderator=moderator, notes="checked", public_note="Two sources agree", now=NOW
    )
    after = reload(post)
    assert after.status == status
    assert after.verdict_source == VerdictSource.MODERATOR
    assert after.verdict_note == "Two sources agree"
    assert (after.flagged_reason, after.pre_review_status) == (None, None)
    assert (after.review_started_at, after.escalated_at) == (None, None)
    assert (after.moderated_by, after.moderated_at) == (moderator, NOW)
    assert after.updated_at > post.updated_at
    assert report_states(post) == [ReportStatus.ACTIONED] * 3
    assert (row.action, row.from_status, row.to_status) == (kind, "under_review", status)
    assert (row.moderator, row.notes, row.public_note) == (
        moderator,
        "checked",
        "Two sources agree",
    )
    assert (row.post, row.post_snapshot, row.created_at) == (post, post.content, NOW)
    assert only_row().pk == row.pk


def test_a_blank_public_note_clears_an_older_verdict_note():
    post = reviewed(verdict_note="An older note")
    services.mark_verified(post.pk, moderator=moderator_user(), now=NOW)
    assert reload(post).verdict_note == ""


def test_verdicts_are_refused_on_an_opinion_and_write_nothing():
    post = reviewed(
        post_type=PostType.OPINION, pre=PostStatus.PUBLISHED, flag=FlaggedReason.REPORTS
    )
    for service in (services.mark_verified, services.mark_false):
        with pytest.raises(services.ActionRefused) as refused:
            service(post.pk, moderator=moderator_user(), now=NOW)
        assert refused.value.refusal.code == "opinion"
    assert reload(post).status == PostStatus.UNDER_REVIEW
    assert ModerationAction.objects.count() == 0
    assert report_states(post) == [ReportStatus.OPEN] * 3


# ---------- Dismiss reports ----------


@pytest.mark.parametrize(
    ("post_type", "pre"),
    [
        (PostType.FACT, PostStatus.PENDING),
        (PostType.FACT, PostStatus.VERIFIED_TRUE),
        (PostType.FACT, PostStatus.VERIFIED_FALSE),
        (PostType.OPINION, PostStatus.PUBLISHED),
    ],
)
def test_dismissing_reports_flagged_only_by_reports_restores_the_old_status(post_type, pre):
    post = reviewed(post_type=post_type, pre=pre, escalated_at=NOW)
    moderator = moderator_user()
    row = services.dismiss_reports(post.pk, moderator=moderator, notes="not enough", now=NOW)
    after = reload(post)
    assert after.status == pre
    assert (after.flagged_reason, after.pre_review_status) == (None, None)
    assert (after.review_started_at, after.escalated_at) == (None, None)
    assert after.verdict_source == post.verdict_source  # a dismissal decides nothing
    assert report_states(post) == [ReportStatus.DISMISSED] * 3
    assert (row.action, row.from_status, row.to_status) == (
        ActionKind.DISMISSED_REPORT,
        "under_review",
        pre,
    )
    assert (row.notes, row.public_note) == ("not enough", "")


def test_dismissing_reports_of_a_post_also_flagged_by_the_pipeline_leaves_it_for_a_moderator():
    post = reviewed(flag=FlaggedReason.BOTH, pre=PostStatus.PENDING, escalated_at=NOW)
    row = services.dismiss_reports(post.pk, moderator=moderator_user(), now=NOW)
    after = reload(post)
    assert after.status == PostStatus.UNDER_REVIEW
    assert after.flagged_reason == FlaggedReason.PIPELINE
    assert after.pre_review_status == PostStatus.PENDING
    assert (after.review_started_at, after.escalated_at) == (STARTED, NOW)
    assert report_states(post) == [ReportStatus.DISMISSED] * 3
    assert (row.from_status, row.to_status) == ("under_review", "under_review")


@pytest.mark.parametrize("flag", [FlaggedReason.PIPELINE, FlaggedReason.APPEAL])
def test_there_are_no_reports_to_dismiss_on_a_post_flagged_only_by_the_pipeline_or_an_appeal(flag):
    post = reviewed(flag=flag, reports=0)
    with pytest.raises(services.ActionRefused) as refused:
        services.dismiss_reports(post.pk, moderator=moderator_user(), now=NOW)
    assert refused.value.refusal.code == "no_reports"


def test_dismissed_reports_stop_counting_so_the_old_ones_cannot_cross_the_threshold_again(
    pipeline_cfg,
):

    cfg = get_platform_settings()
    post = reviewed(pre=PostStatus.PUBLISHED, post_type=PostType.OPINION, reports=5)
    now = timezone.now()
    assert counting_reports(post, cfg, now) == 5
    services.dismiss_reports(post.pk, moderator=moderator_user(), now=now)
    assert counting_reports(post, cfg, now) == 0


# ---------- Remove ----------


@pytest.mark.parametrize(
    "pre", [PostStatus.PENDING, PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE]
)
@pytest.mark.parametrize("flag", [FlaggedReason.PIPELINE, FlaggedReason.REPORTS, "both", "appeal"])
def test_removing_a_post_under_review_remembers_the_status_before_the_review(flag, pre):
    post = reviewed(flag=flag, pre=pre, escalated_at=NOW)
    moderator = moderator_user()
    row = services.remove_post(
        post.pk, moderator=moderator, notes="clear abuse", public_note="Harassment", now=NOW
    )
    after = reload(post)
    assert after.status == PostStatus.REMOVED
    assert after.pre_removal_status == pre
    assert (after.flagged_reason, after.pre_review_status) == (None, None)
    assert (after.review_started_at, after.escalated_at) == (None, None)
    assert (after.moderated_by, after.moderated_at) == (moderator, NOW)
    assert report_states(post) == [ReportStatus.ACTIONED] * 3
    assert (row.action, row.from_status, row.to_status) == (
        ActionKind.REMOVED,
        "under_review",
        "removed",
    )
    assert (row.notes, row.public_note) == ("clear abuse", "Harassment")


def test_removing_never_touches_the_verdict_note():
    post = reviewed(verdict_note="Public note from an earlier verdict")
    services.remove_post(post.pk, moderator=moderator_user(), public_note="Spam", now=NOW)
    assert reload(post).verdict_note == "Public note from an earlier verdict"


@pytest.mark.parametrize(
    ("make", "before"),
    [
        (lambda: PostFactory(), PostStatus.PUBLISHED),
        (lambda: PostFactory(fact=True), PostStatus.PENDING),
        (lambda: PostFactory(verified_pipeline=True), PostStatus.VERIFIED_TRUE),
        (lambda: PostFactory(moderator_verdict=True), PostStatus.VERIFIED_FALSE),
    ],
)
def test_removing_a_post_that_is_not_under_review_remembers_its_current_status(make, before):
    post = make()
    ReportFactory(post=post)
    row = services.remove_post(post.pk, moderator=moderator_user(), now=NOW)
    after = reload(post)
    assert (after.status, after.pre_removal_status) == (PostStatus.REMOVED, before)
    assert report_states(post) == [ReportStatus.ACTIONED]
    assert (row.from_status, row.to_status) == (before, "removed")


def test_removing_an_already_removed_post_is_refused():
    post = PostFactory(removed=True)
    with pytest.raises(services.ActionRefused) as refused:
        services.remove_post(post.pk, moderator=moderator_user(), now=NOW)
    assert refused.value.refusal.code == "already_removed"
    assert ModerationAction.objects.count() == 0


# ---------- Escalate ----------


def test_escalating_stamps_the_post_and_changes_nothing_else():
    post = reviewed(flag=FlaggedReason.BOTH)
    moderator = moderator_user()
    row = services.escalate(post.pk, moderator=moderator, notes="needs a senior", now=NOW)
    after = reload(post)
    assert after.escalated_at == NOW
    assert (after.status, after.flagged_reason, after.pre_review_status) == (
        PostStatus.UNDER_REVIEW,
        FlaggedReason.BOTH,
        PostStatus.PENDING,
    )
    assert after.review_started_at == STARTED
    assert report_states(post) == [ReportStatus.OPEN] * 3  # reports stay open
    assert (row.action, row.from_status, row.to_status) == (
        ActionKind.ESCALATED,
        "under_review",
        "under_review",
    )
    assert row.notes == "needs a senior"


def test_escalating_twice_and_escalating_outside_review_are_refused():
    post = reviewed(escalated_at=NOW)
    with pytest.raises(services.ActionRefused) as twice:
        services.escalate(post.pk, moderator=moderator_user(), now=NOW)
    assert twice.value.refusal.code == "already_escalated"
    published = PostFactory()
    with pytest.raises(services.ActionRefused) as outside:
        services.escalate(published.pk, moderator=moderator_user(), now=NOW)
    assert outside.value.refusal.code == "not_under_review"
    assert ModerationAction.objects.count() == 0
    assert reload(published).escalated_at is None


# ---------- the same for every action ----------

ALL = [
    ("mark_verified", {}),
    ("mark_false", {}),
    ("dismiss_reports", {}),
    ("remove_post", {}),
    ("escalate", {}),
]


@pytest.mark.parametrize(("name", "extra"), ALL)
def test_a_refusal_writes_nothing_at_all(name, extra):
    """A deleted post is refused by every action: no row, no report change, no `updated_at`."""
    post = reviewed(deleted=True)
    before = reload(post)
    with pytest.raises(services.ActionRefused) as refused:
        getattr(services, name)(post.pk, moderator=moderator_user(), now=NOW, **extra)
    assert refused.value.refusal is DELETED
    assert ModerationAction.objects.count() == 0
    assert report_states(post) == [ReportStatus.OPEN] * 3
    assert reload(post).updated_at == before.updated_at
    assert reload(post).status == PostStatus.UNDER_REVIEW


@pytest.mark.parametrize(("name", "extra"), ALL)
def test_a_post_that_does_not_exist_is_the_deleted_refusal_not_a_crash(name, extra):
    import uuid

    with pytest.raises(services.ActionRefused) as refused:
        getattr(services, name)(uuid.uuid4(), moderator=moderator_user(), now=NOW, **extra)
    assert refused.value.refusal is DELETED


@pytest.mark.parametrize(("name", "extra"), ALL)
def test_nobody_acts_on_their_own_post_except_a_superuser(name, extra):
    moderator = moderator_user()
    post = reviewed()
    post.author = moderator
    post.save()
    with pytest.raises(services.ActionRefused) as refused:
        getattr(services, name)(post.pk, moderator=moderator, now=NOW, **extra)
    assert refused.value.refusal.code == "own_post"
    assert ModerationAction.objects.count() == 0
    root = moderator_user(is_superuser=True)
    post.author = root
    post.save()
    getattr(services, name)(post.pk, moderator=root, now=NOW, **extra)  # no refusal
    assert ModerationAction.objects.count() == 1


@pytest.mark.parametrize("name", ["mark_verified", "mark_false", "dismiss_reports", "escalate"])
def test_actions_that_need_a_review_refuse_a_post_that_is_not_under_review(name):
    post = PostFactory(fact=True)
    with pytest.raises(services.ActionRefused) as refused:
        getattr(services, name)(post.pk, moderator=moderator_user(), now=NOW)
    assert refused.value.refusal.code == "not_under_review"


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [("dismiss_reports", {}), ("remove_post", {})],
)
def test_a_missing_status_to_return_to_is_a_refusal_not_an_integrity_error(name, kwargs):
    post = reviewed(pre=None)
    with pytest.raises(services.ActionRefused) as refused:
        getattr(services, name)(post.pk, moderator=moderator_user(), now=NOW, **kwargs)
    assert refused.value.refusal.code == "no_prior_status"
    assert reload(post).status == PostStatus.UNDER_REVIEW


@pytest.mark.parametrize(
    "name", ["mark_verified", "mark_false", "dismiss_reports", "remove_post", "escalate"]
)
def test_the_pipeline_columns_are_never_touched(name):
    post = reviewed(
        pipeline_attempts=3,
        pipeline_verdict="false",
        confidence_score=Decimal("91.00"),
        pipeline_checked_at=NOW - timedelta(hours=2),
        pipeline_next_attempt_at=NOW + timedelta(minutes=5),
        pipeline_result={"raw": True},
    )
    getattr(services, name)(post.pk, moderator=moderator_user(), now=NOW)
    after = reload(post)
    for field in (
        "pipeline_attempts",
        "pipeline_verdict",
        "confidence_score",
        "pipeline_checked_at",
        "pipeline_next_attempt_at",
        "pipeline_result",
    ):
        assert getattr(after, field) == getattr(post, field)


def test_only_the_posts_own_open_reports_change():
    post = reviewed(reports=2)
    ReportFactory(post=post, dismissed=True)
    other = reviewed(reports=2)
    services.remove_post(post.pk, moderator=moderator_user(), now=NOW)
    assert report_states(post) == ["actioned"] * 2 + ["dismissed"]
    assert report_states(other) == ["open", "open"]
    closed = Report.objects.filter(post=post, status=ReportStatus.ACTIONED)
    assert all(r.resolved_at == NOW and r.resolved_by is not None for r in closed)


def test_one_row_per_action_with_the_actors_and_no_other_writes():
    post = reviewed()
    moderator = moderator_user()
    with CaptureQueriesContext(connection) as queries:
        services.escalate(post.pk, moderator=moderator, now=NOW)
    inserts = [q["sql"] for q in queries if q["sql"].startswith("INSERT")]
    assert len(inserts) == 1 and "moderation_moderationaction" in inserts[0]
    assert ModerationAction.objects.count() == 1


def test_now_defaults_to_the_clock():
    post = reviewed()
    row = services.escalate(post.pk, moderator=moderator_user())
    assert abs(row.created_at - timezone.now()) < timedelta(seconds=30)
    assert reload(post).moderated_at == row.created_at
