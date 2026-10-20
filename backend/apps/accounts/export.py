"""Everything stored about one account, as the JSON of `GET /api/v1/me/export/` (Part 14).

**One query per section, so the count is fixed whatever the volume** (`test_export.py` pins it).
Every section names its columns (`.values()` or `.only()`), so a column added to a model later is
left out until someone adds it here on purpose: `search_vector` and `pipeline_result` can never
appear, and nor can anything about another person beyond the public username.

Never included: another person's email, role or credibility; a moderator's identity (`resolved_by`,
`moderated_by`, `original_moderator`); the moderators' `notes`; `flagged_reason`; `report_count`;
`counts_toward_threshold`; the pipeline's internals; avatar fields (Part 14B owns the photo).
"""

from allauth.socialaccount.models import SocialAccount

from apps.moderation.models import Appeal
from apps.moderation.queries import with_appeal_fields
from apps.notifications.models import Notification
from apps.posts.models import Post
from apps.posts.serializers import iso, shown_confidence, shown_verdict_source
from apps.reports.models import Report
from apps.reputation import scoring
from apps.reputation.models import ReputationEvent
from apps.reputation.serializers import event_data, is_reversed
from apps.social.models import Bookmark, Comment, Follow, Like, Repost

FORMAT = "rumor-zero-export"
VERSION = 1

# The columns of a post that the export reads (everything else, `search_vector` included, stays in
# the database). `removal_reason` is an annotation from `with_appeal_fields`.
POST_COLUMNS = (
    "id",
    "post_type",
    "content",
    "sources",
    "is_emergency",
    "emergency_expires_at",
    "emergency_demoted_at",
    "status",
    "verdict_source",
    "confidence_score",
    "verdict_note",
    "created_at",
    "deleted_at",
)


def filename(user, now):
    """`rumor-zero-<username>-<YYYY-MM-DD>.json`: a username is `[a-z0-9_]`, safe in a header."""
    return f"rumor-zero-{user.username}-{now:%Y-%m-%d}.json"


def _post_row(post):
    return {
        "id": str(post.pk),
        "post_type": post.post_type,
        "content": post.content,
        "sources": list(post.sources),
        "is_emergency": post.is_emergency,
        "emergency_expires_at": iso(post.emergency_expires_at),
        "emergency_demoted_at": iso(post.emergency_demoted_at),
        "status": post.status,
        "confidence_score": shown_confidence(post),
        "verdict_source": shown_verdict_source(post),
        "verdict_note": post.verdict_note,
        # What the moderator told you; only a removed post has one.
        "removal_reason": post.removal_reason,
        "created_at": iso(post.created_at),
        "deleted_at": iso(post.deleted_at),
    }


def _posts(user):
    rows = with_appeal_fields(Post.objects.filter(author=user), user).only(*POST_COLUMNS)
    return [_post_row(post) for post in rows.order_by("created_at", "id")]


def _comments(user):
    rows = Comment.objects.filter(author=user).order_by("created_at", "id")
    return [
        {
            "id": str(row["id"]),
            "post_id": str(row["post_id"]),
            "content": row["content"],
            "hidden": row["is_hidden"],
            "created_at": iso(row["created_at"]),
            "deleted_at": iso(row["deleted_at"]),
        }
        for row in rows.values("id", "post_id", "content", "is_hidden", "created_at", "deleted_at")
    ]


def _dated_posts(model, user):
    """`likes` and `bookmarks`: the post and when."""
    rows = model.objects.filter(user=user).order_by("created_at", "id")
    return [
        {"post_id": str(post_id), "created_at": iso(created_at)}
        for post_id, created_at in rows.values_list("post_id", "created_at")
    ]


def _reposts(user):
    rows = Repost.objects.filter(user=user).order_by("created_at", "id")
    return [
        {"post_id": str(post_id), "status_at_repost": status, "created_at": iso(created_at)}
        for post_id, status, created_at in rows.values_list(
            "post_id", "status_at_repost", "created_at"
        )
    ]


