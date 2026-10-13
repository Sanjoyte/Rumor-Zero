"""Appeals (ARCHITECTURE §4): `file_appeal`, the two new actions Restore and Keep removed, and how
the five older actions close an open appeal. Each one against each starting state, the rows it
writes, and "a refusal writes nothing"."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.moderation import services
from apps.moderation.models import ActionKind, Appeal, AppealKind, AppealStatus, ModerationAction
from apps.moderation.tests.factories import (
    AppealFactory,
    ModerationActionFactory,
    moderator_user,
    senior_user,
)
from apps.pipeline import processor
from apps.pipeline.routing import MAX_ATTEMPTS
from apps.posts.models import (
    FlaggedReason,
    PipelineVerdict,
    Post,
    PostStatus,
    PostType,
    VerdictSource,
)
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.reports.models import ReportStatus
from apps.reports.tests.factories import ReportFactory

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
LONG_AGO = NOW - timedelta(days=2)


def false_post(*, source=VerdictSource.PIPELINE, **fields):
    """A FALSE-labelled fact: the pipeline's by default, a moderator's with `source=moderator`."""
    return PostFactory(
        post_type=PostType.FACT,
        status=PostStatus.VERIFIED_FALSE,
        verdict_source=source,
        pipeline_verdict=PipelineVerdict.FALSE,
        confidence_score=Decimal("93.00"),
        pipeline_checked_at=LONG_AGO,
        pipeline_attempts=1,
        verdict_note="Contradicted by the filing" if source == VerdictSource.MODERATOR else "",
        **fields,
    )


def removed_post(*, remover=None, reason="", before=PostStatus.VERIFIED_FALSE, **fields):
    """A removed fact, with the `removed` row a moderator's Remove leaves."""
    post = PostFactory(
        post_type=PostType.FACT, status=PostStatus.REMOVED, pre_removal_status=before, **fields
    )
    ModerationActionFactory(
        post=post,
        moderator=remover,
        action=ActionKind.REMOVED,
        from_status=before,
        to_status=PostStatus.REMOVED,
        public_note=reason,
        created_at=LONG_AGO,
    )
    return post


def reload(post):
    return Post.objects.get(pk=post.pk)


def appeal_of(post):
    return Appeal.objects.get(post=post)


def refused_with(code, fn, *args, **kwargs):
    with pytest.raises(services.ActionRefused) as refused:
        fn(*args, **kwargs)
    assert refused.value.refusal.code == code


# ---------- file_appeal ----------


def test_a_label_appeal_sends_the_false_post_back_to_review():
    post = false_post()
    appeal = services.file_appeal(
        author=post.author, post_id=post.pk, reason="Read it again", now=NOW
    )
    after = reload(post)
    assert after.status == PostStatus.UNDER_REVIEW
    assert after.flagged_reason == FlaggedReason.APPEAL
    assert after.pre_review_status == PostStatus.VERIFIED_FALSE
    assert after.review_started_at == NOW  # the queue's clock starts now
    assert after.updated_at > post.updated_at
    assert (appeal.post, appeal.author, appeal.kind) == (post, post.author, AppealKind.LABEL)
    assert (appeal.status, appeal.reason, appeal.created_at) == (
        AppealStatus.OPEN,
        "Read it again",
        NOW,
    )
    assert (appeal.resolved_at, appeal.resolved_by) == (None, None)
    assert Appeal.objects.count() == 1


def test_a_label_appeal_leaves_the_label_the_pipeline_fields_and_the_audit_trail_alone():
    post = false_post()
    services.file_appeal(author=post.author, post_id=post.pk, now=NOW)
    after = reload(post)
    for field in (
        "verdict_source",
        "verdict_note",
        "confidence_score",
        "pipeline_verdict",
        "pipeline_attempts",
        "pipeline_checked_at",
        "pipeline_next_attempt_at",
        "pre_removal_status",
        "moderated_by",
        "report_count",
        "content",
    ):
        assert getattr(after, field) == getattr(post, field), field
    assert ModerationAction.objects.count() == 0  # an author's request isn't a moderator's action


