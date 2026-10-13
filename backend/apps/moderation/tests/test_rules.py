"""The pure rules (no database): every action against every starting state the checks allow,
compared with ARCHITECTURE §4 written out a second time, per action rather than per check.
Part 11 adds Restore, Keep removed, the open appeal every call takes, and the rule that the
moderator who made the first decision can't resolve its appeal (seniors and superusers can)."""

import itertools
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from apps.accounts.models import Role
from apps.moderation import rules
from apps.moderation.models import ActionKind, AppealKind, AppealStatus
from apps.moderation.rules import Act
from apps.pipeline.routing import MAX_ATTEMPTS
from apps.posts.models import FlaggedReason, PostStatus, PostType, VerdictSource
from apps.reports.models import ReportStatus

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
STARTED = NOW - timedelta(hours=5)
ESCALATED = NOW - timedelta(hours=1)
MODERATOR = SimpleNamespace(pk="mod", is_superuser=False, role=Role.MODERATOR)
SENIOR = SimpleNamespace(pk="senior", is_superuser=False, role=Role.SENIOR_MODERATOR)
SUPERUSER = SimpleNamespace(pk="root", is_superuser=True, role=Role.USER)
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
    pre_removal_status=None,
    pipeline_checked_at=NOW,
    pipeline_attempts=2,
):
    under_review = status == PostStatus.UNDER_REVIEW
    return SimpleNamespace(
        post_type=post_type,
        status=status,
        flagged_reason=flagged_reason,
        pre_review_status=pre_review_status,
        pre_removal_status=pre_removal_status,
        verdict_source=verdict_source,
        verdict_note="old note",
        review_started_at=STARTED if under_review else None,
        escalated_at=ESCALATED if escalated else None,
        deleted_at=NOW if deleted else None,
        author_id=author,
        moderated_by=None,
        moderated_at=None,
        pipeline_attempts=pipeline_attempts,
        pipeline_verdict="false",
        confidence_score=91,
        pipeline_next_attempt_at=None,
        pipeline_checked_at=pipeline_checked_at,
    )


def make_appeal(kind, *, original=None, status=AppealStatus.OPEN):
    return SimpleNamespace(kind=kind, status=status, original_moderator_id=original)


LABEL_APPEAL = make_appeal(AppealKind.LABEL)
REMOVAL_APPEAL = make_appeal(AppealKind.REMOVAL)


def expected_refusal(act, post, moderator, appeal):
    """§4 and the plan's table, one action at a time."""
    if post.deleted_at is not None:
        return "deleted"
    if post.author_id == moderator.pk and not moderator.is_superuser:
        return "own_post"
    under_review = post.status == PostStatus.UNDER_REVIEW
    removed = post.status == PostStatus.REMOVED
    open_removal = appeal is not None and appeal.kind == AppealKind.REMOVAL
    open_label = appeal is not None and appeal.kind == AppealKind.LABEL
    returnable = {
        PostType.OPINION: {PostStatus.PUBLISHED},
        PostType.FACT: {PostStatus.PENDING, PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE},
    }[post.post_type]
    verdict = act in (Act.MARK_VERIFIED, Act.MARK_FALSE)
    if verdict:
        if post.post_type == PostType.OPINION:
            return "opinion"
        if not under_review:
            return "not_under_review"
    elif act == Act.REMOVE:
        if removed:
            return "already_removed"
        if under_review and post.pre_review_status not in returnable:
            return "no_prior_status"
    elif act in (Act.RESTORE, Act.KEEP_REMOVED):
        if not (removed and open_removal):
            return "no_removal_appeal"
        if act == Act.RESTORE and post.pre_removal_status not in returnable:
            return "no_prior_status"
    elif act == Act.ESCALATE:
        if not (under_review or (removed and open_removal)):
            return "not_under_review"
        if post.escalated_at is not None:
            return "already_escalated"
    else:  # dismiss reports
        if not under_review:
            return "not_under_review"
        if post.flagged_reason not in (FlaggedReason.REPORTS, FlaggedReason.BOTH):
            return "no_reports"
        if (
            post.flagged_reason == FlaggedReason.REPORTS
            and post.pre_review_status not in returnable
        ):
            return "no_prior_status"
    resolves = (
        act in (Act.RESTORE, Act.KEEP_REMOVED)
        or (verdict or act == Act.REMOVE)
        and under_review
        and open_label
    )
    if (
        resolves
        and appeal.original_moderator_id == moderator.pk
        and not moderator.is_superuser
        and moderator.role != Role.SENIOR_MODERATOR
    ):
        return "original_moderator"
    return None


