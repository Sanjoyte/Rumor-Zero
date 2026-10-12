"""The pure rules (no database): every action against every starting state the checks allow,
compared with ARCHITECTURE §4 written out a second time, per action rather than per check."""

import itertools
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from apps.moderation import rules
from apps.moderation.models import ActionKind
from apps.moderation.rules import Act
from apps.posts.models import FlaggedReason, PostStatus, PostType, VerdictSource
from apps.reports.models import ReportStatus

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
STARTED = NOW - timedelta(hours=5)
ESCALATED = NOW - timedelta(hours=1)
MODERATOR = SimpleNamespace(pk="mod", is_superuser=False)
SUPERUSER = SimpleNamespace(pk="root", is_superuser=True)
OTHER_AUTHOR = "someone-else"

# Every column `rules.transition` is allowed to write; nothing else may change.
ALLOWED = {
    "status",
    "flagged_reason",
    "pre_review_status",
    "pre_removal_status",
    "review_started_at",
    "escalated_at",
    "verdict_source",
    "verdict_note",
    "moderated_by",
    "moderated_at",
}


def make_post(
    *,
    post_type=PostType.FACT,
    status=PostStatus.UNDER_REVIEW,
    flagged_reason=FlaggedReason.REPORTS,
    pre_review_status=PostStatus.PENDING,
    verdict_source=None,
    deleted=False,
    author=OTHER_AUTHOR,
    escalated=False,
):
    under_review = status == PostStatus.UNDER_REVIEW
    return SimpleNamespace(
        post_type=post_type,
        status=status,
        flagged_reason=flagged_reason,
        pre_review_status=pre_review_status,
        pre_removal_status=None,
        verdict_source=verdict_source,
        verdict_note="old note",
        review_started_at=STARTED if under_review else None,
        escalated_at=ESCALATED if escalated else None,
        deleted_at=NOW if deleted else None,
        author_id=author,
        moderated_by=None,
        moderated_at=None,
        pipeline_attempts=2,
        pipeline_verdict="false",
        confidence_score=91,
        pipeline_next_attempt_at=None,
        pipeline_checked_at=NOW,
    )


def expected_refusal(act, post, moderator):
    """§4 and the plan's table, one action at a time."""
    if post.deleted_at is not None:
        return "deleted"
    if post.author_id == moderator.pk and not moderator.is_superuser:
        return "own_post"
    under_review = post.status == PostStatus.UNDER_REVIEW
    returnable = {
        PostType.OPINION: {PostStatus.PUBLISHED},
        PostType.FACT: {PostStatus.PENDING, PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE},
    }[post.post_type]
    if act in (Act.MARK_VERIFIED, Act.MARK_FALSE):
        if post.post_type == PostType.OPINION:
            return "opinion"
        return None if under_review else "not_under_review"
    if act == Act.REMOVE:
        if post.status == PostStatus.REMOVED:
            return "already_removed"
        if under_review and post.pre_review_status not in returnable:
            return "no_prior_status"
        return None
    if not under_review:
        return "not_under_review"
    if act == Act.DISMISS_REPORTS:
        if post.flagged_reason not in (FlaggedReason.REPORTS, FlaggedReason.BOTH):
            return "no_reports"
        if (
            post.flagged_reason == FlaggedReason.REPORTS
            and post.pre_review_status not in returnable
        ):
            return "no_prior_status"
        return None
    if post.escalated_at is not None:  # escalate
        return "already_escalated"
    return None


def every_starting_state():
    """Every combination of the columns the rules read that the database checks accept (plus the
    review clock being set exactly while under review)."""
    for post_type, status, flag, pre, source, deleted, escalated in itertools.product(
        PostType.values,
        PostStatus.values,
        [None, *FlaggedReason.values],
        [None, *PostStatus.values],
        [None, *VerdictSource.values],
        [False, True],
        [False, True],
    ):
        if post_type == PostType.OPINION and status not in (
            PostStatus.PUBLISHED,
            PostStatus.UNDER_REVIEW,
            PostStatus.REMOVED,
        ):
            continue
        if post_type == PostType.FACT and status == PostStatus.PUBLISHED:
            continue
        yield make_post(
            post_type=post_type,
            status=status,
            flagged_reason=flag,
            pre_review_status=pre,
            verdict_source=source,
            deleted=deleted,
            escalated=escalated,
        )