def test_a_removal_appeal_leaves_the_post_removed_and_listed():
    post = removed_post(remover=moderator_user())
    appeal = services.file_appeal(author=post.author, post_id=post.pk, now=NOW)
    after = reload(post)
    assert after.status == PostStatus.REMOVED
    assert after.flagged_reason == FlaggedReason.APPEAL
    assert after.review_started_at is None  # a removed post has no queue clock of its own
    assert after.pre_review_status is None
    assert after.pre_removal_status == PostStatus.VERIFIED_FALSE
    assert after.updated_at > post.updated_at
    assert (appeal.kind, appeal.status) == (AppealKind.REMOVAL, AppealStatus.OPEN)


def test_the_reason_is_optional():
    post = false_post()
    assert services.file_appeal(author=post.author, post_id=post.pk, now=NOW).reason == ""


def test_the_time_is_taken_when_no_clock_is_given():
    post = false_post()
    before = timezone.now()
    appeal = services.file_appeal(author=post.author, post_id=post.pk)
    assert before <= appeal.created_at <= timezone.now()
    assert reload(post).review_started_at == appeal.created_at


def test_the_original_moderator_of_a_pipeline_false_is_nobody():
    post = false_post()
    # An old marked_false row of someone else must not be taken for the pipeline's label.
    ModerationActionFactory(post=post, action=ActionKind.MARKED_FALSE, moderator=moderator_user())
    appeal = services.file_appeal(author=post.author, post_id=post.pk, now=NOW)
    assert appeal.original_moderator_id is None


def test_the_original_moderator_of_a_moderator_false_is_who_marked_it_not_who_dismissed_reports():
    labeller, dismisser = moderator_user(), moderator_user()
    post = false_post(source=VerdictSource.MODERATOR, moderated_by=dismisser)
    ModerationActionFactory(
        post=post, action=ActionKind.MARKED_FALSE, moderator=labeller, created_at=LONG_AGO
    )
    ModerationActionFactory(
        post=post,
        action=ActionKind.DISMISSED_REPORT,
        moderator=dismisser,
        created_at=NOW - timedelta(hours=1),
    )
    appeal = services.file_appeal(author=post.author, post_id=post.pk, now=NOW)
    assert appeal.original_moderator == labeller


def test_when_two_moderators_marked_a_post_false_only_the_latest_counts():
    first, second = moderator_user(), moderator_user()
    post = false_post(source=VerdictSource.MODERATOR)
    ModerationActionFactory(
        post=post, action=ActionKind.MARKED_FALSE, moderator=first, created_at=LONG_AGO
    )
    ModerationActionFactory(
        post=post,
        action=ActionKind.MARKED_FALSE,
        moderator=second,
        created_at=LONG_AGO + timedelta(hours=3),
    )
    appeal = services.file_appeal(author=post.author, post_id=post.pk, now=NOW)
    assert appeal.original_moderator == second


def test_the_original_moderator_of_a_removal_is_who_removed_it_latest():
    first, second = moderator_user(), moderator_user()
    post = removed_post(remover=first)
    ModerationActionFactory(
        post=post,
        action=ActionKind.REMOVED,
        moderator=second,
        created_at=LONG_AGO + timedelta(hours=1),
    )
    appeal = services.file_appeal(author=post.author, post_id=post.pk, now=NOW)
    assert appeal.original_moderator == second


def test_a_moderator_whose_account_is_gone_leaves_no_original_moderator():
    remover = moderator_user()
    post = removed_post(remover=remover)
    remover.delete()
    appeal = services.file_appeal(author=post.author, post_id=post.pk, now=NOW)
    assert appeal.original_moderator_id is None


def test_a_removal_with_no_audit_row_has_no_original_moderator():
    post = PostFactory(post_type=PostType.FACT, status=PostStatus.REMOVED)
    assert services.file_appeal(author=post.author, post_id=post.pk).original_moderator_id is None


