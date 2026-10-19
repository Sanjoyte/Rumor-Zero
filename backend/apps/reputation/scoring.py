"""The credibility score's rules (ARCHITECTURE §4a; D5, ANALYSIS f-5).

Pure: no database, no clock. `apps/reputation/services.py` reads the rows, calls these functions
and does every write.

**The score.** `score(p, n)` is `100 · (5 + p) / (10 + p + n)` rounded **half up**, where `p` and
`n` are the sums of every ledger row's weights (reversals included). It starts at 50, and the ten
imaginary events damp single-post swings. It is public once a person has `PUBLIC_AFTER` counted
events (un-reversed own-post rows).

**Reconciliation.** A post's events are kept in step with its state rather than written event by
event. Each row belongs to one of two slots:

- **LABEL**: the author's `fact_*` / `emergency_false`, the reposters' `repost_true` /
  `repost_false` / `repost_emergency_false`, and the `report_upheld` rows a Mark FALSE earned;
- **REMOVAL**: the author's `post_removed`, the reposters' `repost_removed`, and the
  `report_upheld` rows a Remove earned.

`desired()` says what each slot should hold for the post's status: a verified status sets LABEL, any
other status leaves it as it is (a review freezes the score, a late TRUE stays private, a removed
post keeps its label); `removed` sets REMOVAL, any other status empties it. `changes()` then lists
the rows to reverse and the rows to add. Running it twice on the same state finds nothing to do,
which is what makes a re-sent verdict harmless.
"""

import enum
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from apps.moderation.models import ActionKind
from apps.posts.models import PostStatus
from apps.reputation.models import EventKind

K = EventKind

# (P, N) per kind (ARCHITECTURE §4a). A reversal carries the negated weights of its row instead.
WEIGHTS = {
    K.FACT_TRUE: (Decimal("1"), Decimal("0")),
    K.FACT_FALSE: (Decimal("0"), Decimal("1")),
    K.EMERGENCY_FALSE: (Decimal("0"), Decimal("3")),
    K.POST_REMOVED: (Decimal("0"), Decimal("2")),
    K.REPOST_TRUE: (Decimal("0.25"), Decimal("0")),
    K.REPOST_FALSE: (Decimal("0"), Decimal("0.5")),
    K.REPOST_EMERGENCY_FALSE: (Decimal("0"), Decimal("1")),
    K.REPOST_REMOVED: (Decimal("0"), Decimal("0.5")),
    K.REPORT_UPHELD: (Decimal("0.25"), Decimal("0")),
}

# Own-post kinds: an un-reversed one counts toward `reputation_sample`.
AUTHOR_KINDS = frozenset({K.FACT_TRUE, K.FACT_FALSE, K.EMERGENCY_FALSE, K.POST_REMOVED})
REPOSTER_KINDS = frozenset(
    {K.REPOST_TRUE, K.REPOST_FALSE, K.REPOST_EMERGENCY_FALSE, K.REPOST_REMOVED}
)
REPORT_UPHELD = K.REPORT_UPHELD

# A repost counts only if it was made while the original was still undecided (`status_at_repost`).
REPOST_COUNTED = frozenset({PostStatus.PENDING, PostStatus.UNDER_REVIEW})

PUBLIC_AFTER = 3  # counted events before the score is shown
START_SCORE = 50

# At most this many un-reversed `report_upheld` rows per reporter in the rolling window.
REPORT_CREDIT_CAP = 4
REPORT_CREDIT_WINDOW = timedelta(days=30)


# ---------- the score ----------


def _quarters(value):
    """`value` in quarter units, as an int. Every weight is a multiple of 0.25, so the sums are
    too; anything else (or a negative sum) means the ledger is broken."""
    quarters = Decimal(value) * 4
    if quarters < 0 or quarters != quarters.to_integral_value():
        raise ValueError(f"a credibility sum must be a non-negative multiple of 0.25: {value!r}")
    return int(quarters)


