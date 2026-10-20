"""The two credibility payloads (ARCHITECTURE §9): the public summary of an account, and your own
ledger. Nothing private reaches the public one: no weights, no `score_after`, no reports, no
reposts, no moderator and no reversal rows."""

from django.db.models import Exists, OuterRef

from apps.posts.models import PostStatus
from apps.posts.serializers import iso
from apps.reputation import scoring
from apps.reputation.models import EventKind, ReputationEvent

# Own-post rows that cost something: the ones an author can ask another look at.
NEGATIVE_OWN_KINDS = frozenset(
    {EventKind.FACT_FALSE, EventKind.EMERGENCY_FALSE, EventKind.POST_REMOVED}
)
APPEALABLE = (PostStatus.VERIFIED_FALSE, PostStatus.REMOVED)
RECENT_SIZE = 10


def is_reversed():
    """Whether a row has been reversed: an `Exists`, because reading the reverse one-to-one
    `reversed_by` of a row that has none raises, even under `select_related`."""
    return Exists(ReputationEvent.objects.filter(reverses=OuterRef("pk")))


def _linkable(post_id, deleted_at):
    """A link to the post, or None when it is gone or its author deleted it (its page is a 404)."""
    return str(post_id) if post_id is not None and deleted_at is None else None


def recent_events(user):
    """The last `RECENT_SIZE` own-post events of `user`, newest first (one query)."""
    rows = (
        ReputationEvent.objects.filter(user=user, kind__in=list(scoring.AUTHOR_KINDS))
        .annotate(is_reversed=is_reversed())
        .order_by("-created_at", "-id")
        .values("kind", "post_id", "created_at", "is_reversed", "post__deleted_at")
    )
    return [
        {
            "kind": row["kind"],
            "label": EventKind(row["kind"]).label,
            "post_id": _linkable(row["post_id"], row["post__deleted_at"]),
            "created_at": iso(row["created_at"]),
            "reversed": row["is_reversed"],
        }
        for row in rows[:RECENT_SIZE]
    ]


def reputation_data(user, recent, trend=None):
    """`GET /api/v1/users/{username}/reputation/`; `user` carries the three status counts.
    `trend` (Part 11D) is the 30 daily points, or None while the score is hidden."""
    return {
        "score": scoring.public_score(user.reputation_score, user.reputation_sample),
        "sample": user.reputation_sample,
        "verified": user.verified_n,
        "false": user.false_n,
        "removed": user.removed_n,
        "recent": recent,
        "trend": trend,
    }


def _decimal(value):
    return format(value, "f")


def _label(row):
    if row.kind == EventKind.REVERSAL:
        # A reversal always points at its row (a database check), loaded with the page.
        return f"Reversed: {row.reverses.get_kind_display()}"
    return row.get_kind_display()


def _appeal(row):
    """For your own negative rows that still stand: where the appeal is, and whether you can still
    file one (the post object's `can_appeal` rule). None for every other row: a repost or a report
    has no appeal of its own."""
    if row.kind not in NEGATIVE_OWN_KINDS or row.is_reversed:
        return None
    post = row.post
    if post is None:
        return {"status": None, "can_appeal": False}
    appeal = getattr(post, "appeal", None)  # RelatedObjectDoesNotExist is an AttributeError
    return {
        "status": appeal.status if appeal is not None else None,
        "can_appeal": (appeal is None and post.deleted_at is None and post.status in APPEALABLE),
    }


def event_data(row):
    """One row of `GET /api/v1/me/reputation/events/` (11 keys)."""
    post = row.post
    return {
        "id": str(row.pk),
        "kind": row.kind,
        "label": _label(row),
        "positive": _decimal(row.positive),
        "negative": _decimal(row.negative),
        "score_after": row.score_after,
        "created_at": iso(row.created_at),
        "post_id": _linkable(row.post_id, post.deleted_at if post is not None else None),
        "reverses": str(row.reverses_id) if row.reverses_id is not None else None,
        "reversed": row.is_reversed,
        "appeal": _appeal(row),
    }
