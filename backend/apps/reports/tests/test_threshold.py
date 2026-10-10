"""`file_report` and the windowed threshold (ARCHITECTURE §4 and §5; ANALYSIS c-2), at a fixed
`NOW` so every boundary is exact."""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.posts.models import FlaggedReason, Post, PostStatus
from apps.reports import services
from apps.reports.models import Report, ReportReason, ReportStatus
from apps.reports.tests.factories import NOW, ReportFactory, VerifiedUserFactory, aged_user
from apps.social.tests.factories import PostFactory

pytestmark = pytest.mark.django_db

WINDOW = timedelta(hours=24)


def file(post, reporter=None, *, now=NOW, reason=ReportReason.INACCURATE, details=""):
    reporter = reporter or aged_user()
    return services.file_report(
        reporter=reporter, post_id=post.pk, reason=reason, details=details, now=now
    )


def reload(post):
    return Post.objects.get(pk=post.pk)


def seed(post, n, **fields):
    """`n` open, counting reports by other people, all inside the window, with the post's lifetime
    counter in step (as if the service had filed them)."""
    for i in range(n):
        ReportFactory(post=post, created_at=NOW - timedelta(minutes=i + 1), **fields)
    Post.objects.filter(pk=post.pk).update(report_count=n)


# ---------- the report itself ----------


def test_a_report_is_stored_with_its_fields_at_now():
    post = PostFactory()
    reporter = aged_user()
    report = file(post, reporter, reason=ReportReason.OTHER, details="It targets me.")
    stored = Report.objects.get()
    assert report.pk == stored.pk
    assert (stored.post_id, stored.reporter_id) == (post.pk, reporter.pk)
    assert (stored.reason, stored.details) == (ReportReason.OTHER, "It targets me.")
    assert stored.status == ReportStatus.OPEN and stored.resolved_at is None
    assert stored.counts_toward_threshold is True
    assert stored.created_at == NOW


def test_a_young_reporter_without_activity_is_recorded_as_not_counting():
    post = PostFactory()
    file(post, VerifiedUserFactory(created_at=NOW - timedelta(hours=1)))
    assert Report.objects.get().counts_toward_threshold is False


def test_every_report_adds_one_to_the_lifetime_counter_counting_or_not():
    post = PostFactory()
    file(post, aged_user())
    file(post, VerifiedUserFactory(created_at=NOW - timedelta(hours=1)))  # doesn't count
    assert reload(post).report_count == 2


def test_a_report_moves_updated_at():
    post = PostFactory()
    before = reload(post).updated_at
    file(post)
    assert reload(post).updated_at > before


# ---------- the threshold ----------


def test_one_below_the_threshold_leaves_the_post_alone():
    post = PostFactory()
    seed(post, 3)
    file(post)  # the 4th of 5
    after = reload(post)
    assert (after.status, after.flagged_reason, after.pre_review_status) == (
        PostStatus.PUBLISHED,
        None,
        None,
    )
    assert after.report_count == 4


def test_the_report_that_reaches_the_threshold_sends_the_post_to_review():
    post = PostFactory()
    seed(post, 4)
    file(post)  # the 5th counts itself
    after = reload(post)
    assert after.status == PostStatus.UNDER_REVIEW
    assert after.flagged_reason == FlaggedReason.REPORTS
    assert after.pre_review_status == PostStatus.PUBLISHED
    assert after.report_count == 5


def test_a_threshold_of_one_means_the_first_report_is_enough(report_settings):
    report_settings(threshold=1)
    post = PostFactory()
    file(post)
    assert reload(post).status == PostStatus.UNDER_REVIEW


def test_the_threshold_is_read_from_the_settings(report_settings):
    report_settings(threshold=2)
    post = PostFactory()
    file(post)
    assert reload(post).status == PostStatus.PUBLISHED
    file(post)
    assert reload(post).status == PostStatus.UNDER_REVIEW


@pytest.mark.parametrize(
    ("traits", "before"),
    [
        ({"fact": True}, PostStatus.PENDING),
        ({}, PostStatus.PUBLISHED),
        ({"verified_pipeline": True}, PostStatus.VERIFIED_TRUE),
        ({"moderator_verdict": True}, PostStatus.VERIFIED_FALSE),
    ],
)
def test_every_reportable_status_goes_to_review_and_remembers_where_it_came_from(traits, before):
    post = PostFactory(**traits)
    seed(post, 4)
    file(post)
    after = reload(post)
    assert after.status == PostStatus.UNDER_REVIEW
    assert after.flagged_reason == FlaggedReason.REPORTS
    assert after.pre_review_status == before


@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        (FlaggedReason.PIPELINE, FlaggedReason.BOTH),
        (FlaggedReason.REPORTS, FlaggedReason.REPORTS),
        (FlaggedReason.BOTH, FlaggedReason.BOTH),
        (FlaggedReason.APPEAL, FlaggedReason.APPEAL),
    ],
)
def test_a_post_already_under_review_keeps_its_status_and_merges_the_reason(flag, expected):
    post = PostFactory(
        fact=True,
        under_review=True,
        flagged_reason=flag,
        pre_review_status=PostStatus.PENDING,
    )
    seed(post, 4)
    file(post)
    after = reload(post)
    assert after.status == PostStatus.UNDER_REVIEW
    assert after.flagged_reason == expected
    assert after.pre_review_status == PostStatus.PENDING


def test_more_reports_after_the_threshold_change_nothing_more():
    post = PostFactory()
    seed(post, 4)
    file(post)
    first = reload(post)
    file(post)
    after = reload(post)
    assert (after.status, after.flagged_reason, after.pre_review_status) == (
        first.status,
        first.flagged_reason,
        first.pre_review_status,
    )
    assert after.report_count == 6


