"""The pure rules of the credibility score (no database): the weight table, the formula and its
rounding, what each slot should hold, and the reconciliation over every slot, value and role
(ARCHITECTURE §4a)."""

import itertools
from decimal import Decimal

import pytest

from apps.moderation.models import ActionKind
from apps.posts.models import PostStatus
from apps.reputation import scoring
from apps.reputation.models import EventKind as K
from apps.reputation.scoring import Addition, Row, Slot, Want

D = Decimal
AUTHOR = "author"


# ---------- the weight table (ARCHITECTURE §4a, written out again) ----------


@pytest.mark.parametrize(
    ("kind", "positive", "negative"),
    [
        (K.FACT_TRUE, "1", "0"),
        (K.FACT_FALSE, "0", "1"),
        (K.EMERGENCY_FALSE, "0", "3"),
        (K.POST_REMOVED, "0", "2"),
        (K.REPORT_UPHELD, "0.25", "0"),
        (K.REPOST_TRUE, "0.25", "0"),
        (K.REPOST_FALSE, "0", "0.5"),
        (K.REPOST_EMERGENCY_FALSE, "0", "1"),
        (K.REPOST_REMOVED, "0", "0.5"),
    ],
)
def test_every_kind_has_the_weights_of_the_table(kind, positive, negative):
    assert scoring.WEIGHTS[kind] == (D(positive), D(negative))


def test_every_kind_but_the_reversal_has_weights_and_one_role():
    assert set(scoring.WEIGHTS) == set(K) - {K.REVERSAL}
    roles = [scoring.role_of(kind) for kind in scoring.WEIGHTS]
    assert roles.count(scoring.Role.AUTHOR) == 4
    assert roles.count(scoring.Role.REPOSTER) == 4
    assert roles.count(scoring.Role.REPORTER) == 1
    with pytest.raises(ValueError, match="no role"):
        scoring.role_of(K.REVERSAL)


def test_only_own_post_kinds_count_toward_the_sample():
    assert {K.FACT_TRUE, K.FACT_FALSE, K.EMERGENCY_FALSE, K.POST_REMOVED} == scoring.AUTHOR_KINDS


def test_the_constants_of_the_configuration_table():
    assert scoring.PUBLIC_AFTER == 3
    assert scoring.START_SCORE == scoring.score(0, 0) == 50
    assert scoring.REPORT_CREDIT_CAP == 4
    assert scoring.REPORT_CREDIT_WINDOW.days == 30
    assert {PostStatus.PENDING, PostStatus.UNDER_REVIEW} == scoring.REPOST_COUNTED


# ---------- the formula ----------


@pytest.mark.parametrize(
    ("p", "n", "expected"),
    [
        (0, 0, 50),
        (0, 1, 45),  # one FALSE: 45.45
        (1, 0, 55),  # one TRUE: 54.55
        (0, 3, 38),  # a FALSE emergency: 38.46
        (3, 0, 62),  # three TRUE: 61.54
        (0, 2, 42),  # two FALSE: 41.67
        (D("0.25"), 0, 51),  # one report credit: 51.22
        (100, 0, 95),
        (0, 1000, 0),
        (5000, 0, 100),
    ],
)
def test_score(p, n, expected):
    assert scoring.score(D(p), D(n)) == expected


@pytest.mark.parametrize(
    ("p", "n", "expected"),
    [
        # Exactly half-way: half up, not to even (Python's `round(12.5)` is 12).
        (0, 30, 13),  # 5 / 40 = 12.5
        (3, 51, 13),  # 8 / 64 = 12.5
        (D("2.5"), D("47.5"), 13),  # 7.5 / 60 = 12.5
        (5, 30, 22),  # 10 / 45 = 22.2: not a half, a control
        (D("0.5"), D("29.5"), 14),  # 5.5 / 40 = 13.75
        (15, 0, 80),  # 20 / 25 = 80 exactly
        (1, 7, 33),  # 6 / 18 = 33.33
    ],
)
def test_score_rounds_a_half_up_exactly(p, n, expected):
    assert scoring.score(D(p), D(n)) == expected


