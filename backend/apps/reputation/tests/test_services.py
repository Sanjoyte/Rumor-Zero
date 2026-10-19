"""`settle_post` through the real writers: the pipeline's label and the moderator actions
(ARCHITECTURE §4a). One test per event kind, the reporter credit rules, every reversal path, what
writes nothing, the timing and privacy rules, the bookkeeping and the locks."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.moderation import services as moderation
from apps.moderation.models import ActionKind, AppealStatus
from apps.pipeline.routing import Outcome
from apps.posts import services as post_services
from apps.posts.models import FlaggedReason, Post, PostStatus, PostType
from apps.reports import services as report_services
from apps.reports.models import ReportStatus
from apps.reputation import scoring, services
from apps.reputation.models import EventKind as K
from apps.reputation.models import ReputationEvent
from apps.reputation.tests.factories import (
    FALSE_95,
    LOW_40,
    TRUE_95,
    EventFactory,
    PostFactory,
    VerifiedUserFactory,
    kinds,
    label_by_pipeline,
    moderator_user,
    open_reports,
    pending_fact,
    reported_fact,
    reported_opinion,
    reposted,
    stored,
)
from apps.social import services as social_services

pytestmark = pytest.mark.django_db

D = Decimal


def emergency_fact(author=None, **fields):
    now = timezone.now()
    return pending_fact(
        author, is_emergency=True, emergency_expires_at=now + timedelta(hours=24), **fields
    )


def rows_of(user):
    return list(ReputationEvent.objects.filter(user=user).order_by("created_at", "id"))


def report_upheld_credits(user):
    return kinds(user).count(K.REPORT_UPHELD)


# ---------- each kind in turn ----------


def test_fact_true_from_the_pipeline():
    post = pending_fact()
    now = timezone.now()
    assert label_by_pipeline(post, TRUE_95, now=now) == Outcome.LABELLED
    [row] = rows_of(post.author)
    assert (row.kind, row.positive, row.negative) == (K.FACT_TRUE, D("1"), D("0"))
    assert (row.post_id, row.moderation_action_id, row.score_after) == (post.pk, None, 55)
    assert row.created_at == now
    assert stored(post.author) == (55, 1)


def test_fact_true_from_a_moderator_links_the_action():
    post = reported_fact()
    entry = moderation.mark_verified(post.pk, moderator=moderator_user())
    [row] = rows_of(post.author)
    assert (row.kind, row.moderation_action_id, row.post_id) == (K.FACT_TRUE, entry.pk, post.pk)
    assert stored(post.author) == (55, 1)


def test_fact_false_from_the_pipeline_and_from_a_moderator():
    by_pipeline = pending_fact()
    label_by_pipeline(by_pipeline, FALSE_95)
    by_moderator = reported_fact()
    moderation.mark_false(by_moderator.pk, moderator=moderator_user())
    for post in (by_pipeline, by_moderator):
        assert kinds(post.author) == [K.FACT_FALSE]
        assert stored(post.author) == (45, 1)


def test_emergency_false_replaces_the_plain_false():
    by_pipeline = emergency_fact()
    label_by_pipeline(by_pipeline, FALSE_95)
    by_moderator = emergency_fact(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.PENDING,
    )
    moderation.mark_false(by_moderator.pk, moderator=moderator_user())
    for post in (by_pipeline, by_moderator):
        assert kinds(post.author) == [K.EMERGENCY_FALSE]
        assert stored(post.author) == (38, 1)


def test_an_emergency_verified_true_is_a_plain_fact_true():
    post = emergency_fact()
    label_by_pipeline(post, TRUE_95)
    assert kinds(post.author) == [K.FACT_TRUE]
    assert stored(post.author) == (55, 1)


@pytest.mark.parametrize("post_type", [PostType.FACT, PostType.OPINION])
def test_post_removed_for_a_fact_and_an_opinion(post_type):
    if post_type == PostType.FACT:
        post = pending_fact()
    else:
        post = PostFactory(post_type=PostType.OPINION, status=PostStatus.PUBLISHED)
    entry = moderation.remove_post(post.pk, moderator=moderator_user())
    [row] = rows_of(post.author)
    assert (row.kind, row.negative, row.moderation_action_id) == (K.POST_REMOVED, D("2"), entry.pk)
    assert stored(post.author) == (42, 1)


@pytest.mark.parametrize(
    ("result", "emergency", "kind", "expected"),
    [
        (TRUE_95, False, K.REPOST_TRUE, 51),  # 5.25 / 10.25
        (FALSE_95, False, K.REPOST_FALSE, 48),  # 5 / 10.5
        (FALSE_95, True, K.REPOST_EMERGENCY_FALSE, 45),  # 5 / 11
    ],
)
def test_the_repost_label_kinds(result, emergency, kind, expected):
    post = emergency_fact() if emergency else pending_fact()
    reposter = reposted(post)  # while pending: it counts
    label_by_pipeline(post, result)
    assert kinds(reposter) == [kind]
    # A reposter's events are not own-post events: they never make the score public.
    assert stored(reposter) == (expected, 0)


def test_repost_removed():
    post = PostFactory(post_type=PostType.OPINION, status=PostStatus.PUBLISHED)
    early = reposted(post, status=PostStatus.UNDER_REVIEW)
    late = reposted(post)  # `published`: an opinion's repost never counts
    moderation.remove_post(post.pk, moderator=moderator_user())
    assert kinds(early) == [K.REPOST_REMOVED]
    assert stored(early) == (48, 0)
    assert kinds(late) == []


def test_no_event_for_a_repost_made_after_the_verdict():
    post = pending_fact()
    label_by_pipeline(post, TRUE_95)
    reposter = VerifiedUserFactory()
    social_services.repost(user=reposter, post_id=post.pk)  # status_at_repost = verified_true
    post = Post.objects.get(pk=post.pk)
    assert not services.pending_changes(post)
    assert kinds(reposter) == []


@pytest.mark.parametrize("act", ["mark_false", "remove_post"])
def test_report_upheld_through_mark_false_and_remove(act):
    post = reported_fact()
    reporters = open_reports(post, 2)
    entry = getattr(moderation, act)(post.pk, moderator=moderator_user())
    for reporter in reporters:
        [row] = rows_of(reporter)
        assert (row.kind, row.positive, row.moderation_action_id) == (
            K.REPORT_UPHELD,
            D("0.25"),
            entry.pk,
        )
        assert stored(reporter) == (51, 0)


@pytest.mark.parametrize("act", ["mark_verified", "dismiss_reports", "escalate"])
def test_no_credit_through_mark_verified_dismiss_or_escalate(act):
    post = reported_fact()
    [reporter] = open_reports(post)
    getattr(moderation, act)(post.pk, moderator=moderator_user())
    assert kinds(reporter) == []
    assert stored(reporter) == (50, 0)


def test_no_credit_through_the_pipeline():
    post = pending_fact()
    label_by_pipeline(post, FALSE_95)
    assert set(ReputationEvent.objects.values_list("kind", flat=True)) == {K.FACT_FALSE}


# ---------- the reporter credit rules ----------


def credits_in_window(reporter, n, *, now, age=timedelta(days=1)):
    for i in range(n):
        EventFactory(
            user=reporter,
            kind=K.REPORT_UPHELD,
            created_at=now - age - timedelta(minutes=i),
            score_after=51,
        )


def mark_false_with_report(reporter, *, now):
    post = reported_fact()
    open_reports(post, reporter=reporter)
    moderation.mark_false(post.pk, moderator=moderator_user(), now=now)
    return post


def test_the_cap_credits_the_fourth_and_not_the_fifth():
    now = timezone.now()
    reporter = VerifiedUserFactory()
    credits_in_window(reporter, 3, now=now)
    mark_false_with_report(reporter, now=now)
    assert report_upheld_credits(reporter) == 4
    mark_false_with_report(reporter, now=now + timedelta(seconds=1))
    assert report_upheld_credits(reporter) == 4  # no fifth row at all


@pytest.mark.parametrize(
    ("age", "credited"),
    [
        (timedelta(days=30, microseconds=1), True),  # out of the window
        (timedelta(days=30), True),  # exactly 30 days old: out (the window is open there)
        (timedelta(days=30) - timedelta(microseconds=1), False),  # still in it
    ],
)
def test_the_cap_window_is_thirty_days(age, credited):
    now = timezone.now()
    reporter = VerifiedUserFactory()
    credits_in_window(reporter, 3, now=now)
    EventFactory(user=reporter, kind=K.REPORT_UPHELD, created_at=now - age)
    mark_false_with_report(reporter, now=now)
    assert report_upheld_credits(reporter) == (5 if credited else 4)


def test_reversed_credits_free_a_slot():
    now = timezone.now()
    reporter = VerifiedUserFactory()
    credits_in_window(reporter, 4, now=now)
    first = ReputationEvent.objects.filter(user=reporter).order_by("created_at").first()
    EventFactory(
        user=reporter,
        kind=K.REVERSAL,
        positive=D("-0.25"),
        negative=D("0"),
        reverses=first,
        created_at=now - timedelta(hours=1),
    )
    mark_false_with_report(reporter, now=now)
    assert report_upheld_credits(reporter) == 5  # 4 old (one reversed) + 1 new


def test_the_deciding_moderator_earns_nothing_from_their_own_report():
    post = reported_fact()
    moderator = moderator_user()
    [other] = open_reports(post)
    open_reports(post, reporter=moderator)
    moderation.mark_false(post.pk, moderator=moderator)
    assert kinds(moderator) == []
    assert kinds(other) == [K.REPORT_UPHELD]


def test_reports_on_a_pipeline_false_post_earn_nothing_when_a_moderator_confirms_it():
    """User decision 5: Mark FALSE credits only when it changed the label."""
    post = pending_fact()
    label_by_pipeline(post, FALSE_95)
    Post.objects.filter(pk=post.pk).update(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.VERIFIED_FALSE,
        review_started_at=timezone.now(),
    )
    [reporter] = open_reports(post)
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert kinds(reporter) == []
    assert kinds(post.author) == [K.FACT_FALSE]  # nothing new for the author either
    assert Post.objects.get(pk=post.pk).status == PostStatus.VERIFIED_FALSE


def test_reports_filed_during_a_label_appeal_earn_nothing_when_it_is_upheld():
    post = pending_fact()
    label_by_pipeline(post, FALSE_95)
    moderation.file_appeal(author=post.author, post_id=post.pk)
    [reporter] = open_reports(post)
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert kinds(reporter) == []


def test_a_remove_always_credits_even_on_a_false_post():
    post = pending_fact()
    label_by_pipeline(post, FALSE_95)
    Post.objects.filter(pk=post.pk).update(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.VERIFIED_FALSE,
        review_started_at=timezone.now(),
    )
    [reporter] = open_reports(post)
    moderation.remove_post(post.pk, moderator=moderator_user())
    assert kinds(reporter) == [K.REPORT_UPHELD]


def test_only_open_reports_are_credited():
    post = reported_fact()
    [open_one] = open_reports(post)
    [dismissed] = open_reports(post, dismissed=True)
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert kinds(open_one) == [K.REPORT_UPHELD]
    assert kinds(dismissed) == []


def test_resolve_open_reports_returns_the_reporters_it_resolved():
    post = reported_fact()
    reporters = open_reports(post, 3)
    open_reports(post, actioned=True)
    other = reported_fact()
    open_reports(other)
    got = report_services.resolve_open_reports(
        post, status=ReportStatus.ACTIONED, moderator=moderator_user(), now=timezone.now()
    )
    assert sorted(got) == sorted(r.pk for r in reporters)
    assert post.reports.filter(status=ReportStatus.OPEN).count() == 0
    assert other.reports.filter(status=ReportStatus.OPEN).count() == 1
    again = report_services.resolve_open_reports(
        post, status=ReportStatus.ACTIONED, moderator=moderator_user(), now=timezone.now()
    )
    assert again == []


# ---------- reversals ----------


def control(final_status, *, emergency=False, reposters=0, removed_after=False):
    """A fresh author whose post went straight to its final state, through the services."""
    post = emergency_fact() if emergency else pending_fact()
    people = [reposted(post) for _ in range(reposters)]
    if final_status in (PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE):
        label_by_pipeline(post, TRUE_95 if final_status == PostStatus.VERIFIED_TRUE else FALSE_95)
    if removed_after:
        moderation.remove_post(post.pk, moderator=moderator_user())
    return post.author, people


def test_a_relabel_true_to_false_through_a_reports_review():
    post = pending_fact()
    reposter = reposted(post)
    label_by_pipeline(post, TRUE_95)
    assert stored(post.author) == (55, 1)
    Post.objects.filter(pk=post.pk).update(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.VERIFIED_TRUE,
        review_started_at=timezone.now(),
    )
    [reporter] = open_reports(post)
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert kinds(post.author) == [K.FACT_TRUE, K.REVERSAL, K.FACT_FALSE]
    assert kinds(reposter) == [K.REPOST_TRUE, K.REVERSAL, K.REPOST_FALSE]
    assert kinds(reporter) == [K.REPORT_UPHELD]  # it changed the label
    # Exactly where a straight FALSE would have left them.
    author, [other] = control(PostStatus.VERIFIED_FALSE, reposters=1)
    assert stored(post.author) == stored(author) == (45, 1)
    assert stored(reposter) == stored(other)


def test_an_overturned_label_appeal_reverses_author_reposters_and_label_credits():
    post = reported_fact()
    reposter = reposted(post)  # made under review: counts
    [reporter] = open_reports(post)
    first = moderator_user()
    moderation.mark_false(post.pk, moderator=first)
    assert stored(post.author) == (45, 1)
    assert stored(reporter) == (51, 0)
    moderation.file_appeal(author=post.author, post_id=post.pk)
    entry = moderation.mark_verified(post.pk, moderator=moderator_user())
    assert entry.appeal.status == AppealStatus.OVERTURNED
    assert kinds(post.author, include_reversed=False) == [K.FACT_TRUE]
    assert kinds(reposter, include_reversed=False) == [K.REPOST_TRUE]
    assert kinds(reporter) == [K.REPORT_UPHELD, K.REVERSAL]
    assert stored(reporter) == (50, 0)
    author, [other] = control(PostStatus.VERIFIED_TRUE, reposters=1)
    assert stored(post.author) == stored(author) == (55, 1)
    assert stored(reposter) == stored(other)
    # Each reversal is linked to the overturning action and to the row it cancels.
    for row in ReputationEvent.objects.filter(kind=K.REVERSAL):
        assert row.moderation_action_id == entry.pk
        assert row.reverses.user_id == row.user_id
        assert (row.positive, row.negative) == (-row.reverses.positive, -row.reverses.negative)


@pytest.mark.parametrize(
    ("before", "expected_status"),
    [
        (PostStatus.VERIFIED_FALSE, PostStatus.VERIFIED_FALSE),
        (PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_TRUE),
    ],
)
def test_restore_reverses_the_removal_and_keeps_the_label(before, expected_status):
    post = pending_fact()
    reposter = reposted(post)
    label_by_pipeline(post, TRUE_95 if before == PostStatus.VERIFIED_TRUE else FALSE_95)
    Post.objects.filter(pk=post.pk).update(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=before,
        review_started_at=timezone.now(),
    )
    [reporter] = open_reports(post)
    moderation.remove_post(post.pk, moderator=moderator_user())
    label = K.FACT_TRUE if before == PostStatus.VERIFIED_TRUE else K.FACT_FALSE
    assert kinds(post.author) == [label, K.POST_REMOVED]
    moderation.file_appeal(author=post.author, post_id=post.pk)
    moderation.restore_post(post.pk, moderator=moderator_user())
    assert Post.objects.get(pk=post.pk).status == expected_status
    assert kinds(post.author) == [label, K.POST_REMOVED, K.REVERSAL]
    assert kinds(post.author, include_reversed=False) == [label]
    assert K.REPOST_REMOVED not in kinds(reposter, include_reversed=False)
    assert kinds(reporter) == [K.REPORT_UPHELD, K.REVERSAL]
    author, [other] = control(before, reposters=1)
    assert stored(post.author) == stored(author)
    assert stored(reposter) == stored(other)
    assert stored(reporter) == (50, 0)


@pytest.mark.parametrize("checked", [False, True])
def test_restore_to_pending_or_to_review_leaves_no_removal_events(checked):
    post = pending_fact()
    if checked:
        # The pipeline had its say: Restore sends it to review, not back to `pending`.
        Post.objects.filter(pk=post.pk).update(pipeline_checked_at=timezone.now())
    moderation.remove_post(post.pk, moderator=moderator_user())
    moderation.file_appeal(author=post.author, post_id=post.pk)
    moderation.restore_post(post.pk, moderator=moderator_user())
    restored = Post.objects.get(pk=post.pk)
    assert restored.status == (PostStatus.UNDER_REVIEW if checked else PostStatus.PENDING)
    assert kinds(post.author) == [K.POST_REMOVED, K.REVERSAL]
    assert stored(post.author) == (50, 0)


def test_remove_on_a_label_appeal_keeps_the_false_and_adds_the_removal():
    post = pending_fact()
    label_by_pipeline(post, FALSE_95)
    moderation.file_appeal(author=post.author, post_id=post.pk)
    entry = moderation.remove_post(post.pk, moderator=moderator_user())
    assert entry.appeal.status == AppealStatus.UPHELD
    assert kinds(post.author) == [K.FACT_FALSE, K.POST_REMOVED]
    assert stored(post.author) == (scoring.score(0, 3), 2) == (38, 2)


# ---------- what writes nothing ----------


def test_keep_removed_writes_nothing():
    post = pending_fact()
    label_by_pipeline(post, FALSE_95)
    moderation.remove_post(post.pk, moderator=moderator_user())
    moderation.file_appeal(author=post.author, post_id=post.pk)
    before = ReputationEvent.objects.count()
    moderation.keep_removed(post.pk, moderator=moderator_user())
    assert ReputationEvent.objects.count() == before


def test_upholding_a_label_appeal_with_mark_false_writes_nothing():
    post = pending_fact()
    label_by_pipeline(post, FALSE_95)
    moderation.file_appeal(author=post.author, post_id=post.pk)
    before = ReputationEvent.objects.count()
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert ReputationEvent.objects.count() == before


def test_dismissing_the_reports_of_a_post_also_flagged_by_the_pipeline_writes_nothing():
    post = reported_fact(flag=FlaggedReason.BOTH)
    open_reports(post)
    moderation.dismiss_reports(post.pk, moderator=moderator_user())
    assert Post.objects.get(pk=post.pk).status == PostStatus.UNDER_REVIEW
    assert ReputationEvent.objects.count() == 0


def test_dismissing_back_to_a_label_that_already_counted_writes_nothing():
    post = pending_fact()
    label_by_pipeline(post, TRUE_95)
    Post.objects.filter(pk=post.pk).update(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.VERIFIED_TRUE,
        review_started_at=timezone.now(),
    )
    open_reports(post)
    moderation.dismiss_reports(post.pk, moderator=moderator_user())
    assert kinds(post.author) == [K.FACT_TRUE]


def test_settling_the_same_state_again_writes_nothing():
    post = pending_fact()
    reposted(post)
    label_by_pipeline(post, FALSE_95)
    before = ReputationEvent.objects.count()
    post = Post.objects.get(pk=post.pk)
    assert services.settle_post(post, now=timezone.now()) == []
    assert ReputationEvent.objects.count() == before == 2


def test_a_resent_pipeline_result_is_ignored_and_counts_nothing():
    post = pending_fact()
    label_by_pipeline(post, TRUE_95)
    assert label_by_pipeline(post, TRUE_95) == Outcome.IGNORED
    assert kinds(post.author) == [K.FACT_TRUE]


@pytest.mark.parametrize("result", [LOW_40, TRUE_95, FALSE_95])
def test_a_review_freezes_the_score(result):
    """A low result sends a pending fact to review; a result for a fact under review for reports
    is held for the moderator: nothing is recorded either way."""
    sent_to_review = pending_fact()
    assert label_by_pipeline(sent_to_review, LOW_40) == Outcome.ENTERED_REVIEW
    held = reported_fact()
    assert label_by_pipeline(held, result) == Outcome.UPDATED_REVIEW
    assert ReputationEvent.objects.count() == 0


# ---------- timing and privacy ----------


def test_a_late_true_stays_private_until_a_dismiss_makes_it_public():
    post = reported_fact()
    label_by_pipeline(post, TRUE_95)  # held in `pre_review_status`
    assert kinds(post.author) == []
    later = timezone.now() + timedelta(hours=1)
    open_reports(post)
    moderation.dismiss_reports(post.pk, moderator=moderator_user(), now=later)
    [row] = rows_of(post.author)
    assert (row.kind, row.created_at) == (K.FACT_TRUE, later)  # dated when it became public


def test_a_repost_undone_before_the_verdict_gets_nothing():
    post = pending_fact()
    reposter = reposted(post)
    social_services.unrepost(user=reposter, post_id=post.pk)
    label_by_pipeline(post, TRUE_95)
    assert kinds(reposter) == []


def test_a_repost_undone_after_the_verdict_keeps_its_row_and_moves_on_a_relabel():
    post = pending_fact()
    reposter = reposted(post)
    label_by_pipeline(post, TRUE_95)
    social_services.unrepost(user=reposter, post_id=post.pk)
    assert kinds(reposter) == [K.REPOST_TRUE]
    Post.objects.filter(pk=post.pk).update(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.VERIFIED_TRUE,
        review_started_at=timezone.now(),
    )
    open_reports(post)
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert kinds(reposter) == [K.REPOST_TRUE, K.REVERSAL, K.REPOST_FALSE]


def test_a_repost_made_under_review_counts_when_the_review_ends():
    """Default 3: the timing rule is literal (`status_at_repost` `under_review` counts)."""
    post = reported_fact(pre=PostStatus.PENDING)
    reposter = reposted(post)
    open_reports(post)
    moderation.mark_false(post.pk, moderator=moderator_user())
    assert kinds(reposter) == [K.REPOST_FALSE]


def test_a_deleted_post_keeps_its_events():
    post = pending_fact()
    reposter = reposted(post)
    label_by_pipeline(post, FALSE_95)
    post_services.delete_post(post_id=post.pk, user=post.author)
    assert kinds(post.author) == [K.FACT_FALSE]
    assert kinds(reposter) == [K.REPOST_FALSE]
    assert stored(post.author) == (45, 1)
    assert ReputationEvent.objects.filter(post_id=post.pk).count() == 2


def test_a_pre_11b_post_is_healed_by_its_next_action():
    """Decision 7: no backfill. A post labelled before the ledger existed gets its missing event
    when a moderator next acts on it, dated that day."""
    post = reported_fact(pre=PostStatus.VERIFIED_FALSE, flag=FlaggedReason.REPORTS)
    open_reports(post)
    moderation.dismiss_reports(post.pk, moderator=moderator_user())
    assert kinds(post.author) == [K.FACT_FALSE]


# ---------- bookkeeping ----------


def test_the_sample_counts_own_post_events_and_the_score_shows_at_three():
    author = VerifiedUserFactory()
    for i in range(3):
        post = pending_fact(author)
        reposted(post)
        label_by_pipeline(post, TRUE_95)
        score, sample = stored(author)
        assert sample == i + 1
        assert scoring.public_score(score, sample) == (None if i < 2 else 62)


def test_a_reversal_takes_its_event_out_of_the_sample():
    post = pending_fact()
    moderation.remove_post(post.pk, moderator=moderator_user())
    assert stored(post.author) == (42, 1)
    moderation.file_appeal(author=post.author, post_id=post.pk)
    moderation.restore_post(post.pk, moderator=moderator_user())
    assert stored(post.author) == (50, 0)


def test_score_after_runs_through_the_users_rows_in_order():
    author = VerifiedUserFactory()
    true_post, false_post = pending_fact(author), pending_fact(author)
    label_by_pipeline(true_post, TRUE_95)
    label_by_pipeline(false_post, FALSE_95)
    moderation.remove_post(false_post.pk, moderator=moderator_user())
    assert [row.score_after for row in rows_of(author)] == [
        scoring.score(1, 0),
        scoring.score(1, 1),
        scoring.score(1, 3),
    ]
    assert stored(author) == (scoring.score(1, 3), 3)


def test_times_stay_strictly_increasing_when_an_older_now_arrives():
    """A writer that waited for a lock may carry a `now` older than the person's last row."""
    author = VerifiedUserFactory()
    now = timezone.now()
    label_by_pipeline(pending_fact(author), TRUE_95, now=now)
    label_by_pipeline(pending_fact(author), TRUE_95, now=now - timedelta(minutes=5))
    label_by_pipeline(pending_fact(author), TRUE_95, now=now)
    times = [row.created_at for row in rows_of(author)]
    tick = timedelta(microseconds=1)
    assert times == [now, now + tick, now + 2 * tick]