@pytest.mark.parametrize("act", list(Act))
@pytest.mark.parametrize(
    "who",
    ["other_moderator", "own_post", "own_post_superuser"],
)
def test_refusals_match_the_tables_for_every_starting_state(act, who):
    moderator = SUPERUSER if who == "own_post_superuser" else MODERATOR
    checked = 0
    for post in every_starting_state():
        if who != "other_moderator":
            post.author_id = moderator.pk
        got = rules.refusal(act, post, moderator)
        assert (got.code if got else None) == expected_refusal(act, post, moderator), vars(post)
        checked += 1
    assert checked > 3000  # the loop really walked the matrix


def test_every_refusal_has_a_code_and_words():
    all_refusals = [
        rules.DELETED,
        rules.OWN_POST,
        rules.OPINION,
        rules.NOT_UNDER_REVIEW,
        rules.NO_REPORTS,
        rules.NO_PRIOR_STATUS,
        rules.ALREADY_REMOVED,
        rules.ALREADY_ESCALATED,
    ]
    assert len({r.code for r in all_refusals}) == 8
    assert all(r.text and r.text == r.text.lower() for r in all_refusals)


def test_the_first_matching_check_wins():
    deleted_own = make_post(deleted=True, author=MODERATOR.pk, post_type=PostType.OPINION)
    assert rules.refusal(Act.MARK_FALSE, deleted_own, MODERATOR) is rules.DELETED
    own_opinion = make_post(author=MODERATOR.pk, post_type=PostType.OPINION, flagged_reason=None)
    assert rules.refusal(Act.MARK_FALSE, own_opinion, MODERATOR) is rules.OWN_POST
    opinion_published = make_post(
        post_type=PostType.OPINION,
        status=PostStatus.PUBLISHED,
        flagged_reason=None,
        pre_review_status=None,
    )
    assert rules.refusal(Act.MARK_VERIFIED, opinion_published, MODERATOR) is rules.OPINION


def test_a_superuser_may_act_on_their_own_post_but_not_on_a_deleted_one():
    mine = make_post(author=SUPERUSER.pk)
    assert rules.refusal(Act.REMOVE, mine, SUPERUSER) is None
    assert rules.refusal(Act.REMOVE, make_post(author=SUPERUSER.pk, deleted=True), SUPERUSER)


# ---------- transition ----------


def run(act, post, public_note=""):
    return rules.transition(act, post, moderator=MODERATOR, now=NOW, public_note=public_note)


def test_mark_verified_labels_the_fact_and_ends_the_review():
    post = make_post(flagged_reason=FlaggedReason.BOTH, escalated=True)
    effect = run(Act.MARK_VERIFIED, post, "Checked against the filing")
    assert post.status == PostStatus.VERIFIED_TRUE
    assert post.verdict_source == VerdictSource.MODERATOR
    assert post.verdict_note == "Checked against the filing"
    assert (post.flagged_reason, post.pre_review_status) == (None, None)
    assert (post.review_started_at, post.escalated_at) == (None, None)
    assert (post.moderated_by, post.moderated_at) == (MODERATOR, NOW)
    assert effect == rules.Effect(
        ActionKind.VERIFIED,
        PostStatus.UNDER_REVIEW,
        PostStatus.VERIFIED_TRUE,
        ReportStatus.ACTIONED,
    )


def test_mark_false_labels_the_fact_false():
    post = make_post()
    effect = run(Act.MARK_FALSE, post)
    assert (post.status, post.verdict_source) == (
        PostStatus.VERIFIED_FALSE,
        VerdictSource.MODERATOR,
    )
    assert effect.kind == ActionKind.MARKED_FALSE
    assert effect.report_status == ReportStatus.ACTIONED


@pytest.mark.parametrize("act", [Act.MARK_VERIFIED, Act.MARK_FALSE])
def test_a_blank_public_note_clears_the_old_verdict_note(act):
    post = make_post()
    run(act, post)
    assert post.verdict_note == ""


@pytest.mark.parametrize(
    "pre", [PostStatus.PENDING, PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE]
)
def test_dismissing_reports_restores_the_status_the_post_had(pre):
    post = make_post(pre_review_status=pre, escalated=True)
    effect = run(Act.DISMISS_REPORTS, post)
    assert post.status == pre
    assert (post.flagged_reason, post.pre_review_status) == (None, None)
    assert (post.review_started_at, post.escalated_at) == (None, None)
    assert effect == rules.Effect(
        ActionKind.DISMISSED_REPORT, PostStatus.UNDER_REVIEW, pre, ReportStatus.DISMISSED
    )


