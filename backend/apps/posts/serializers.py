from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.fields import get_error_detail

from apps.accounts.serializers import user_summary
from apps.posts.emergency import is_active_emergency
from apps.posts.models import MAX_CONTENT_LENGTH, PostStatus, PostType, VerdictSource
from apps.posts.services import FACT_QUOTA_WINDOW
from apps.posts.validators import source_kind, validate_sources

_DATETIME = serializers.DateTimeField()


def iso(value):
    """ISO-8601 UTC, e.g. `2026-09-29T12:00:00Z`, or None."""
    return None if value is None else _DATETIME.to_representation(value)


class SourcesField(serializers.Field):
    """A list of at most 5 URLs or DOIs, normalised (ARCHITECTURE §4c).

    Not `ListField`: that checks every element before its length, so six sources with one bad one
    would give a per-index error instead of "too many". The Django `ValidationError` from
    `validate_sources` keeps its dict, so errors reach the client per index:
    `{"sources": {"1": ["…"]}}`, or `{"sources": ["…"]}` for the list rule.
    """

    def to_internal_value(self, data):
        try:
            return validate_sources(data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(get_error_detail(exc)) from None

    def to_representation(self, value):
        return [{"value": item, "kind": source_kind(item)} for item in value]


class PostCreateSerializer(serializers.Serializer):
    """`POST /api/v1/posts/`. Undeclared fields (`status`, `author`, …) are ignored."""

    content = serializers.CharField(
        max_length=MAX_CONTENT_LENGTH,
        error_messages={
            "required": "Write something first.",
            "blank": "Write something first.",
            "null": "Write something first.",
            "max_length": f"Keep it to {MAX_CONTENT_LENGTH} characters.",
        },
    )
    post_type = serializers.ChoiceField(
        choices=PostType.choices,
        error_messages={
            "required": "Choose Opinion or Fact.",
            "invalid_choice": "Choose Opinion or Fact.",
            "null": "Choose Opinion or Fact.",
        },
    )
    sources = SourcesField(required=False)
    is_emergency = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs["post_type"] != PostType.FACT and attrs.get("sources"):
            raise serializers.ValidationError({"sources": ["Only fact posts can have sources."]})
        return attrs


def shown_confidence(post):
    """The public confidence, e.g. `"94.00"`: only a pipeline verdict (`verified_*`) has one."""
    if (
        post.status in (PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE)
        and post.verdict_source == VerdictSource.PIPELINE
        and post.confidence_score is not None
    ):
        return f"{post.confidence_score:.2f}"
    return None


def status_item(post):
    """One entry of `GET /api/v1/posts/status/`: just what a badge needs. A removed post says only
    that it is removed."""
    removed = post.status == PostStatus.REMOVED
    return {
        "id": str(post.pk),
        "status": post.status,
        "confidence_score": shown_confidence(post),  # None unless a pipeline verdict
        "verdict_source": None if removed else post.verdict_source,
    }


class PostSerializer(serializers.BaseSerializer):
    """The post object of ARCHITECTURE §9, for lists, the detail page and the 201 answer.

    Fields later parts fill (counts, `*_by_me`, appeals) are `0`, `false` or `null` for now. Nothing
    internal leaks: no `flagged_reason`, pipeline fields, `report_count` or moderation fields.
    **A removed post is a tombstone for everyone but its author** (user decision 2026-10-09): the
    same keys, with `content`, `sources`, `verdict_note`, `confidence_score` and `verdict_source`
    blanked. The rule lives here so no list can ever leak a removed post's text.
    Context: `request` (for `is_mine`) and `now` (one clock for `emergency_active`).
    """

    def to_representation(self, post):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        now = self.context.get("now") or timezone.now()
        is_mine = bool(user and user.is_authenticated and post.author_id == user.pk)
        tombstone = post.status == PostStatus.REMOVED and not is_mine
        return {
            "id": str(post.pk),
            "author": user_summary(post.author),
            "content": "" if tombstone else post.content,
            "post_type": post.post_type,
            "status": post.status,
            "sources": (
                [] if tombstone else [{"value": s, "kind": source_kind(s)} for s in post.sources]
            ),
            "is_emergency": post.is_emergency,
            "emergency_active": is_active_emergency(post, now),
            "emergency_expires_at": iso(post.emergency_expires_at),
            "confidence_score": None if tombstone else shown_confidence(post),
            "verdict_source": None if tombstone else post.verdict_source,
            "verdict_note": "" if tombstone else post.verdict_note,
            "like_count": 0,
            "comment_count": 0,
            "repost_count": 0,
            "liked_by_me": False,
            "reposted_by_me": False,
            "bookmarked_by_me": False,
            "reported_by_me": False,
            "is_mine": is_mine,
            "can_appeal": False,
            "appeal_status": None,
            "created_at": iso(post.created_at),
        }


def feed_item(post_data):
    """One entry of a feed (§9). Recent only has originals; reposts arrive in Part 7B."""
    return {
        "kind": "post",
        "post": post_data,
        "reposted_by": None,
        "activity_at": post_data["created_at"],
    }


def fact_quota_data(quota):
    """`GET /api/v1/me/fact-quota/`. Part 11C adds an `emergency` block."""
    return {
        "limit": quota.limit,
        "used": quota.used,
        "remaining": quota.remaining,
        "window_hours": int(FACT_QUOTA_WINDOW.total_seconds() // 3600),
        "next_slot_at": iso(quota.next_slot_at),
    }