@pytest.mark.parametrize(
    "fields",
    [
        {"status": PostStatus.PENDING},
        {"status": PostStatus.PUBLISHED, "post_type": PostType.OPINION},
        {"status": PostStatus.VERIFIED_TRUE, "verdict_source": VerdictSource.PIPELINE},
        {
            "status": PostStatus.UNDER_REVIEW,
            "flagged_reason": FlaggedReason.PIPELINE,
            "pre_review_status": PostStatus.PENDING,
        },
        # A FALSE post that reports sent to review: not appealable until that review ends.
        {
            "status": PostStatus.UNDER_REVIEW,
            "flagged_reason": FlaggedReason.REPORTS,
            "pre_review_status": PostStatus.VERIFIED_FALSE,
            "verdict_source": VerdictSource.PIPELINE,
        },
    ],
)
def test_only_a_false_label_or_a_removal_can_be_appealed(fields):
    post = PostFactory(**{"post_type": PostType.FACT, **fields})
    with pytest.raises(services.NotAppealable):
        services.file_appeal(author=post.author, post_id=post.pk, now=NOW)
    assert Appeal.objects.count() == 0
    after = reload(post)
    assert (after.status, after.flagged_reason) == (post.status, post.flagged_reason)
    assert after.updated_at == post.updated_at


def test_somebody_elses_post_cannot_be_appealed_even_by_a_moderator():
    post = false_post()
    for stranger in (VerifiedUserFactory(), moderator_user()):
        with pytest.raises(services.NotPostAuthor):
            services.file_appeal(author=stranger, post_id=post.pk, now=NOW)
    assert Appeal.objects.count() == 0
    assert reload(post).status == PostStatus.VERIFIED_FALSE


def test_a_deleted_or_unknown_post_is_not_found_its_author_included():
    import uuid

    post = false_post(deleted_at=NOW)
    with pytest.raises(services.PostNotFound):
        services.file_appeal(author=post.author, post_id=post.pk, now=NOW)
    with pytest.raises(services.PostNotFound):
        services.file_appeal(author=post.author, post_id=uuid.uuid4(), now=NOW)
    assert Appeal.objects.count() == 0


@pytest.mark.parametrize("status", AppealStatus.values)
def test_a_post_can_be_appealed_once_for_life(status):
    resolved = status != AppealStatus.OPEN
    appeal = AppealFactory(
        status=status,
        resolved_at=NOW if resolved else None,
        resolved_by=moderator_user() if resolved else None,
    )
    with pytest.raises(services.AlreadyAppealed):
        services.file_appeal(author=appeal.author, post_id=appeal.post_id, now=NOW)
    assert Appeal.objects.count() == 1


def test_already_appealed_wins_over_not_appealable_after_an_outcome():
    """The label was overturned, so the post is TRUE now: the answer is still "already"."""
    post = false_post()
    services.file_appeal(author=post.author, post_id=post.pk, now=NOW)
    services.mark_verified(post.pk, moderator=moderator_user(), now=NOW)
    assert reload(post).status == PostStatus.VERIFIED_TRUE
    with pytest.raises(services.AlreadyAppealed):
        services.file_appeal(author=post.author, post_id=post.pk, now=NOW)


# ---------- a verdict or Remove on a label appeal ----------


def label_appeal(**fields):
    """A FALSE post an author appealed through the service, with its open appeal."""
    post = false_post(**fields)
    appeal = services.file_appeal(
        author=post.author,
        post_id=post.pk,
        reason="Please look again",
        now=NOW - timedelta(hours=2),
    )
    return post, appeal


@pytest.mark.parametrize(
    ("service", "status", "kind", "outcome"),
    [
        (
            services.mark_verified,
            PostStatus.VERIFIED_TRUE,
            ActionKind.VERIFIED,
            AppealStatus.OVERTURNED,
        ),
        (
            services.mark_false,
            PostStatus.VERIFIED_FALSE,
            ActionKind.MARKED_FALSE,
            AppealStatus.UPHELD,
        ),
    ],
)
def test_a_verdict_on_a_post_under_appeal_resolves_the_appeal(service, status, kind, outcome):
    post, appeal = label_appeal()
    moderator = moderator_user()
    row = service(
        post.pk, moderator=moderator, notes="second look", public_note="Rechecked", now=NOW
    )
    after, resolved = reload(post), appeal_of(post)
    assert after.status == status
    assert (after.verdict_source, after.verdict_note) == (VerdictSource.MODERATOR, "Rechecked")
    assert (after.flagged_reason, after.pre_review_status, after.review_started_at) == (
        None,
        None,
        None,
    )
    assert (resolved.status, resolved.resolved_by, resolved.resolved_at) == (
        outcome,
        moderator,
        NOW,
    )
    assert row.action == kind and row.appeal == resolved
    assert resolved.reason == "Please look again"  # the author's words are never touched