def test_dismissing_reports_on_an_opinion_publishes_it_again():
    post = make_post(
        post_type=PostType.OPINION, pre_review_status=PostStatus.PUBLISHED, flagged_reason="reports"
    )
    run(Act.DISMISS_REPORTS, post)
    assert post.status == PostStatus.PUBLISHED


def test_dismissing_reports_of_a_post_also_flagged_by_the_pipeline_keeps_it_under_review():
    post = make_post(flagged_reason=FlaggedReason.BOTH, escalated=True)
    effect = run(Act.DISMISS_REPORTS, post)
    assert post.status == PostStatus.UNDER_REVIEW
    assert post.flagged_reason == FlaggedReason.PIPELINE
    assert post.pre_review_status == PostStatus.PENDING  # kept
    assert (post.review_started_at, post.escalated_at) == (STARTED, ESCALATED)  # kept
    assert effect.to_status == PostStatus.UNDER_REVIEW
    assert effect.report_status == ReportStatus.DISMISSED


@pytest.mark.parametrize(
    "pre", [PostStatus.PENDING, PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE]
)
def test_removing_a_post_under_review_remembers_the_status_before_the_review(pre):
    post = make_post(pre_review_status=pre, escalated=True)
    effect = run(Act.REMOVE, post)
    assert post.status == PostStatus.REMOVED
    assert post.pre_removal_status == pre  # not `under_review`
    assert (post.flagged_reason, post.pre_review_status) == (None, None)
    assert (post.review_started_at, post.escalated_at) == (None, None)
    assert effect == rules.Effect(
        ActionKind.REMOVED, PostStatus.UNDER_REVIEW, PostStatus.REMOVED, ReportStatus.ACTIONED
    )


@pytest.mark.parametrize(
    ("post_type", "status"),
    [
        (PostType.OPINION, PostStatus.PUBLISHED),
        (PostType.FACT, PostStatus.PENDING),
        (PostType.FACT, PostStatus.VERIFIED_TRUE),
        (PostType.FACT, PostStatus.VERIFIED_FALSE),
    ],
)
def test_removing_a_post_not_under_review_remembers_its_current_status(post_type, status):
    post = make_post(
        post_type=post_type, status=status, flagged_reason=None, pre_review_status=None
    )
    effect = run(Act.REMOVE, post)
    assert (post.status, post.pre_removal_status) == (PostStatus.REMOVED, status)
    assert effect.from_status == status


def test_escalating_only_stamps_the_post():
    post = make_post()
    effect = run(Act.ESCALATE, post)
    assert post.escalated_at == NOW
    assert post.status == PostStatus.UNDER_REVIEW and post.flagged_reason == FlaggedReason.REPORTS
    assert post.review_started_at == STARTED
    assert effect == rules.Effect(
        ActionKind.ESCALATED, PostStatus.UNDER_REVIEW, PostStatus.UNDER_REVIEW, None
    )


def test_an_unknown_action_is_a_bug_not_a_noop():
    with pytest.raises(ValueError, match="not an action"):
        run("burn", make_post())


@pytest.mark.parametrize("act", list(Act))
def test_a_transition_only_touches_the_listed_fields_and_never_the_pipeline_ones(act):
    walked = 0
    for post in every_starting_state():
        if rules.refusal(act, post, MODERATOR) is not None:
            continue
        before = dict(vars(post))
        run(act, post)
        changed = {key for key, value in vars(post).items() if before[key] != value}
        assert changed <= ALLOWED, (act, changed - ALLOWED)
        # The claim token of Part 9 and the pipeline's answer stay as they were.
        for field in (
            "pipeline_attempts",
            "pipeline_verdict",
            "confidence_score",
            "pipeline_next_attempt_at",
            "pipeline_checked_at",
        ):
            assert getattr(post, field) == before[field]
        walked += 1
    assert walked > 100


@pytest.mark.parametrize("act", list(Act))
def test_every_allowed_transition_lands_on_a_state_the_database_accepts(act):
    """The result must satisfy the checks that a wrong `pre_review_status` would break."""
    for post in every_starting_state():
        if rules.refusal(act, post, MODERATOR) is not None:
            continue
        run(act, post)
        if post.post_type == PostType.OPINION:
            assert post.status in (
                PostStatus.PUBLISHED,
                PostStatus.UNDER_REVIEW,
                PostStatus.REMOVED,
            )
        else:
            assert post.status != PostStatus.PUBLISHED
        # The queue's clock runs exactly while the post is under review.
        assert (post.status == PostStatus.UNDER_REVIEW) == (post.review_started_at is not None)
        assert post.flagged_reason is None or post.status == PostStatus.UNDER_REVIEW