# ---------- what counts: the window, the status, the flag ----------


def test_a_report_exactly_one_window_old_still_counts(report_settings):
    report_settings(threshold=2)
    post = PostFactory()
    ReportFactory(post=post, created_at=NOW - WINDOW)
    file(post)
    assert reload(post).status == PostStatus.UNDER_REVIEW


def test_a_report_a_microsecond_older_than_the_window_does_not_count(report_settings):
    report_settings(threshold=2)
    post = PostFactory()
    ReportFactory(post=post, created_at=NOW - WINDOW - timedelta(microseconds=1))
    file(post)
    assert reload(post).status == PostStatus.PUBLISHED
    assert reload(post).report_count == 1


def test_the_window_is_read_from_the_settings(report_settings):
    report_settings(threshold=2, window_hours=1)
    post = PostFactory()
    ReportFactory(post=post, created_at=NOW - timedelta(minutes=61))
    file(post)
    assert reload(post).status == PostStatus.PUBLISHED
    other = PostFactory()
    ReportFactory(post=other, created_at=NOW - timedelta(minutes=59))
    file(other)
    assert reload(other).status == PostStatus.UNDER_REVIEW


def test_a_report_made_after_now_still_counts_because_the_window_has_no_upper_bound(
    report_settings,
):
    """`now` is taken before a lock wait, so a report that waited can carry a `now` older than a
    row that has committed since: that row must still count."""
    report_settings(threshold=2)
    post = PostFactory()
    ReportFactory(post=post, created_at=NOW + timedelta(minutes=5))
    file(post)
    assert reload(post).status == PostStatus.UNDER_REVIEW


@pytest.mark.parametrize("trait", ["dismissed", "actioned", "not_counting"])
def test_dismissed_actioned_and_non_counting_reports_do_not_count(report_settings, trait):
    report_settings(threshold=2)
    post = PostFactory()
    ReportFactory(post=post, created_at=NOW - timedelta(minutes=1), **{trait: True})
    file(post)
    after = reload(post)
    assert after.status == PostStatus.PUBLISHED
    assert after.report_count == 1  # only the report this test filed went through the service


def test_reports_on_other_posts_do_not_count(report_settings):
    report_settings(threshold=2)
    post = PostFactory()
    ReportFactory(post=PostFactory(), created_at=NOW - timedelta(minutes=1))
    file(post)
    assert reload(post).status == PostStatus.PUBLISHED


def test_the_same_person_on_two_posts_counts_once_per_post(report_settings):
    report_settings(threshold=2)
    reporter = aged_user()
    first, second = PostFactory(), PostFactory()
    file(first, reporter)
    file(second, reporter)
    assert reload(first).status == PostStatus.PUBLISHED
    assert reload(second).status == PostStatus.PUBLISHED


def test_young_reporters_with_no_activity_can_not_reach_the_threshold_together(report_settings):
    report_settings(threshold=3)
    post = PostFactory()
    for _ in range(5):
        file(post, VerifiedUserFactory(created_at=NOW - timedelta(hours=1)))
    after = reload(post)
    assert after.status == PostStatus.PUBLISHED
    assert after.report_count == 5


def test_a_young_reporter_with_a_post_does_count(report_settings):
    report_settings(threshold=1)
    post = PostFactory()
    reporter = VerifiedUserFactory(created_at=NOW - timedelta(hours=1))
    PostFactory(author=reporter)
    file(post, reporter)
    assert reload(post).status == PostStatus.UNDER_REVIEW


# ---------- refusals leave no trace ----------


def test_your_own_post_is_refused_and_nothing_is_written():
    post = PostFactory()
    with pytest.raises(services.CannotReportOwn):
        file(post, post.author)
    assert Report.objects.count() == 0 and reload(post).report_count == 0


def test_a_second_report_of_the_same_post_is_refused_even_after_a_dismissal():
    post = PostFactory()
    reporter = aged_user()
    file(post, reporter)
    with pytest.raises(services.AlreadyReported):
        file(post, reporter)
    Report.objects.update(status=ReportStatus.DISMISSED, resolved_at=NOW)
    with pytest.raises(services.AlreadyReported):
        file(post, reporter)
    assert Report.objects.count() == 1 and reload(post).report_count == 1


@pytest.mark.parametrize("traits", [{"removed": True}, {"deleted": True}])
def test_a_removed_or_deleted_post_is_not_found(traits):
    post = PostFactory(**traits)
    with pytest.raises(services.PostNotFound):
        file(post)
    assert Report.objects.count() == 0


def test_an_unknown_post_is_not_found():
    with pytest.raises(services.PostNotFound):
        services.file_report(
            reporter=aged_user(), post_id=uuid.uuid4(), reason=ReportReason.SPAM, details=""
        )


def test_your_own_removed_post_is_not_found_not_refused_as_own():
    post = PostFactory(removed=True)
    with pytest.raises(services.PostNotFound):
        file(post, post.author)


def test_the_check_order_is_not_found_then_own_then_already_reported():
    post = PostFactory()
    mine = aged_user()
    other = PostFactory(author=mine)
    ReportFactory(post=other, reporter=mine, created_at=NOW)  # impossible in practice: own post
    with pytest.raises(services.CannotReportOwn):  # own is checked before the duplicate
        file(other, mine)
    file(post, mine)
    with pytest.raises(services.AlreadyReported):
        file(post, mine)


def test_the_real_clock_is_used_when_now_is_not_given():
    post = PostFactory()
    report = services.file_report(
        reporter=aged_user(hours=48, now=timezone.now()),
        post_id=post.pk,
        reason=ReportReason.SPAM,
        details="",
    )
    assert abs((report.created_at - timezone.now()).total_seconds()) < 60