def test_score_matches_exact_half_up_rounding_over_a_grid():
    """Against fractions, quarter by quarter: no float anywhere."""
    from fractions import Fraction

    for p4, n4 in itertools.product(range(0, 120, 3), range(0, 120, 5)):
        value = Fraction(100 * (20 + p4), 40 + p4 + n4)
        expected = int(value + Fraction(1, 2))  # floor(x + ½) for x ≥ 0
        assert scoring.score(D(p4) / 4, D(n4) / 4) == expected


@pytest.mark.parametrize(
    ("p", "n"),
    [
        (D("-0.25"), 0),
        (0, D("-1")),
        (D("0.1"), 0),
        (0, D("0.3")),
        (D("1.125"), 0),
    ],
)
def test_score_refuses_negative_sums_and_weights_that_are_not_quarters(p, n):
    with pytest.raises(ValueError, match="multiple of 0.25"):
        scoring.score(p, n)


@pytest.mark.parametrize(
    ("sample", "shown"),
    [(0, None), (1, None), (2, None), (3, 61), (40, 61)],
)
def test_the_public_score_shows_once_three_events_count(sample, shown):
    assert scoring.public_score(61, sample) == shown


@pytest.mark.parametrize(("held", "credited"), [(0, True), (3, True), (4, False), (9, False)])
def test_the_reporter_cap_allows_four(held, credited):
    assert scoring.within_cap(held) is credited


# ---------- what each slot should hold ----------


@pytest.mark.parametrize(
    ("status", "emergency", "label", "removal"),
    [
        (PostStatus.VERIFIED_TRUE, False, Want.TRUE, Want.NONE),
        (PostStatus.VERIFIED_TRUE, True, Want.TRUE, Want.NONE),  # no emergency bonus
        (PostStatus.VERIFIED_FALSE, False, Want.FALSE, Want.NONE),
        (PostStatus.VERIFIED_FALSE, True, Want.EMERGENCY_FALSE, Want.NONE),
        (PostStatus.REMOVED, False, Want.KEEP, Want.REMOVED),
        (PostStatus.REMOVED, True, Want.KEEP, Want.REMOVED),
        (PostStatus.UNDER_REVIEW, False, Want.KEEP, Want.NONE),
        (PostStatus.UNDER_REVIEW, True, Want.KEEP, Want.NONE),
        (PostStatus.PENDING, False, Want.KEEP, Want.NONE),
        (PostStatus.PENDING, True, Want.KEEP, Want.NONE),
        (PostStatus.PUBLISHED, False, Want.KEEP, Want.NONE),
    ],
)
def test_desired_for_every_status(status, emergency, label, removal):
    assert scoring.desired(status, emergency) == {Slot.LABEL: label, Slot.REMOVAL: removal}


def test_every_status_is_mapped():
    for status, emergency in itertools.product(PostStatus.values, [False, True]):
        target = scoring.desired(status, emergency)
        assert set(target) == {Slot.LABEL, Slot.REMOVAL}


@pytest.mark.parametrize(
    ("status", "adds"),
    [
        (PostStatus.VERIFIED_TRUE, True),
        (PostStatus.VERIFIED_FALSE, True),
        (PostStatus.REMOVED, True),
        (PostStatus.UNDER_REVIEW, False),
        (PostStatus.PENDING, False),
        (PostStatus.PUBLISHED, False),
    ],
)
def test_may_add_only_when_a_slot_has_an_outcome(status, adds):
    assert scoring.may_add(scoring.desired(status, False)) is adds


# ---------- slots of rows ----------


def row(kind, user="u", *, action=None, id=None):
    return Row(
        id=id or f"{kind}-{user}",
        user_id=user,
        kind=kind,
        positive=scoring.WEIGHTS[kind][0],
        negative=scoring.WEIGHTS[kind][1],
        action=action,
    )