def every_starting_state():
    """`(post, open appeal)` for every combination of the columns the rules read that the database
    checks accept (plus the review clock being set exactly while under review).

    The appeal is none, a label appeal or a removal appeal, each with no original moderator and
    with the moderator the matrix uses. Removed posts also walk `pre_removal_status` and whether the
    pipeline had its say, but with the other columns cut down to the ones that matter for them, so
    the matrix doesn't grow twentyfold.
    """
    appeals = [
        None,
        LABEL_APPEAL,
        REMOVAL_APPEAL,
        make_appeal(AppealKind.LABEL, original=MODERATOR.pk),
        make_appeal(AppealKind.REMOVAL, original=MODERATOR.pk),
    ]
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
        # A removed post is walked again below, with its appeal.
        for appeal in [None] if status == PostStatus.REMOVED else appeals:
            yield (
                make_post(
                    post_type=post_type,
                    status=status,
                    flagged_reason=flag,
                    pre_review_status=pre,
                    verdict_source=source,
                    deleted=deleted,
                    escalated=escalated,
                ),
                appeal,
            )
    for post_type, flag, source, deleted, escalated, pre_removal, said in itertools.product(
        PostType.values,
        [None, FlaggedReason.APPEAL],
        [None, VerdictSource.MODERATOR],
        [False, True],
        [False, True],
        [None, *PostStatus.values],
        [False, True],
    ):
        for appeal in appeals:
            yield (
                make_post(
                    post_type=post_type,
                    status=PostStatus.REMOVED,
                    flagged_reason=flag,
                    pre_review_status=None,
                    verdict_source=source,
                    deleted=deleted,
                    escalated=escalated,
                    pre_removal_status=pre_removal,
                    pipeline_checked_at=NOW if said else None,
                ),
                appeal,
            )


@pytest.mark.parametrize("act", list(Act))
@pytest.mark.parametrize(
    "who", ["other_moderator", "own_post", "own_post_superuser", "senior", "superuser"]
)
def test_refusals_match_the_tables_for_every_starting_state(act, who):
    moderator = {
        "other_moderator": MODERATOR,
        "own_post": MODERATOR,
        "own_post_superuser": SUPERUSER,
        "senior": SENIOR,
        "superuser": SUPERUSER,
    }[who]
    # The two "own post" rows need the author to be the moderator; the rest are somebody else's,
    # so the original moderator of an appeal (`mod`) is somebody else too, unless it is them.
    checked = 0
    for post, appeal in every_starting_state():
        if who.startswith("own_post"):
            post.author_id = moderator.pk
        got = rules.refusal(act, post, moderator, appeal=appeal)
        assert (got.code if got else None) == expected_refusal(act, post, moderator, appeal), (
            vars(post),
            appeal,
        )
        checked += 1
    assert checked > 10000  # the loop really walked the matrix


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
        rules.NO_REMOVAL_APPEAL,
        rules.ORIGINAL_MODERATOR,
    ]
    assert len({r.code for r in all_refusals}) == 10
    assert all(r.text and r.text == r.text.lower() for r in all_refusals)


