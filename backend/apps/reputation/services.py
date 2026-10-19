"""The credibility ledger's only writer (ARCHITECTURE §4a).

Only this module writes `ReputationEvent` rows and `users.reputation_score` /
`reputation_sample` (`recompute_reputation` repairs the two fields from the ledger). It is called
explicitly, never through signals: by `posts.services.record_pipeline_result` when the pipeline
labels a post, and by `moderation.services` after every action but Escalate, in the caller's
transaction and **after the caller has locked the post** (`FOR NO KEY UPDATE`).

**Locks.** The post first (the caller), then every affected user, sorted, with
`FOR NO KEY UPDATE`: the moderator's own inserts take `KEY SHARE` on users' rows at commit (the
foreign keys are deferred), and a plain `FOR UPDATE` on someone who is also deciding another post
could deadlock with them. Never a user and then a post. One `settle_post` per transaction.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, F, Max, Q, Sum

from apps.accounts.models import User
from apps.reputation import scoring
from apps.reputation.models import EventKind, ReputationEvent
from apps.social.models import Repost

_TICK = timedelta(microseconds=1)


@dataclass(frozen=True)
class Totals:
    """A person's whole ledger in sums: the weights (reversals included), the counted events and
    the time of the last row."""

    positive: Decimal = Decimal("0")
    negative: Decimal = Decimal("0")
    sample: int = 0
    last: object = None

    @property
    def score(self):
        return scoring.score(self.positive, self.negative)


def totals_for(user_ids):
    """`Totals` per user id, from one grouped query (a user with no rows is absent: use
    `Totals()`). Postgres refuses an aggregate with `FOR UPDATE`, so the lock is its own query."""
    rows = (
        ReputationEvent.objects.filter(user_id__in=list(user_ids))
        .order_by()
        .values("user_id")
        .annotate(
            p=Sum("positive"),
            n=Sum("negative"),
            sample=Count(
                "pk",
                filter=Q(kind__in=list(scoring.AUTHOR_KINDS), reversed_by__isnull=True),
            ),
            last=Max("created_at"),
        )
    )
    return {row["user_id"]: Totals(row["p"], row["n"], row["sample"], row["last"]) for row in rows}


def _post_rows(post):
    """The post's un-reversed, non-reversal rows, oldest first (one query)."""
    rows = (
        ReputationEvent.objects.filter(post=post, reversed_by__isnull=True)
        .exclude(kind=EventKind.REVERSAL)
        .order_by("created_at", "id")
        .values(
            "id", "user_id", "kind", "positive", "negative", action=F("moderation_action__action")
        )
    )
    return [scoring.Row(**row) for row in rows]


def _plan(post, *, reporters=(), action=None):
    rows = _post_rows(post)
    target = scoring.desired(post.status, post.is_emergency)
    reposts = ()
    if scoring.may_add(target):
        reposts = list(Repost.objects.filter(post=post).values_list("user_id", "status_at_repost"))
    return scoring.changes(
        target, rows, author_id=post.author_id, reposts=reposts, reporters=reporters, action=action
    )


def pending_changes(post):
    """What `settle_post` would do to `post` now with no reporters to credit (no lock, no write).
    Empty after every settle: the sequence tests check the ledger matches each post's state."""
    return _plan(post)


def _lock_users(user_ids):
    """Lock the users whose ledger changes, in id order, with `FOR NO KEY UPDATE` (see the module
    text). A separate function so the race tests can switch it off."""
    return list(
        User.objects.select_for_update(no_key=True)
        .filter(pk__in=list(user_ids))
        .order_by("pk")
        .only("pk", "reputation_score", "reputation_sample")
    )


def _read_totals(user_ids):
    """`totals_for`, under the users' locks. Separate so the race tests can pause after it."""
    return totals_for(user_ids)


def _within_cap(additions, now):
    """Drop the credits of reporters who already hold `REPORT_CREDIT_CAP` un-reversed credits from
    the last 30 days. Read **after** the users' locks: two decisions at once would otherwise both
    see room for one more."""
    reporters = [a.user_id for a in additions if a.kind == scoring.REPORT_UPHELD]
    if not reporters:
        return list(additions)
    held = dict(
        ReputationEvent.objects.filter(
            user_id__in=reporters,
            kind=scoring.REPORT_UPHELD,
            created_at__gt=now - scoring.REPORT_CREDIT_WINDOW,
            reversed_by__isnull=True,
        )
        .order_by()
        .values("user_id")
        .annotate(n=Count("pk"))
        .values_list("user_id", "n")
    )
    return [
        a
        for a in additions
        if a.kind != scoring.REPORT_UPHELD or scoring.within_cap(held.get(a.user_id, 0))
    ]


def settle_post(post, *, now, action=None, credited_reporters=()):
    """Bring `post`'s ledger rows in line with its current state, and return the new rows.

    `action` is the `ModerationAction` that caused it (None for the pipeline); it is linked on
    every new row. `credited_reporters` are the reporters whose open reports `action` upheld (Mark
    FALSE when it changed the label, or Remove), without the deciding moderator. Each one gets a
    `report_upheld` row unless they already hold `REPORT_CREDIT_CAP` recent credits.

    Must run inside the caller's `transaction.atomic()` with the post locked. Nothing to do means
    nothing is locked or written, so a re-sent verdict, a Keep removed or a Dismiss that changes no
    label costs two reads.
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("settle_post runs inside the caller's transaction, with the post locked")
    plan = _plan(
        post,
        reporters=credited_reporters,
        action=action.action if action is not None else None,
    )
    if not plan:
        return []
    users = _lock_users(plan.user_ids)
    additions = _within_cap(plan.add, now)
    if not plan.reverse and not additions:
        return []
    entries = defaultdict(list)
    for row in plan.reverse:
        entries[row.user_id].append(row)
    for addition in additions:
        entries[addition.user_id].append(addition)
    totals = _read_totals(list(entries))

    new_rows, changed = [], []
    for user in users:
        if user.pk not in entries:
            continue
        mine = totals.get(user.pk, Totals())
        positive, negative, sample, last = mine.positive, mine.negative, mine.sample, mine.last
        for entry in entries[user.pk]:
            if isinstance(entry, scoring.Row):
                kind, reverses_id = EventKind.REVERSAL, entry.id
                p, n = -entry.positive, -entry.negative
                sample -= entry.kind in scoring.AUTHOR_KINDS
            else:
                kind, reverses_id = entry.kind, None
                p, n = scoring.WEIGHTS[entry.kind]
                sample += entry.kind in scoring.AUTHOR_KINDS
            positive, negative = positive + p, negative + n
            # Strictly increasing per person, in the order rows were written: a writer whose `now`
            # is older than this person's last row (it waited for a lock) still comes after it.
            created_at = now if last is None else max(now, last + _TICK)
            last = created_at
            new_rows.append(
                ReputationEvent(
                    user_id=user.pk,
                    kind=kind,
                    positive=p,
                    negative=n,
                    post=post,
                    moderation_action=action,
                    reverses_id=reverses_id,
                    score_after=scoring.score(positive, negative),
                    created_at=created_at,
                )
            )
        user.reputation_score = scoring.score(positive, negative)
        user.reputation_sample = sample
        changed.append(user)
    ReputationEvent.objects.bulk_create(new_rows)
    # Not `save()`: no group sync, and only these two columns.
    User.objects.bulk_update(changed, ["reputation_score", "reputation_sample"], batch_size=500)
    return new_rows