@pytest.mark.parametrize(
    ("kind", "action", "slot"),
    [
        (K.FACT_TRUE, None, Slot.LABEL),
        (K.FACT_FALSE, ActionKind.MARKED_FALSE, Slot.LABEL),
        (K.EMERGENCY_FALSE, None, Slot.LABEL),
        (K.REPOST_TRUE, None, Slot.LABEL),
        (K.REPOST_FALSE, None, Slot.LABEL),
        (K.REPOST_EMERGENCY_FALSE, None, Slot.LABEL),
        (K.POST_REMOVED, ActionKind.REMOVED, Slot.REMOVAL),
        (K.REPOST_REMOVED, ActionKind.REMOVED, Slot.REMOVAL),
        (K.REPORT_UPHELD, ActionKind.MARKED_FALSE, Slot.LABEL),
        (K.REPORT_UPHELD, ActionKind.REMOVED, Slot.REMOVAL),
        (K.REPORT_UPHELD, None, None),  # unknown: never touched
        (K.REPORT_UPHELD, ActionKind.VERIFIED, None),
    ],
)
def test_each_row_belongs_to_one_slot(kind, action, slot):
    assert scoring.slot_of(row(kind, action=action)) == slot


def test_a_reversal_is_never_reconciled():
    with pytest.raises(ValueError):
        scoring.slot_of(Row(id="r", user_id="u", kind=K.REVERSAL, positive=D(-1), negative=D(0)))


# ---------- changes(): the reconciliation ----------


def plan(status, rows=(), *, emergency=False, reposts=(), reporters=(), action=None):
    return scoring.changes(
        scoring.desired(status, emergency),
        list(rows),
        author_id=AUTHOR,
        reposts=reposts,
        reporters=reporters,
        action=action,
    )


def adds(changes):
    return {(a.user_id, a.kind) for a in changes.add}


def reversed_ids(changes):
    return {r.id for r in changes.reverse}


AUTHOR_KIND_FOR = {
    PostStatus.VERIFIED_TRUE: K.FACT_TRUE,
    PostStatus.VERIFIED_FALSE: K.FACT_FALSE,
}


def test_nothing_to_do_is_falsy_and_has_no_users():
    changes = plan(PostStatus.PENDING)
    assert not changes
    assert changes.user_ids == []


@pytest.mark.parametrize(
    ("status", "emergency", "kind"),
    [
        (PostStatus.VERIFIED_TRUE, False, K.FACT_TRUE),
        (PostStatus.VERIFIED_TRUE, True, K.FACT_TRUE),
        (PostStatus.VERIFIED_FALSE, False, K.FACT_FALSE),
        (PostStatus.VERIFIED_FALSE, True, K.EMERGENCY_FALSE),
        (PostStatus.REMOVED, False, K.POST_REMOVED),
    ],
)
def test_the_author_gets_the_outcome_once(status, emergency, kind):
    first = plan(status, emergency=emergency)
    assert adds(first) == {(AUTHOR, kind)}
    assert first.reverse == ()
    # Applied, the same state asks for nothing more: a re-sent verdict never double-counts.
    assert not plan(status, [row(kind, AUTHOR)], emergency=emergency)


@pytest.mark.parametrize("status", [PostStatus.PENDING, PostStatus.UNDER_REVIEW])
def test_a_review_or_pending_freezes_the_label(status):
    held = [row(K.FACT_FALSE, AUTHOR), row(K.REPOST_FALSE, "r1")]
    assert not plan(status, held, reposts=[("r2", PostStatus.PENDING)])