def score(p, n):
    """`round(100 · (5 + p) / (10 + p + n))`, rounding a half **up**, computed exactly.

    With `P = 4p`, `N = 4n` and `D = 40 + P + N` the value is `100 · (20 + P) / D`, and
    `floor(x + ½)` of it is `(200 · (20 + P) + D) // (2D)` in integers. Python's `round` would
    round a half to even: (0, 30) is 12.5, which must give 13, not 12.
    """
    p4, n4 = _quarters(p), _quarters(n)
    denominator = 40 + p4 + n4
    return (200 * (20 + p4) + denominator) // (2 * denominator)


def public_score(stored_score, sample):
    """What the public sees: the score once `sample` reaches `PUBLIC_AFTER`, otherwise None."""
    return stored_score if sample >= PUBLIC_AFTER else None


def within_cap(credits_in_window):
    """Whether a reporter holding `credits_in_window` recent, un-reversed credits gets another."""
    return credits_in_window < REPORT_CREDIT_CAP


# ---------- slots ----------


class Slot(enum.StrEnum):
    LABEL = "label"
    REMOVAL = "removal"


class Want(enum.StrEnum):
    """What a slot should hold. KEEP (LABEL only) leaves it as it is; NONE (REMOVAL only) empties
    it."""

    TRUE = "true"
    FALSE = "false"
    EMERGENCY_FALSE = "emergency_false"
    REMOVED = "removed"
    NONE = "none"
    KEEP = "keep"


class Role(enum.StrEnum):
    AUTHOR = "author"
    REPOSTER = "reposter"
    REPORTER = "reporter"


# The kind a person in a role should hold for a slot's value. A reporter is credited only for a
# negative outcome, so there is no reporter kind for TRUE.
_KIND = {
    (Role.AUTHOR, Want.TRUE): K.FACT_TRUE,
    (Role.AUTHOR, Want.FALSE): K.FACT_FALSE,
    (Role.AUTHOR, Want.EMERGENCY_FALSE): K.EMERGENCY_FALSE,
    (Role.AUTHOR, Want.REMOVED): K.POST_REMOVED,
    (Role.REPOSTER, Want.TRUE): K.REPOST_TRUE,
    (Role.REPOSTER, Want.FALSE): K.REPOST_FALSE,
    (Role.REPOSTER, Want.EMERGENCY_FALSE): K.REPOST_EMERGENCY_FALSE,
    (Role.REPOSTER, Want.REMOVED): K.REPOST_REMOVED,
    (Role.REPORTER, Want.FALSE): K.REPORT_UPHELD,
    (Role.REPORTER, Want.EMERGENCY_FALSE): K.REPORT_UPHELD,
    (Role.REPORTER, Want.REMOVED): K.REPORT_UPHELD,
}

_LABEL_KINDS = frozenset(
    {
        K.FACT_TRUE,
        K.FACT_FALSE,
        K.EMERGENCY_FALSE,
        K.REPOST_TRUE,
        K.REPOST_FALSE,
        K.REPOST_EMERGENCY_FALSE,
    }
)
_REMOVAL_KINDS = frozenset({K.POST_REMOVED, K.REPOST_REMOVED})

# Which moderator action credits reporters, and in which slot.
REPORT_SLOT = {ActionKind.MARKED_FALSE: Slot.LABEL, ActionKind.REMOVED: Slot.REMOVAL}


@dataclass(frozen=True)
class Row:
    """An un-reversed, non-reversal ledger row about the post. `action` is the kind of the
    moderator action that wrote it (it tells a `report_upheld` row's slot), or None."""

    id: object
    user_id: object
    kind: str
    positive: Decimal
    negative: Decimal
    action: str | None = None


@dataclass(frozen=True)
class Addition:
    user_id: object
    kind: str


@dataclass(frozen=True)
class Changes:
    reverse: tuple = ()
    add: tuple = ()

    def __bool__(self):
        return bool(self.reverse or self.add)

    @property
    def user_ids(self):
        """Everyone whose ledger changes, sorted (the lock order)."""
        return sorted({row.user_id for row in self.reverse} | {a.user_id for a in self.add})