def test_removing_a_post_under_a_label_appeal_upholds_the_appeal():
    post, appeal = label_appeal()
    moderator = moderator_user()
    row = services.remove_post(post.pk, moderator=moderator, public_note="Hate speech", now=NOW)
    after, resolved = reload(post), appeal_of(post)
    assert after.status == PostStatus.REMOVED
    assert after.pre_removal_status == PostStatus.VERIFIED_FALSE
    assert (resolved.status, resolved.resolved_by, resolved.resolved_at) == (
        AppealStatus.UPHELD,
        moderator,
        NOW,
    )
    assert row.appeal == resolved
    assert after.flagged_reason is None


def test_the_reports_on_a_post_under_appeal_are_actioned_with_the_appeal():
    post, _ = label_appeal()
    for _ in range(3):
        ReportFactory(post=post)
    services.mark_false(post.pk, moderator=moderator_user(), now=NOW)
    assert set(post.reports.values_list("status", flat=True)) == {ReportStatus.ACTIONED}
    assert appeal_of(post).status == AppealStatus.UPHELD


def test_reports_dismissal_is_not_how_an_appeal_ends():
    post, _ = label_appeal()
    refused_with("no_reports", services.dismiss_reports, post.pk, moderator=moderator_user())
    assert appeal_of(post).status == AppealStatus.OPEN


def test_the_moderator_who_made_the_first_decision_cannot_resolve_the_appeal():
    labeller = moderator_user()
    post = false_post(source=VerdictSource.MODERATOR)
    ModerationActionFactory(post=post, action=ActionKind.MARKED_FALSE, moderator=labeller)
    services.file_appeal(author=post.author, post_id=post.pk, now=NOW - timedelta(hours=1))
    before = reload(post)
    for service in (services.mark_verified, services.mark_false, services.remove_post):
        refused_with("original_moderator", service, post.pk, moderator=labeller, now=NOW)
    # Nothing was written: the post, the appeal and the log are as they were.
    after = reload(post)
    assert (after.status, after.updated_at) == (before.status, before.updated_at)
    assert appeal_of(post).status == AppealStatus.OPEN
    assert ModerationAction.objects.filter(post=post).count() == 1


def test_a_senior_or_another_moderator_can_resolve_it_and_so_can_a_superuser():
    labeller = moderator_user()
    for resolver in (moderator_user(), senior_user(), VerifiedUserFactory(is_superuser=True)):
        post = false_post(source=VerdictSource.MODERATOR)
        ModerationActionFactory(post=post, action=ActionKind.MARKED_FALSE, moderator=labeller)
        services.file_appeal(author=post.author, post_id=post.pk, now=NOW - timedelta(hours=1))
        services.mark_verified(post.pk, moderator=resolver, now=NOW)
        assert appeal_of(post).resolved_by == resolver
    senior = senior_user()
    post = false_post(source=VerdictSource.MODERATOR)
    ModerationActionFactory(post=post, action=ActionKind.MARKED_FALSE, moderator=senior)
    services.file_appeal(author=post.author, post_id=post.pk, now=NOW - timedelta(hours=1))
    services.mark_false(post.pk, moderator=senior, now=NOW)  # the senior's own call: allowed
    assert appeal_of(post).status == AppealStatus.UPHELD


def test_escalating_is_allowed_to_the_moderator_who_made_the_first_decision_and_resolves_nothing():
    labeller = moderator_user()
    post = false_post(source=VerdictSource.MODERATOR)
    ModerationActionFactory(post=post, action=ActionKind.MARKED_FALSE, moderator=labeller)
    services.file_appeal(author=post.author, post_id=post.pk, now=NOW - timedelta(hours=1))
    row = services.escalate(post.pk, moderator=labeller, now=NOW)
    assert row.action == ActionKind.ESCALATED and row.appeal is None  # linked on resolution only
    assert reload(post).escalated_at == NOW
    assert appeal_of(post).status == AppealStatus.OPEN


# ---------- Restore post / Keep removed ----------