def test_a_relabel_reverses_the_old_outcome_for_the_author_and_every_reposter():
    held = [row(K.FACT_TRUE, AUTHOR), row(K.REPOST_TRUE, "r1"), row(K.REPOST_TRUE, "r2")]
    reposts = [("r1", PostStatus.PENDING), ("r2", PostStatus.UNDER_REVIEW)]
    changes = plan(PostStatus.VERIFIED_FALSE, held, reposts=reposts)
    assert reversed_ids(changes) == {r.id for r in held}
    assert adds(changes) == {
        (AUTHOR, K.FACT_FALSE),
        ("r1", K.REPOST_FALSE),
        ("r2", K.REPOST_FALSE),
    }


def test_an_overturned_false_also_reverses_the_label_credits():
    """User decision 6: the reporters' credit for a Mark FALSE goes when the label becomes TRUE."""
    held = [
        row(K.FACT_FALSE, AUTHOR),
        row(K.REPORT_UPHELD, "rep", action=ActionKind.MARKED_FALSE),
    ]
    changes = plan(PostStatus.VERIFIED_TRUE, held)
    assert reversed_ids(changes) == {held[0].id, held[1].id}
    assert adds(changes) == {(AUTHOR, K.FACT_TRUE)}


def test_a_removal_adds_to_the_label_and_keeps_it():
    """User decision 1: a removed FALSE post costs N+1 and N+2."""
    held = [row(K.FACT_FALSE, AUTHOR), row(K.REPORT_UPHELD, "rep", action=ActionKind.MARKED_FALSE)]
    changes = plan(PostStatus.REMOVED, held)
    assert changes.reverse == ()
    assert adds(changes) == {(AUTHOR, K.POST_REMOVED)}


@pytest.mark.parametrize(
    "back_to", [PostStatus.VERIFIED_FALSE, PostStatus.PENDING, PostStatus.UNDER_REVIEW]
)
def test_restore_reverses_only_the_removal_and_its_credits(back_to):
    held = [
        row(K.FACT_FALSE, AUTHOR),
        row(K.POST_REMOVED, AUTHOR, action=ActionKind.REMOVED),
        row(K.REPOST_REMOVED, "r1", action=ActionKind.REMOVED),
        row(K.REPORT_UPHELD, "rep", action=ActionKind.REMOVED),
        row(K.REPORT_UPHELD, "old", action=ActionKind.MARKED_FALSE),
    ]
    changes = plan(back_to, held, reposts=[("r1", PostStatus.PENDING)])
    assert reversed_ids(changes) == {held[1].id, held[2].id, held[3].id}
    if back_to == PostStatus.VERIFIED_FALSE:
        # The reposter never had a label row: the post's FALSE reaches them now.
        assert adds(changes) == {("r1", K.REPOST_FALSE)}
    else:
        assert changes.add == ()


@pytest.mark.parametrize("status_at_repost", PostStatus.values)
@pytest.mark.parametrize("has_row", [False, True])
@pytest.mark.parametrize("status", [PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE])
def test_reposter_eligibility(status_at_repost, has_row, status):
    """A repost made while the post was undecided counts; an existing row in the slot keeps the
    person eligible whatever their repost says (or whether it still exists)."""
    held = [row(K.REPOST_TRUE, "r1")] if has_row else []
    changes = plan(status, held, reposts=[("r1", status_at_repost)])
    eligible = status_at_repost in (PostStatus.PENDING, PostStatus.UNDER_REVIEW) or has_row
    wanted = K.REPOST_TRUE if status == PostStatus.VERIFIED_TRUE else K.REPOST_FALSE
    gets = ("r1", wanted) in adds(changes)
    already = has_row and wanted == K.REPOST_TRUE
    assert gets is (eligible and not already)


def test_a_repost_undone_after_the_verdict_keeps_its_row():
    held = [row(K.FACT_TRUE, AUTHOR), row(K.REPOST_TRUE, "gone")]
    assert not plan(PostStatus.VERIFIED_TRUE, held, reposts=[])