def test_the_first_matching_check_wins():
    deleted_own = make_post(deleted=True, author=MODERATOR.pk, post_type=PostType.OPINION)
    assert rules.refusal(Act.MARK_FALSE, deleted_own, MODERATOR, appeal=None) is rules.DELETED
    own_opinion = make_post(author=MODERATOR.pk, post_type=PostType.OPINION, flagged_reason=None)
    assert rules.refusal(Act.MARK_FALSE, own_opinion, MODERATOR, appeal=None) is rules.OWN_POST
    opinion_published = make_post(
        post_type=PostType.OPINION,
        status=PostStatus.PUBLISHED,
        flagged_reason=None,
        pre_review_status=None,
    )
    assert (
        rules.refusal(Act.MARK_VERIFIED, opinion_published, MODERATOR, appeal=None) is rules.OPINION
    )
    # The state beats the appeal rule: the moderator who removed a post can't be told "you made
    # the first decision" about a post that has no open appeal, and a post that can't take the act
    # says why first.
    mine = make_appeal(AppealKind.REMOVAL, original=MODERATOR.pk)
    pending = make_post(status=PostStatus.PENDING, flagged_reason=None, pre_review_status=None)
    assert rules.refusal(Act.RESTORE, pending, MODERATOR, appeal=mine) is rules.NO_REMOVAL_APPEAL


def test_a_superuser_may_act_on_their_own_post_but_not_on_a_deleted_one():
    mine = make_post(author=SUPERUSER.pk)
    assert rules.refusal(Act.REMOVE, mine, SUPERUSER, appeal=None) is None
    deleted = make_post(author=SUPERUSER.pk, deleted=True)
    assert rules.refusal(Act.REMOVE, deleted, SUPERUSER, appeal=None)


def test_the_appeal_is_a_required_keyword():
    with pytest.raises(TypeError):
        rules.refusal(Act.REMOVE, make_post(), MODERATOR)  # a call that forgets it fails loudly


# ---------- the appeal rules ----------


def removed(**fields):
    fields.setdefault("flagged_reason", FlaggedReason.APPEAL)
    fields.setdefault("pre_review_status", None)
    fields.setdefault("pre_removal_status", PostStatus.VERIFIED_TRUE)
    return make_post(status=PostStatus.REMOVED, **fields)


def test_restore_and_keep_removed_need_a_removed_post_with_an_open_removal_appeal():
    for act in (Act.RESTORE, Act.KEEP_REMOVED):
        assert rules.refusal(act, removed(), MODERATOR, appeal=REMOVAL_APPEAL) is None
        assert rules.refusal(act, removed(), MODERATOR, appeal=None) is rules.NO_REMOVAL_APPEAL
        # A label appeal is not a removal appeal; a resolved appeal is not open.
        assert rules.refusal(act, removed(), MODERATOR, appeal=LABEL_APPEAL) is (
            rules.NO_REMOVAL_APPEAL
        )
        done = make_appeal(AppealKind.REMOVAL, status=AppealStatus.UPHELD)
        assert rules.refusal(act, removed(), MODERATOR, appeal=done) is rules.NO_REMOVAL_APPEAL
        assert rules.refusal(act, make_post(), MODERATOR, appeal=REMOVAL_APPEAL) is (
            rules.NO_REMOVAL_APPEAL
        )


def test_restore_needs_a_status_the_post_could_return_to_but_keep_removed_does_not():
    post = removed(pre_removal_status=None)
    assert rules.refusal(Act.RESTORE, post, MODERATOR, appeal=REMOVAL_APPEAL) is (
        rules.NO_PRIOR_STATUS
    )
    assert rules.refusal(Act.KEEP_REMOVED, post, MODERATOR, appeal=REMOVAL_APPEAL) is None
    # A fact never returns to `published`, an opinion never to a fact status.
    fact = removed(pre_removal_status=PostStatus.PUBLISHED)
    assert rules.refusal(Act.RESTORE, fact, MODERATOR, appeal=REMOVAL_APPEAL) is (
        rules.NO_PRIOR_STATUS
    )
    opinion = removed(post_type=PostType.OPINION, pre_removal_status=PostStatus.PENDING)
    assert rules.refusal(Act.RESTORE, opinion, MODERATOR, appeal=REMOVAL_APPEAL) is (
        rules.NO_PRIOR_STATUS
    )
    opinion_ok = removed(post_type=PostType.OPINION, pre_removal_status=PostStatus.PUBLISHED)
    assert rules.refusal(Act.RESTORE, opinion_ok, MODERATOR, appeal=REMOVAL_APPEAL) is None