def test_one_settle_writes_reversals_before_additions_with_increasing_times():
    post = pending_fact()
    label_by_pipeline(post, TRUE_95)
    Post.objects.filter(pk=post.pk).update(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.VERIFIED_TRUE,
        review_started_at=timezone.now(),
    )
    open_reports(post)
    moderation.mark_false(post.pk, moderator=moderator_user())
    rows = rows_of(post.author)
    assert [r.kind for r in rows] == [K.FACT_TRUE, K.REVERSAL, K.FACT_FALSE]
    assert rows[1].created_at < rows[2].created_at
    assert [r.score_after for r in rows] == [55, 50, 45]


def test_settle_returns_the_rows_it_wrote():
    post = pending_fact()
    reposter = reposted(post)
    Post.objects.filter(pk=post.pk).update(status=PostStatus.VERIFIED_TRUE)
    post = Post.objects.get(pk=post.pk)
    written = services.settle_post(post, now=timezone.now())
    assert {(row.user_id, row.kind) for row in written} == {
        (post.author_id, K.FACT_TRUE),
        (reposter.pk, K.REPOST_TRUE),
    }
    assert all(row.pk for row in written)


# ---------- mechanics ----------


@pytest.mark.django_db(transaction=True)
def test_settle_post_refuses_to_run_outside_a_transaction():
    post = pending_fact()
    with pytest.raises(RuntimeError, match="inside the caller's transaction"):
        services.settle_post(post, now=timezone.now())