def _people(rows):
    """Follow rows as `(user id, username, created_at)`: the public bits of the other person."""
    return [
        {"user_id": str(user_id), "username": username, "created_at": iso(created_at)}
        for user_id, username, created_at in rows
    ]


def _following(user):
    rows = Follow.objects.filter(follower=user).order_by("created_at", "id")
    return _people(rows.values_list("following_id", "following__username", "created_at"))


def _followers(user):
    rows = Follow.objects.filter(following=user).order_by("created_at", "id")
    return _people(rows.values_list("follower_id", "follower__username", "created_at"))


def _reports(user):
    rows = Report.objects.filter(reporter=user).order_by("created_at", "id")
    return [
        {
            "id": str(row["id"]),
            "post_id": str(row["post_id"]),
            "reason": row["reason"],
            "details": row["details"],
            "status": row["status"],
            "created_at": iso(row["created_at"]),
            "resolved_at": iso(row["resolved_at"]),
        }
        for row in rows.values(
            "id", "post_id", "reason", "details", "status", "created_at", "resolved_at"
        )
    ]


def _appeals(user):
    rows = Appeal.objects.filter(author=user).order_by("created_at", "id")
    return [
        {
            "id": str(row["id"]),
            "post_id": str(row["post_id"]),
            "kind": row["kind"],
            "reason": row["reason"],
            "status": row["status"],
            "created_at": iso(row["created_at"]),
            "resolved_at": iso(row["resolved_at"]),
        }
        for row in rows.values(
            "id", "post_id", "kind", "reason", "status", "created_at", "resolved_at"
        )
    ]


def _credibility_history(user):
    """Every ledger row, reversals included: the keys of `GET /me/reputation/events/` without the
    `appeal` state (that is a live view of the post, not part of the record). The real post id is
    kept even when the post is deleted: it is your own record."""
    rows = (
        ReputationEvent.objects.filter(user=user)
        .select_related("post", "post__appeal", "reverses")
        .defer("post__pipeline_result", "post__search_vector", "post__content", "post__sources")
        .annotate(is_reversed=is_reversed())
        .order_by("created_at", "id")
    )
    history = []
    for row in rows:
        data = event_data(row)
        del data["appeal"]
        data["post_id"] = str(row.post_id) if row.post_id is not None else None
        history.append(data)
    return history


def _notifications(user):
    rows = Notification.objects.filter(recipient=user).order_by("created_at", "id")
    return [
        {
            "id": str(row["id"]),
            "type": row["type"],
            "outcome": row["outcome"],
            "post_id": str(row["post_id"]) if row["post_id"] is not None else None,
            "comment_id": str(row["comment_id"]) if row["comment_id"] is not None else None,
            "actor": row["actor__username"],
            "is_read": row["is_read"],
            "created_at": iso(row["created_at"]),
        }
        for row in rows.values(
            "id",
            "type",
            "outcome",
            "post_id",
            "comment_id",
            "actor__username",
            "is_read",
            "created_at",
        )
    ]


def _account(user):
    return {
        "id": str(user.pk),
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "email": user.email,
        "is_email_verified": user.is_email_verified,
        "role": user.role,
        "created_at": iso(user.created_at),
        "has_usable_password": user.has_usable_password(),
        "google_connected": SocialAccount.objects.filter(user=user, provider="google").exists(),
        "credibility": {
            "score": user.reputation_score,
            "sample": user.reputation_sample,
            "public_score": scoring.public_score(user.reputation_score, user.reputation_sample),
        },
    }


def build_export(user, now):
    """The whole export as a JSON-ready dict: 12 queries (the Google check, then one for each of the
    11 lists), whatever the volume."""
    return {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": iso(now),
        "account": _account(user),
        "posts": _posts(user),
        "comments": _comments(user),
        "likes": _dated_posts(Like, user),
        "following": _following(user),
        "followers": _followers(user),
        "bookmarks": _dated_posts(Bookmark, user),
        "reposts": _reposts(user),
        "reports": _reports(user),
        "appeals": _appeals(user),
        "credibility_history": _credibility_history(user),
        "notifications": _notifications(user),
    }