def test_escalate_is_offered_on_a_removed_post_only_with_an_open_removal_appeal():
    assert rules.refusal(Act.ESCALATE, removed(), MODERATOR, appeal=REMOVAL_APPEAL) is None
    assert rules.refusal(Act.ESCALATE, removed(), MODERATOR, appeal=None) is (
        rules.NOT_UNDER_REVIEW
    )
    assert rules.refusal(Act.ESCALATE, removed(), MODERATOR, appeal=LABEL_APPEAL) is (
        rules.NOT_UNDER_REVIEW
    )
    twice = removed(escalated=True)
    assert rules.refusal(Act.ESCALATE, twice, MODERATOR, appeal=REMOVAL_APPEAL) is (
        rules.ALREADY_ESCALATED
    )


@pytest.mark.parametrize(
    "act",
    [Act.MARK_VERIFIED, Act.MARK_FALSE, Act.REMOVE],
)
def test_a_label_appeal_cannot_be_resolved_by_the_moderator_who_made_the_first_decision(act):
    under_appeal = make_post(
        flagged_reason=FlaggedReason.APPEAL, pre_review_status=PostStatus.VERIFIED_FALSE
    )
    mine = make_appeal(AppealKind.LABEL, original=MODERATOR.pk)
    assert rules.refusal(act, under_appeal, MODERATOR, appeal=mine) is rules.ORIGINAL_MODERATOR
    # Somebody else, a senior and a superuser can; so can anyone when nobody is recorded.
    other = SimpleNamespace(pk="other", is_superuser=False, role=Role.MODERATOR)
    assert rules.refusal(act, under_appeal, other, appeal=mine) is None
    assert rules.refusal(act, under_appeal, MODERATOR, appeal=LABEL_APPEAL) is None
    senior_made_it = make_appeal(AppealKind.LABEL, original=SENIOR.pk)
    assert rules.refusal(act, under_appeal, SENIOR, appeal=senior_made_it) is None
    root_made_it = make_appeal(AppealKind.LABEL, original=SUPERUSER.pk)
    assert rules.refusal(act, under_appeal, SUPERUSER, appeal=root_made_it) is None


@pytest.mark.parametrize("act", [Act.RESTORE, Act.KEEP_REMOVED])
def test_a_removal_appeal_cannot_be_resolved_by_the_moderator_who_removed_the_post(act):
    mine = make_appeal(AppealKind.REMOVAL, original=MODERATOR.pk)
    assert rules.refusal(act, removed(), MODERATOR, appeal=mine) is rules.ORIGINAL_MODERATOR
    assert rules.refusal(act, removed(), SENIOR, appeal=mine) is None
    assert rules.refusal(act, removed(), SUPERUSER, appeal=mine) is None


def test_the_rule_does_not_apply_to_escalating_or_to_a_post_with_no_open_appeal():
    mine_label = make_appeal(AppealKind.LABEL, original=MODERATOR.pk)
    under_appeal = make_post(
        flagged_reason=FlaggedReason.APPEAL, pre_review_status=PostStatus.VERIFIED_FALSE
    )
    # Escalating is what the first moderator should do.
    assert rules.refusal(Act.ESCALATE, under_appeal, MODERATOR, appeal=mine_label) is None
    mine_removal = make_appeal(AppealKind.REMOVAL, original=MODERATOR.pk)
    assert rules.refusal(Act.ESCALATE, removed(), MODERATOR, appeal=mine_removal) is None
    # Not flagged for an appeal and no appeal row: an ordinary review (and a flagged post with no
    # row, from a factory or a test, doesn't crash).
    flagged_without_row = make_post(
        flagged_reason=FlaggedReason.APPEAL, pre_review_status=PostStatus.VERIFIED_FALSE
    )
    assert rules.refusal(Act.MARK_FALSE, flagged_without_row, MODERATOR, appeal=None) is None
    # Dismiss never applies to a post flagged for an appeal alone.
    assert rules.refusal(Act.DISMISS_REPORTS, under_appeal, MODERATOR, appeal=mine_label) is (
        rules.NO_REPORTS
    )


