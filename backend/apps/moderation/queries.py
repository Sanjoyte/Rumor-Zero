"""What the post object says about appeals, as annotations on a post queryset (ARCHITECTURE §9).

`PostQuerySet.for_list(viewer)` calls `with_appeal_fields`, next to `with_engagement`, so every list
and the detail page carry `appeal_status` and `removal_reason` in the same query as the posts: two
correlated subqueries, no N+1. Both are the **author's** alone: a visitor or anyone else gets
`None` and `""`. `PostSerializer` reads them strictly (a list that forgot `for_list` fails loudly);
a post that was just created has neither yet, so `appeal_defaults` says so explicitly.
"""

from django.db.models import Case, CharField, OuterRef, Subquery, Value, When
from django.db.models.functions import Coalesce

from apps.moderation.models import ActionKind, Appeal, ModerationAction
from apps.posts.models import PostStatus


def with_appeal_fields(queryset, viewer=None):
    """Annotate a `Post` queryset with `appeal_status` (the viewer's own appeal of the post, or
    null) and `removal_reason` (the `public_note` of the post's latest `removed` row, for the
    author of a removed post; `""` otherwise)."""
    if viewer is None or not viewer.is_authenticated:
        return queryset.annotate(
            appeal_status=Value(None, output_field=CharField()),
            removal_reason=Value("", output_field=CharField()),
        )
    mine = Appeal.objects.filter(post=OuterRef("pk"), author=viewer)
    latest_removal = ModerationAction.objects.filter(
        post=OuterRef("pk"), action=ActionKind.REMOVED
    ).order_by("-created_at")
    return queryset.annotate(
        appeal_status=Subquery(mine.values("status")[:1], output_field=CharField()),
        # Only the author of a removed post is told the reason (the serializer gates it again),
        # and Postgres runs the subquery only for such a row.
        removal_reason=Case(
            When(
                author=viewer,
                status=PostStatus.REMOVED,
                then=Coalesce(
                    Subquery(latest_removal.values("public_note")[:1], output_field=CharField()),
                    Value(""),
                ),
            ),
            default=Value(""),
            output_field=CharField(),
        ),
    )


def appeal_defaults(post):
    """A new post has no appeal and no removal reason."""
    post.appeal_status = None
    post.removal_reason = ""
    return post


def with_verdict_time(queryset):
    """Annotate a `Post` queryset with `moderator_verdict_at`: when a moderator last decided the
    post's current label (Mark verified or Mark FALSE into the status it has now), from the audit
    row. Not `moderated_at`, which every later moderator action (Demote, Dismiss, Escalate)
    overwrites. Null when no row matches. `modaction_post_created_idx` serves the subquery."""
    decided = ModerationAction.objects.filter(
        post=OuterRef("pk"),
        action__in=(ActionKind.VERIFIED, ActionKind.MARKED_FALSE),
        to_status=OuterRef("status"),
    ).order_by("-created_at")
    return queryset.annotate(moderator_verdict_at=Subquery(decided.values("created_at")[:1]))