def removal_appeal(*, remover=None, **fields):
    post = removed_post(remover=remover or moderator_user(), reason="Not allowed here", **fields)
    appeal = services.file_appeal(
        author=post.author, post_id=post.pk, reason="It was fine", now=NOW - timedelta(hours=2)
    )
    return post, appeal


@pytest.mark.parametrize("before", [PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE])
def test_restore_puts_a_verified_fact_back_with_its_label(before):
    post, _ = removal_appeal(
        before=before,
        verdict_source=VerdictSource.PIPELINE,
        confidence_score=Decimal("92.00"),
        pipeline_checked_at=LONG_AGO,
    )
    moderator = moderator_user()
    row = services.restore_post(post.pk, moderator=moderator, notes="fine on rereading", now=NOW)
    after, resolved = reload(post), appeal_of(post)
    assert after.status == before
    assert (after.flagged_reason, after.pre_removal_status, after.review_started_at) == (
        None,
        None,
        None,
    )
    assert (after.verdict_source, after.confidence_score) == (
        VerdictSource.PIPELINE,
        Decimal("92.00"),
    )
    assert (after.moderated_by, after.moderated_at) == (moderator, NOW)
    assert (resolved.status, resolved.resolved_by, resolved.resolved_at) == (
        AppealStatus.OVERTURNED,
        moderator,
        NOW,
    )
    assert (row.action, row.from_status, row.to_status) == (
        ActionKind.RESTORED,
        PostStatus.REMOVED,
        before,
    )
    assert (row.appeal, row.notes, row.public_note) == (resolved, "fine on rereading", "")


def test_restore_puts_an_opinion_back_to_published():
    post = PostFactory(status=PostStatus.REMOVED, pre_removal_status=PostStatus.PUBLISHED)
    services.file_appeal(author=post.author, post_id=post.pk, now=NOW - timedelta(hours=1))
    services.restore_post(post.pk, moderator=moderator_user(), now=NOW)
    assert reload(post).status == PostStatus.PUBLISHED


def test_restore_of_a_fact_the_pipeline_never_finished_goes_back_to_pending():
    post, _ = removal_appeal(
        before=PostStatus.PENDING, pipeline_checked_at=None, pipeline_attempts=2
    )
    services.restore_post(post.pk, moderator=moderator_user(), now=NOW)
    after = reload(post)
    assert (after.status, after.flagged_reason, after.pre_removal_status) == (
        PostStatus.PENDING,
        None,
        None,
    )
    assert after.pipeline_attempts == 2  # the claim token is not touched (Part 9)


@pytest.mark.parametrize(
    ("checked_at", "attempts"), [(LONG_AGO, 1), (None, MAX_ATTEMPTS)], ids=["answered", "gave up"]
)
def test_restore_of_a_checked_pending_fact_goes_to_the_review_queue_not_back_to_the_pipeline(
    checked_at, attempts
):
    post, _ = removal_appeal(
        before=PostStatus.PENDING, pipeline_checked_at=checked_at, pipeline_attempts=attempts
    )
    moderator = moderator_user()
    row = services.restore_post(post.pk, moderator=moderator, now=NOW)
    after = reload(post)
    assert after.status == PostStatus.UNDER_REVIEW
    assert (after.flagged_reason, after.pre_review_status) == (
        FlaggedReason.PIPELINE,
        PostStatus.PENDING,
    )
    assert after.review_started_at == NOW and after.pre_removal_status is None
    assert after.pipeline_attempts == attempts  # not reset
    assert (row.from_status, row.to_status) == (PostStatus.REMOVED, PostStatus.UNDER_REVIEW)
    assert appeal_of(post).status == AppealStatus.OVERTURNED
    # And the pipeline's queue leaves it alone: a moderator gives the label.
    from apps.pipeline.routing import awaiting_check_q

    assert not Post.objects.filter(awaiting_check_q(), pk=post.pk).exists()


def test_restore_clears_an_escalation():
    post, _ = removal_appeal()
    services.escalate(post.pk, moderator=moderator_user(), now=NOW - timedelta(hours=1))
    assert reload(post).escalated_at is not None
    services.restore_post(post.pk, moderator=moderator_user(), now=NOW)
    assert reload(post).escalated_at is None