def test_a_relabel_after_an_undone_repost_moves_it_to_the_new_kind():
    held = [row(K.FACT_TRUE, AUTHOR), row(K.REPOST_TRUE, "gone")]
    changes = plan(PostStatus.VERIFIED_FALSE, held, reposts=[])
    assert reversed_ids(changes) == {r.id for r in held}
    assert adds(changes) == {(AUTHOR, K.FACT_FALSE), ("gone", K.REPOST_FALSE)}


def test_a_repost_of_a_checked_post_earns_nothing():
    changes = plan(
        PostStatus.VERIFIED_TRUE,
        reposts=[("late", PostStatus.VERIFIED_TRUE), ("early", PostStatus.PENDING)],
    )
    assert adds(changes) == {(AUTHOR, K.FACT_TRUE), ("early", K.REPOST_TRUE)}


@pytest.mark.parametrize(
    ("emergency", "author_kind", "repost_kind"),
    [(False, K.FACT_FALSE, K.REPOST_FALSE), (True, K.EMERGENCY_FALSE, K.REPOST_EMERGENCY_FALSE)],
)
def test_the_emergency_weight_replaces_the_plain_false(emergency, author_kind, repost_kind):
    changes = plan(
        PostStatus.VERIFIED_FALSE, emergency=emergency, reposts=[("r1", PostStatus.PENDING)]
    )
    assert adds(changes) == {(AUTHOR, author_kind), ("r1", repost_kind)}


def test_the_removal_slot_for_reposters():
    changes = plan(
        PostStatus.REMOVED,
        [row(K.FACT_TRUE, AUTHOR), row(K.REPOST_TRUE, "r1")],
        reposts=[("r1", PostStatus.PENDING), ("r2", PostStatus.UNDER_REVIEW)],
    )
    assert adds(changes) == {
        (AUTHOR, K.POST_REMOVED),
        ("r1", K.REPOST_REMOVED),
        ("r2", K.REPOST_REMOVED),
    }
    assert changes.reverse == ()  # the label is kept


@pytest.mark.parametrize(
    ("status", "action", "author_kind"),
    [
        (PostStatus.VERIFIED_FALSE, ActionKind.MARKED_FALSE, K.FACT_FALSE),
        (PostStatus.REMOVED, ActionKind.REMOVED, K.POST_REMOVED),
    ],
)
def test_reporters_are_credited_in_the_slot_of_the_action(status, action, author_kind):
    changes = plan(status, reporters=["b", "a"], action=action)
    assert adds(changes) == {(AUTHOR, author_kind), ("a", K.REPORT_UPHELD), ("b", K.REPORT_UPHELD)}
    reporters = [a.user_id for a in changes.add if a.kind == K.REPORT_UPHELD]
    assert reporters == ["a", "b"]  # sorted
    # Applied (each credit carrying the action that earned it), nothing more is asked for.
    held = [row(K.REPORT_UPHELD, user, action=action) for user in ("a", "b")]
    held.append(row(author_kind, AUTHOR))
    assert not plan(status, held, reporters=["a", "b"], action=action)


@pytest.mark.parametrize(
    ("status", "action"),
    [
        (PostStatus.VERIFIED_TRUE, ActionKind.VERIFIED),
        (PostStatus.VERIFIED_TRUE, ActionKind.MARKED_FALSE),
        (PostStatus.UNDER_REVIEW, ActionKind.DISMISSED_REPORT),
        (PostStatus.PENDING, ActionKind.REMOVED),
        (PostStatus.VERIFIED_FALSE, ActionKind.REMOVED),
        (PostStatus.VERIFIED_FALSE, None),
    ],
)
def test_reporters_with_an_action_that_cannot_credit_them_are_a_bug(status, action):
    with pytest.raises(ValueError, match="can't be credited"):
        plan(status, reporters=["a"], action=action)


def test_a_reporter_who_holds_the_credit_gets_no_second_one():
    held = [
        row(K.FACT_FALSE, AUTHOR),
        row(K.REPORT_UPHELD, "a", action=ActionKind.MARKED_FALSE),
    ]
    changes = plan(PostStatus.VERIFIED_FALSE, held, reporters=["a"], action=ActionKind.MARKED_FALSE)
    assert not changes