def test_the_users_are_locked_sorted_with_for_no_key_update_after_the_post():
    post = reported_fact()
    open_reports(post, 3)
    reposted(post)
    with CaptureQueriesContext(connection) as queries:
        moderation.mark_false(post.pk, moderator=moderator_user())
    sql = [q["sql"] for q in queries]
    post_lock = next(i for i, q in enumerate(sql) if 'FROM "posts_post"' in q and "FOR " in q)
    user_locks = [i for i, q in enumerate(sql) if 'FROM "accounts_user"' in q and "FOR " in q]
    assert len(user_locks) == 1
    lock = sql[user_locks[0]]
    assert lock.rstrip().endswith("FOR NO KEY UPDATE")
    assert 'ORDER BY "accounts_user"."id" ASC' in lock
    assert post_lock < user_locks[0]
    # The cap is read after the users' lock, and so are the totals.
    cap = next(i for i, q in enumerate(sql) if "report_upheld" in q and "COUNT" in q)
    totals = next(i for i, q in enumerate(sql) if 'SUM("reputation_reputationevent"' in q)
    assert user_locks[0] < cap < totals


def test_nothing_to_do_locks_and_writes_nothing():
    post = reported_fact(pre=PostStatus.VERIFIED_TRUE)
    reposted(post)
    with CaptureQueriesContext(connection) as queries:
        assert services.settle_post(post, now=timezone.now()) == []
    sql = [q["sql"] for q in queries]
    assert not any('FROM "accounts_user"' in q for q in sql)
    assert not any("INSERT" in q or "UPDATE" in q for q in sql)
    assert len(sql) == 1  # the post's rows; a review can't add, so the reposts aren't read