def test_keep_removed_closes_the_appeal_and_leaves_the_post_removed_and_unflagged():
    post, _ = removal_appeal()
    services.escalate(post.pk, moderator=moderator_user(), now=NOW - timedelta(hours=1))
    moderator = moderator_user()
    row = services.keep_removed(post.pk, moderator=moderator, notes="clear violation", now=NOW)
    after, resolved = reload(post), appeal_of(post)
    assert after.status == PostStatus.REMOVED
    assert (after.flagged_reason, after.escalated_at) == (None, None)
    assert after.pre_removal_status == PostStatus.VERIFIED_FALSE  # nothing is undone
    assert (resolved.status, resolved.resolved_by, resolved.resolved_at) == (
        AppealStatus.UPHELD,
        moderator,
        NOW,
    )
    assert (row.action, row.from_status, row.to_status) == (
        ActionKind.KEPT_REMOVED,
        PostStatus.REMOVED,
        PostStatus.REMOVED,
    )
    assert (row.appeal, row.notes, row.public_note) == (resolved, "clear violation", "")


def test_a_decided_removal_appeal_is_gone_from_the_queue_and_cannot_be_decided_twice():
    post, _ = removal_appeal()
    services.keep_removed(post.pk, moderator=moderator_user(), now=NOW)
    for service in (services.restore_post, services.keep_removed):
        refused_with("no_removal_appeal", service, post.pk, moderator=moderator_user())
    assert ModerationAction.objects.filter(post=post, action=ActionKind.KEPT_REMOVED).count() == 1


@pytest.mark.parametrize("service", [services.restore_post, services.keep_removed])
def test_restore_and_keep_removed_need_an_open_removal_appeal(service):
    plain = removed_post(remover=moderator_user())  # removed, never appealed
    refused_with("no_removal_appeal", service, plain.pk, moderator=moderator_user())
    published = PostFactory()
    refused_with("no_removal_appeal", service, published.pk, moderator=moderator_user())
    under_label_appeal, _ = label_appeal()
    refused_with("no_removal_appeal", service, under_label_appeal.pk, moderator=moderator_user())
    assert ModerationAction.objects.filter(action__in=[ActionKind.RESTORED]).count() == 0


@pytest.mark.parametrize("service", [services.restore_post, services.keep_removed])
def test_the_moderator_who_removed_the_post_cannot_decide_its_appeal_but_a_senior_can(service):
    remover = moderator_user()
    post, appeal = removal_appeal(remover=remover)
    before = reload(post)
    refused_with("original_moderator", service, post.pk, moderator=remover, now=NOW)
    after = reload(post)
    assert (after.status, after.flagged_reason, after.updated_at) == (
        before.status,
        before.flagged_reason,
        before.updated_at,
    )
    assert appeal_of(post).status == AppealStatus.OPEN
    assert ModerationAction.objects.filter(post=post).count() == 1  # only the original Remove
    service(post.pk, moderator=senior_user(), now=NOW)
    assert appeal_of(post).status != AppealStatus.OPEN


def test_a_removed_post_the_moderator_wrote_themselves_cannot_be_restored_by_them():
    moderator = moderator_user()
    post = removed_post(remover=moderator_user(), author=moderator)
    services.file_appeal(author=moderator, post_id=post.pk, now=NOW - timedelta(hours=1))
    refused_with("own_post", services.restore_post, post.pk, moderator=moderator, now=NOW)


def test_a_restore_with_no_status_to_return_to_is_refused_and_writes_nothing():
    post, _ = removal_appeal(before=PostStatus.PUBLISHED)  # a fact never returns to `published`
    refused_with("no_prior_status", services.restore_post, post.pk, moderator=moderator_user())
    assert appeal_of(post).status == AppealStatus.OPEN
    assert reload(post).status == PostStatus.REMOVED


def test_a_deleted_post_cannot_be_decided_and_its_appeal_stays_open():
    post, _ = removal_appeal()
    Post.objects.filter(pk=post.pk).update(deleted_at=NOW)
    refused_with("deleted", services.restore_post, post.pk, moderator=moderator_user())
    assert appeal_of(post).status == AppealStatus.OPEN


def test_an_unknown_post_is_refused_like_a_deleted_one():
    import uuid

    refused_with("deleted", services.keep_removed, uuid.uuid4(), moderator=moderator_user())