def test_a_report_credit_with_an_unknown_action_is_left_alone():
    held = [row(K.FACT_TRUE, AUTHOR), row(K.REPORT_UPHELD, "a", action=None)]
    assert not plan(PostStatus.VERIFIED_TRUE, held)


def test_user_ids_are_everyone_touched_sorted():
    held = [row(K.FACT_TRUE, AUTHOR), row(K.REPOST_TRUE, "zed")]
    changes = plan(
        PostStatus.VERIFIED_FALSE,
        held,
        reposts=[("bob", PostStatus.PENDING)],
        reporters=["amy"],
        action=ActionKind.MARKED_FALSE,
    )
    assert changes.user_ids == sorted({AUTHOR, "zed", "bob", "amy"})


# ---------- the whole matrix: every slot × value × row kind ----------

LABEL_ROWS = [
    K.FACT_TRUE,
    K.FACT_FALSE,
    K.EMERGENCY_FALSE,
    K.REPOST_TRUE,
    K.REPOST_FALSE,
    K.REPOST_EMERGENCY_FALSE,
]
REMOVAL_ROWS = [K.POST_REMOVED, K.REPOST_REMOVED]


def matching_kind(kind, want):
    """Written out again: the kind a holder of `kind` should have for `want`, or None."""
    author = kind in (K.FACT_TRUE, K.FACT_FALSE, K.EMERGENCY_FALSE, K.POST_REMOVED)
    reporter = kind == K.REPORT_UPHELD
    table = {
        Want.TRUE: (K.FACT_TRUE, K.REPOST_TRUE, None),
        Want.FALSE: (K.FACT_FALSE, K.REPOST_FALSE, K.REPORT_UPHELD),
        Want.EMERGENCY_FALSE: (K.EMERGENCY_FALSE, K.REPOST_EMERGENCY_FALSE, K.REPORT_UPHELD),
        Want.REMOVED: (K.POST_REMOVED, K.REPOST_REMOVED, K.REPORT_UPHELD),
        Want.NONE: (None, None, None),
    }[want]
    return table[2] if reporter else table[0] if author else table[1]


@pytest.mark.parametrize(
    ("status", "emergency"),
    [
        (PostStatus.VERIFIED_TRUE, False),
        (PostStatus.VERIFIED_FALSE, False),
        (PostStatus.VERIFIED_FALSE, True),
        (PostStatus.REMOVED, False),
        (PostStatus.REMOVED, True),
        (PostStatus.UNDER_REVIEW, False),
        (PostStatus.PENDING, False),
        (PostStatus.PUBLISHED, False),
    ],
)
@pytest.mark.parametrize(
    ("kind", "action"),
    [(kind, None) for kind in LABEL_ROWS + REMOVAL_ROWS]
    + [(K.REPORT_UPHELD, ActionKind.MARKED_FALSE), (K.REPORT_UPHELD, ActionKind.REMOVED)],
)
def test_one_held_row_against_every_target(status, emergency, kind, action):
    holder = AUTHOR if kind in scoring.AUTHOR_KINDS else "someone"
    held = row(kind, holder, action=action)
    target = scoring.desired(status, emergency)
    slot = scoring.slot_of(held)
    want = target[slot]
    changes = plan(status, [held], emergency=emergency)
    if want == Want.KEEP:
        assert held not in changes.reverse
        return
    should_hold = matching_kind(kind, want)
    assert (held in changes.reverse) is (should_hold != kind)
    if should_hold is not None and should_hold != kind and kind != K.REPORT_UPHELD:
        # An author or reposter moves to the matching kind; a reporter is never re-credited.
        assert Addition(holder, should_hold) in changes.add
    if kind == K.REPORT_UPHELD:
        assert all(a.kind != K.REPORT_UPHELD for a in changes.add)