def test_escalate_never_settles(monkeypatch):
    calls = []
    monkeypatch.setattr(services, "settle_post", lambda *a, **k: calls.append(a))
    post = reported_fact()
    moderation.escalate(post.pk, moderator=moderator_user())
    assert calls == []


@pytest.mark.parametrize("act", ["mark_verified", "mark_false", "dismiss_reports", "remove_post"])
def test_every_other_action_settles_with_its_audit_row(monkeypatch, act):
    calls = []
    monkeypatch.setattr(
        services, "settle_post", lambda post, **kwargs: calls.append((post.pk, kwargs))
    )
    post = reported_fact()
    entry = getattr(moderation, act)(post.pk, moderator=moderator_user())
    [(post_id, kwargs)] = calls
    assert post_id == post.pk
    assert kwargs["action"] == entry
    assert kwargs["now"] == entry.created_at
    assert entry.action in {
        ActionKind.VERIFIED,
        ActionKind.MARKED_FALSE,
        ActionKind.DISMISSED_REPORT,
        ActionKind.REMOVED,
    }


def test_an_opinion_with_reports_removed_credits_its_reporters():
    post = reported_opinion()
    [reporter] = open_reports(post)
    moderation.remove_post(post.pk, moderator=moderator_user())
    assert kinds(post.author) == [K.POST_REMOVED]
    assert kinds(reporter) == [K.REPORT_UPHELD]