def test_a_removal_of_a_post_under_a_label_appeal_is_a_decision_on_that_appeal():
    under_appeal = make_post(
        flagged_reason=FlaggedReason.APPEAL, pre_review_status=PostStatus.VERIFIED_FALSE
    )
    mine = make_appeal(AppealKind.LABEL, original=MODERATOR.pk)
    assert rules.refusal(Act.REMOVE, under_appeal, MODERATOR, appeal=mine) is (
        rules.ORIGINAL_MODERATOR
    )
    # A removal of a post with no open appeal carries no appeal rule.
    reported = make_post()
    assert rules.refusal(Act.REMOVE, reported, MODERATOR, appeal=None) is None


# ---------- transition ----------


def run(act, post, public_note="", appeal=None):
    return rules.transition(
        act, post, moderator=MODERATOR, now=NOW, appeal=appeal, public_note=public_note
    )


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
    for post, appeal in every_starting_state():
        if rules.refusal(act, post, MODERATOR, appeal=appeal) is not None:
            continue
        before = dict(vars(post))
        run(act, post, appeal=appeal)
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
    # Restore and Keep removed need a removed post with an open appeal: a small corner.
    assert walked > (50 if act in rules.REMOVAL_APPEAL_ACTS else 100)


@pytest.mark.parametrize("act", list(Act))
def test_every_allowed_transition_lands_on_a_state_the_database_accepts(act):
    """The result must satisfy the checks that a wrong `pre_review_status` would break."""
    for post, appeal in every_starting_state():
        if rules.refusal(act, post, MODERATOR, appeal=appeal) is not None:
            continue
        run(act, post, appeal=appeal)
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
        # A flag outside review is only the removal appeal's (the post stays removed and listed).
        assert (
            post.flagged_reason is None
            or post.status == PostStatus.UNDER_REVIEW
            or (post.status == PostStatus.REMOVED and post.flagged_reason == FlaggedReason.APPEAL)
        )


# ---------- appeals: what each action does to the appeal and the post ----------


def label_appeal_post(**fields):
    fields.setdefault("flagged_reason", FlaggedReason.APPEAL)
    fields.setdefault("pre_review_status", PostStatus.VERIFIED_FALSE)
    fields.setdefault("verdict_source", VerdictSource.PIPELINE)
    return make_post(**fields)


@pytest.mark.parametrize(
    ("act", "post_status", "appeal_status"),
    [
        (Act.MARK_VERIFIED, PostStatus.VERIFIED_TRUE, AppealStatus.OVERTURNED),
        (Act.MARK_FALSE, PostStatus.VERIFIED_FALSE, AppealStatus.UPHELD),
        (Act.REMOVE, PostStatus.REMOVED, AppealStatus.UPHELD),
    ],
)
def test_a_decision_on_a_post_under_a_label_appeal_resolves_the_appeal(
    act, post_status, appeal_status
):
    post = label_appeal_post(escalated=True)
    effect = run(act, post, appeal=LABEL_APPEAL)
    assert post.status == post_status
    assert effect.appeal_status == appeal_status
    assert effect.from_status == PostStatus.UNDER_REVIEW
    assert (post.flagged_reason, post.pre_review_status) == (None, None)
    assert (post.review_started_at, post.escalated_at) == (None, None)


@pytest.mark.parametrize("act", [Act.MARK_VERIFIED, Act.MARK_FALSE, Act.REMOVE])
def test_the_same_decisions_resolve_no_appeal_when_there_is_none(act):
    assert run(act, make_post(), appeal=None).appeal_status is None


def test_dismissing_or_escalating_never_resolves_an_appeal():
    assert run(Act.DISMISS_REPORTS, make_post(), appeal=LABEL_APPEAL).appeal_status is None
    assert run(Act.ESCALATE, label_appeal_post(), appeal=LABEL_APPEAL).appeal_status is None
    assert run(Act.ESCALATE, removed(), appeal=REMOVAL_APPEAL).appeal_status is None