def role_of(kind):
    if kind in AUTHOR_KINDS:
        return Role.AUTHOR
    if kind in REPOSTER_KINDS:
        return Role.REPOSTER
    if kind == REPORT_UPHELD:
        return Role.REPORTER
    raise ValueError(f"no role for {kind!r}")


def slot_of(row):
    """The slot a row belongs to, or None for a `report_upheld` row whose action is unknown (it is
    then never touched)."""
    if row.kind in _LABEL_KINDS:
        return Slot.LABEL
    if row.kind in _REMOVAL_KINDS:
        return Slot.REMOVAL
    if row.kind == REPORT_UPHELD:
        return REPORT_SLOT.get(row.action)
    raise ValueError(f"not a reconcilable row: {row.kind!r}")


def desired(status, is_emergency):
    """What each slot should hold for a post in `status`."""
    if status == PostStatus.VERIFIED_TRUE:
        label = Want.TRUE
    elif status == PostStatus.VERIFIED_FALSE:
        label = Want.EMERGENCY_FALSE if is_emergency else Want.FALSE
    else:
        label = Want.KEEP
    removal = Want.REMOVED if status == PostStatus.REMOVED else Want.NONE
    return {Slot.LABEL: label, Slot.REMOVAL: removal}


def may_add(target):
    """Whether any slot can gain rows (so the reposts are worth reading)."""
    return any(want not in (Want.KEEP, Want.NONE) for want in target.values())


def _matches(row, want):
    return _KIND.get((role_of(row.kind), want)) == row.kind


def changes(target, rows, *, author_id, reposts=(), reporters=(), action=None):
    """The rows to reverse and to add so the post's ledger matches `target` (from `desired`).

    - `rows`: the post's un-reversed, non-reversal rows (`Row`).
    - `reposts`: `(user_id, status_at_repost)` of every current repost of the post. Only those
      made while the post was undecided (`REPOST_COUNTED`) make someone eligible; so does an
      un-reversed reposter row they already hold in the slot (a repost undone after the verdict
      keeps its row, and moves to the new kind on a re-label).
    - `reporters`: the ids to credit, in the slot of `action` (Mark FALSE: LABEL; Remove:
      REMOVAL). The caller has already left out the deciding moderator; the cap is applied later,
      under the users' locks.

    For each slot that isn't KEEP, every row whose kind no longer matches is reversed, and each
    eligible person who lacks the matching row gets one.
    """
    credit_slot = None
    if reporters:
        credit_slot = REPORT_SLOT.get(action)
        if credit_slot is None or (Role.REPORTER, target[credit_slot]) not in _KIND:
            raise ValueError(f"reporters can't be credited by {action!r} on {target!r}")
    counted = {user_id for user_id, status in reposts if status in REPOST_COUNTED}
    reverse, add = [], []
    for slot in (Slot.LABEL, Slot.REMOVAL):
        want = target[slot]
        if want == Want.KEEP:
            continue
        in_slot = [row for row in rows if slot_of(row) == slot]
        reverse.extend(row for row in in_slot if not _matches(row, want))
        if want == Want.NONE:
            continue
        held = {(row.user_id, row.kind) for row in in_slot if _matches(row, want)}

        def needs(user_id, role, want=want, held=held):
            kind = _KIND[(role, want)]
            if (user_id, kind) not in held:
                held.add((user_id, kind))
                add.append(Addition(user_id, kind))

        needs(author_id, Role.AUTHOR)
        sticky = {row.user_id for row in in_slot if role_of(row.kind) == Role.REPOSTER}
        for user_id in sorted(counted | sticky):
            needs(user_id, Role.REPOSTER)
        if slot == credit_slot:
            for user_id in sorted(set(reporters)):
                needs(user_id, Role.REPORTER)
    return Changes(tuple(reverse), tuple(add))