def test_a_label_that_flips_twice_ends_where_the_last_verdict_says():
    """TRUE, then FALSE through a reports review, then TRUE again through an overturned appeal:
    the reversed rows must never be reconciled a second time."""
    post = pending_fact()
    reposter = reposted(post)
    label_by_pipeline(post, TRUE_95)
    Post.objects.filter(pk=post.pk).update(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.VERIFIED_TRUE,
        review_started_at=timezone.now(),
    )
    open_reports(post)
    moderation.mark_false(post.pk, moderator=moderator_user())
    moderation.file_appeal(author=post.author, post_id=post.pk)
    moderation.mark_verified(post.pk, moderator=moderator_user())
    assert kinds(post.author) == [K.FACT_TRUE, K.REVERSAL, K.FACT_FALSE, K.REVERSAL, K.FACT_TRUE]
    assert kinds(post.author, include_reversed=False) == [K.FACT_TRUE]
    assert kinds(reposter, include_reversed=False) == [K.REPOST_TRUE]
    author, [other] = control(PostStatus.VERIFIED_TRUE, reposters=1)
    assert stored(post.author) == stored(author) == (55, 1)
    assert stored(reposter) == stored(other)
    assert not services.pending_changes(Post.objects.get(pk=post.pk))


def test_the_sample_leaves_out_rows_reversed_by_an_earlier_settle():
    """The totals of a later write must not count an own-post row that was reversed before."""
    author = VerifiedUserFactory()
    removed = pending_fact(author)
    moderation.remove_post(removed.pk, moderator=moderator_user())
    moderation.file_appeal(author=author, post_id=removed.pk)
    moderation.restore_post(removed.pk, moderator=moderator_user())
    assert stored(author) == (50, 0)
    label_by_pipeline(pending_fact(author), TRUE_95)
    assert stored(author) == (55, 1)
    assert rows_of(author)[-1].score_after == 55