def test_escalating_a_removed_post_with_an_open_appeal_stamps_it_and_keeps_the_appeal_open():
    post, _ = removal_appeal()
    moderator = moderator_user()
    row = services.escalate(post.pk, moderator=moderator, notes="needs a senior", now=NOW)
    after = reload(post)
    assert (after.status, after.flagged_reason, after.escalated_at) == (
        PostStatus.REMOVED,
        FlaggedReason.APPEAL,
        NOW,
    )
    assert appeal_of(post).status == AppealStatus.OPEN
    assert (row.from_status, row.to_status, row.appeal) == (
        PostStatus.REMOVED,
        PostStatus.REMOVED,
        None,
    )
    refused_with("already_escalated", services.escalate, post.pk, moderator=moderator_user())


def test_escalating_a_removed_post_with_no_appeal_is_still_refused():
    post = removed_post(remover=moderator_user())
    refused_with("not_under_review", services.escalate, post.pk, moderator=moderator_user())


@pytest.mark.parametrize("service", [services.restore_post, services.keep_removed])
def test_neither_action_touches_the_pipeline_fields_or_the_reports(service):
    post, _ = removal_appeal(pipeline_checked_at=LONG_AGO, pipeline_attempts=3)
    ReportFactory(post=post, status=ReportStatus.ACTIONED, resolved_at=LONG_AGO)
    before = reload(post)
    service(post.pk, moderator=moderator_user(), now=NOW)
    after = reload(post)
    for field in (
        "pipeline_attempts",
        "pipeline_verdict",
        "pipeline_checked_at",
        "pipeline_next_attempt_at",
        "confidence_score",
        "report_count",
        "content",
    ):
        assert getattr(after, field) == getattr(before, field), field
    assert set(post.reports.values_list("status", flat=True)) == {ReportStatus.ACTIONED}


# ---------- the after-commit kick ----------


@pytest.fixture
def kicks(monkeypatch, settings):
    """Turn the kick on and record the posts it is started for (no thread is started)."""
    settings.PIPELINE_INLINE_KICK = True
    started = []
    monkeypatch.setattr(processor, "start_kick", started.append)
    return started


def test_a_post_restored_to_pending_is_kicked_after_the_commit(
    kicks, django_capture_on_commit_callbacks
):
    post, _ = removal_appeal(
        before=PostStatus.PENDING, pipeline_checked_at=None, pipeline_attempts=0
    )
    with django_capture_on_commit_callbacks(execute=True):
        services.restore_post(post.pk, moderator=moderator_user(), now=NOW)
        assert kicks == []  # not before the commit
    assert kicks == [post.pk]


@pytest.mark.parametrize(
    "before", [PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE, PostStatus.PENDING]
)
def test_other_restores_and_other_actions_start_no_check(
    kicks, django_capture_on_commit_callbacks, before
):
    # Checked pending, or already labelled: nothing for the pipeline to do.
    post, _ = removal_appeal(
        before=before, pipeline_checked_at=LONG_AGO, pipeline_attempts=MAX_ATTEMPTS
    )
    with django_capture_on_commit_callbacks(execute=True):
        services.restore_post(post.pk, moderator=moderator_user(), now=NOW)
    assert kicks == []


def test_dismissing_reports_back_to_pending_starts_no_check_either(
    kicks, django_capture_on_commit_callbacks
):
    post = PostFactory(
        post_type=PostType.FACT,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.PENDING,
        review_started_at=LONG_AGO,
    )
    with django_capture_on_commit_callbacks(execute=True):
        services.dismiss_reports(post.pk, moderator=moderator_user(), now=NOW)
    assert reload(post).status == PostStatus.PENDING and kicks == []


def test_nothing_is_kicked_with_the_setting_off(monkeypatch, django_capture_on_commit_callbacks):
    started = []
    monkeypatch.setattr(processor, "start_kick", started.append)
    post, _ = removal_appeal(
        before=PostStatus.PENDING, pipeline_checked_at=None, pipeline_attempts=0
    )
    with django_capture_on_commit_callbacks(execute=True):
        services.restore_post(post.pk, moderator=moderator_user(), now=NOW)
    assert started == []
