import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.posts.models import Post
from apps.reports.models import Report, ReportReason, ReportStatus
from apps.reports.tests.factories import ReportFactory, VerifiedUserFactory
from apps.social.tests.factories import PostFactory

pytestmark = pytest.mark.django_db


def refused(**fields):
    """True when the database refuses to store a report with these fields."""
    with pytest.raises(IntegrityError), transaction.atomic():
        ReportFactory(**fields)


def test_defaults_and_the_id():
    report = ReportFactory()
    assert report.status == ReportStatus.OPEN
    assert report.details == ""
    assert report.resolved_by is None and report.resolved_at is None
    assert report.id is not None and len(str(report.id)) == 36
    assert report.created_at <= timezone.now()


def test_one_report_per_person_and_post_for_life():
    report = ReportFactory()
    refused(post=report.post, reporter=report.reporter)
    # A resolved one still blocks a second try.
    resolved = ReportFactory(dismissed=True)
    refused(post=resolved.post, reporter=resolved.reporter)
    # Other pairs are fine.
    ReportFactory(post=report.post)
    ReportFactory(reporter=report.reporter)


def test_the_reason_is_one_of_the_five():
    for reason in ReportReason.values:
        ReportFactory(reason=reason, details="why")
    refused(reason="nonsense", details="x")
    assert set(ReportReason.values) == {"inaccurate", "misleading", "harassment", "spam", "other"}


def test_the_status_is_one_of_the_three():
    refused(status="nonsense", resolved_at=timezone.now())


def test_something_else_needs_details_and_the_others_do_not():
    refused(reason=ReportReason.OTHER, details="")
    ReportFactory(reason=ReportReason.OTHER, details="It impersonates me.")
    ReportFactory(reason=ReportReason.SPAM, details="")


def test_open_means_unresolved_and_the_rest_resolved():
    refused(status=ReportStatus.OPEN, resolved_at=timezone.now())
    refused(status=ReportStatus.DISMISSED, resolved_at=None)
    refused(status=ReportStatus.ACTIONED, resolved_at=None)
    ReportFactory(dismissed=True)
    ReportFactory(actioned=True)


def test_details_have_a_500_character_column():
    ReportFactory(reason=ReportReason.OTHER, details="x" * 500)
    with pytest.raises(Exception, match="too long"), transaction.atomic():
        ReportFactory(reason=ReportReason.OTHER, details="x" * 501)


def test_the_counting_flag_has_no_default():
    with pytest.raises(IntegrityError), transaction.atomic():
        Report.objects.create(
            post=PostFactory(), reporter=VerifiedUserFactory(), reason=ReportReason.SPAM
        )


def test_deleting_the_post_or_the_reporter_deletes_the_report():
    by_post, by_person = ReportFactory(), ReportFactory()
    by_post.post.delete()
    by_person.reporter.delete()
    assert Report.objects.count() == 0


def test_deleting_the_resolver_keeps_the_report():
    moderator = VerifiedUserFactory()
    report = ReportFactory(dismissed=True, resolved_by=moderator)
    moderator.delete()
    report.refresh_from_db()
    assert report.resolved_by is None and report.status == ReportStatus.DISMISSED


def test_deleting_a_reporter_leaves_the_posts_lifetime_counter_alone():
    """`report_count` is a lifetime counter (§2): the cascade removes the row, not the count."""
    post = PostFactory(report_count=3)
    reporter = VerifiedUserFactory()
    ReportFactory(post=post, reporter=reporter)
    reporter.delete()
    assert Report.objects.filter(post=post).count() == 0
    assert Post.objects.get(pk=post.pk).report_count == 3
    assert User.objects.filter(pk=reporter.pk).count() == 0


def test_str_never_shows_the_details():
    report = ReportFactory(reason=ReportReason.OTHER, details="a private accusation")
    assert "private" not in str(report)
    assert str(report.reporter_id) in str(report)