def test_escalating_a_removed_post_only_stamps_it():
    post = removed()
    effect = run(Act.ESCALATE, post, appeal=REMOVAL_APPEAL)
    assert post.escalated_at == NOW
    assert (post.status, post.flagged_reason) == (PostStatus.REMOVED, FlaggedReason.APPEAL)
    assert post.pre_removal_status == PostStatus.VERIFIED_TRUE  # kept
    assert effect == rules.Effect(
        ActionKind.ESCALATED, PostStatus.REMOVED, PostStatus.REMOVED, None, None
    )


@pytest.mark.parametrize(
    "target", [PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE, PostStatus.PENDING]
)
def test_restore_puts_a_fact_back_to_the_status_it_had(target):
    # A pending fact that the pipeline never finished is checked as usual.
    post = removed(
        pre_removal_status=target, escalated=True, pipeline_checked_at=None, pipeline_attempts=1
    )
    effect = run(Act.RESTORE, post, appeal=REMOVAL_APPEAL)
    assert post.status == target
    assert (post.flagged_reason, post.pre_removal_status, post.escalated_at) == (None, None, None)
    assert (post.pre_review_status, post.review_started_at) == (None, None)
    assert effect == rules.Effect(
        ActionKind.RESTORED, PostStatus.REMOVED, target, None, AppealStatus.OVERTURNED
    )
    assert (post.moderated_by, post.moderated_at) == (MODERATOR, NOW)


def test_restore_puts_an_opinion_back_to_published():
    post = removed(post_type=PostType.OPINION, pre_removal_status=PostStatus.PUBLISHED)
    run(Act.RESTORE, post, appeal=REMOVAL_APPEAL)
    assert post.status == PostStatus.PUBLISHED


@pytest.mark.parametrize(
    ("checked_at", "attempts"), [(NOW, 1), (None, MAX_ATTEMPTS), (NOW, MAX_ATTEMPTS)]
)
def test_restore_of_a_pending_fact_the_pipeline_already_had_its_say_on_goes_to_review(
    checked_at, attempts
):
    post = removed(
        pre_removal_status=PostStatus.PENDING,
        escalated=True,
        pipeline_checked_at=checked_at,
        pipeline_attempts=attempts,
    )
    effect = run(Act.RESTORE, post, appeal=REMOVAL_APPEAL)
    assert post.status == PostStatus.UNDER_REVIEW
    assert post.flagged_reason == FlaggedReason.PIPELINE
    assert post.pre_review_status == PostStatus.PENDING
    assert post.review_started_at == NOW  # the clock starts now
    assert (post.pre_removal_status, post.escalated_at) == (None, None)
    assert effect.to_status == PostStatus.UNDER_REVIEW
    assert effect.appeal_status == AppealStatus.OVERTURNED


def test_a_restored_post_keeps_its_label_its_source_and_every_pipeline_field():
    post = removed(
        pre_removal_status=PostStatus.VERIFIED_FALSE, verdict_source=VerdictSource.MODERATOR
    )
    before = dict(vars(post))
    run(Act.RESTORE, post, appeal=REMOVAL_APPEAL)
    for field in (
        "verdict_source",
        "verdict_note",
        "confidence_score",
        "pipeline_attempts",
        "pipeline_verdict",
        "pipeline_checked_at",
        "pipeline_next_attempt_at",
    ):
        assert getattr(post, field) == before[field]


def test_keep_removed_closes_the_appeal_and_clears_the_flag_and_the_escalation():
    post = removed(escalated=True)
    effect = run(Act.KEEP_REMOVED, post, appeal=REMOVAL_APPEAL)
    assert post.status == PostStatus.REMOVED
    assert (post.flagged_reason, post.escalated_at) == (None, None)
    assert post.pre_removal_status == PostStatus.VERIFIED_TRUE  # kept: nothing is undone
    assert effect == rules.Effect(
        ActionKind.KEPT_REMOVED, PostStatus.REMOVED, PostStatus.REMOVED, None, AppealStatus.UPHELD
    )
    assert (post.moderated_by, post.moderated_at) == (MODERATOR, NOW)


def test_the_appeal_is_a_required_keyword_of_transition_too():
    with pytest.raises(TypeError):
        rules.transition(Act.REMOVE, make_post(), moderator=MODERATOR, now=NOW)
