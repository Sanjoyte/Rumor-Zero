"""Filing a report and deciding whether it counts (ARCHITECTURE §5; ANALYSIS c-2).

There is no HTTP here: the view turns these domain errors into responses. The threshold is a
windowed count over `reports` rows, worked out inside the same transaction as the insert and
under the post's row lock, so two simultaneous reports can't both miss it. Redis is never used:
a cache eviction must never lose a report.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.services import get_platform_settings
from apps.posts import services as post_services
from apps.posts.models import Post, PostStatus
from apps.reports.models import Report, ReportStatus
from apps.social.models import Comment


class PostNotFound(Exception):
    """No post the public can see has this id (unknown, deleted, or removed)."""


class CannotReportOwn(Exception):
    """You can't report your own post."""


class AlreadyReported(Exception):
    """You already reported this post (one report per person and post, for life)."""


def counts_toward_threshold(reporter, cfg, now):
    """Whether `reporter`'s report counts toward the threshold (ARCHITECTURE §5; guide §6.3).

    It counts when the account is at least `report_min_account_age_hours` old (inclusive), **or**
    the person has already taken part: a post that isn't removed, or a comment that isn't hidden.
    Posts and comments the person deleted themselves still count ("deleting undoes nothing", as for
    the fact quota); content a moderator took down doesn't earn trust (user decision 2026-10-10).
    Short-circuits in that order, so an established account costs no query.
    """
    if reporter.created_at <= now - timedelta(hours=cfg.report_min_account_age_hours):
        return True
    if Post.objects.filter(author=reporter).exclude(status=PostStatus.REMOVED).exists():
        return True
    return Comment.objects.filter(author=reporter, is_hidden=False).exists()


def counting_reports(post, cfg, now):
    """The post's open, counting reports inside the window (inclusive of its start). There is no
    upper bound on purpose: `now` is taken before a lock wait, so a report that waited can carry a
    `now` older than a row that has committed since."""
    since = now - timedelta(hours=cfg.report_window_hours)
    return Report.objects.filter(
        post=post,
        status=ReportStatus.OPEN,
        counts_toward_threshold=True,
        created_at__gte=since,
    ).count()


def file_report(*, reporter, post_id, reason, details, now=None):
    """Record `reporter`'s report of a post and apply the threshold. Returns the `Report`.

    Order: a post the public can see (else `PostNotFound`), your own post (`CannotReportOwn`),
    an earlier report by you (`AlreadyReported`). The post row is locked with `FOR NO KEY UPDATE`,
    like a repost: it serialises reports with each other and with status writes (a delete, a
    moderator's action), but not with the `FOR KEY SHARE` locks that likes, comments and bookmark
    inserts take on a busy post. A report that waited for a delete or a removal re-checks the row
    and finds nothing. The lock also makes the duplicate check race-free (the unique pair stays as
    the last-resort guard), and it is what lets `report_count` be a plain read-modify-write.
    """
    now = now or timezone.now()
    with transaction.atomic():
        post = (
            Post.objects.visible()
            .select_for_update(no_key=True, of=("self",))
            .defer("pipeline_result")
            .filter(pk=post_id)
            .first()
        )
        if post is None:
            raise PostNotFound
        if post.author_id == reporter.pk:
            raise CannotReportOwn
        if Report.objects.filter(post=post, reporter=reporter).exists():
            raise AlreadyReported
        cfg = get_platform_settings()
        report = Report.objects.create(
            post=post,
            reporter=reporter,
            reason=reason,
            details=details,
            counts_toward_threshold=counts_toward_threshold(reporter, cfg, now),
            created_at=now,
        )
        post_services.record_report(
            post, counting_reports=counting_reports(post, cfg, now), cfg=cfg, now=now
        )
    return report


def resolve_open_reports(post, *, status, moderator, now):
    """Close `post`'s open reports as `dismissed` or `actioned` (ARCHITECTURE §4); returns the
    reporters' ids (Part 11B credits them when a moderator upholds their reports).

    One `UPDATE` sets the status, `resolved_by` and `resolved_at` together, as the database check
    `reports_resolution_consistent` demands. Reports that are already resolved, and other posts',
    are untouched. A resolved report never counts toward the threshold again. Called by the
    moderation services inside their transaction with the post's row lock held, so a report that
    arrives meanwhile waits and is filed afterwards (`file_report` locks the post first), and the
    reporters read just before the `UPDATE` are exactly the ones it resolves. Report writes stay
    in this module.
    """
    if status not in (ReportStatus.DISMISSED, ReportStatus.ACTIONED):
        raise ValueError(f"a report is resolved as dismissed or actioned, not {status!r}")
    open_reports = Report.objects.filter(post=post, status=ReportStatus.OPEN)
    reporters = list(open_reports.order_by("reporter_id").values_list("reporter_id", flat=True))
    if reporters:
        open_reports.update(status=status, resolved_by=moderator, resolved_at=now)
    return reporters
