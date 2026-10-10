"""The profile and user-row objects (ARCHITECTURE §9)."""

from django.db.models import Exists, OuterRef, Value
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import avatar_url, user_summary
from apps.posts.models import Post, PostStatus
from apps.posts.serializers import content_field, iso
from apps.social.engagement import count_subquery as _count
from apps.social.models import Follow

# The credibility score is public only after this many counted events (ARCHITECTURE §4a). Nothing
# writes `reputation_sample` before Part 11B, so `score` is null until then.
MIN_PUBLIC_SAMPLE = 3


def _by_status(author, status):
    return Post.objects.filter(author=author, status=status)


def profile_queryset(viewer):
    """Active users with every profile count as an annotation: one query for the whole profile."""
    me = OuterRef("pk")
    is_following = (
        Exists(Follow.objects.filter(follower=viewer, following=me))
        if viewer is not None and viewer.is_authenticated
        else Value(False)
    )
    return User.objects.filter(is_active=True).annotate(
        followers_n=_count(Follow.objects.filter(following=me), "following"),
        following_n=_count(Follow.objects.filter(follower=me), "follower"),
        # Only what the public can see...
        posts_n=_count(Post.objects.visible().filter(author=me), "author"),
        # ...but a deleted post keeps its verdict in the record (user decision 2026-10-09). A
        # removed post's status is `removed`, so it is in neither.
        verified_n=_count(_by_status(me, PostStatus.VERIFIED_TRUE), "author"),
        false_n=_count(_by_status(me, PostStatus.VERIFIED_FALSE), "author"),
        is_following_n=is_following,
    )


def reputation_block(user):
    return {
        "score": user.reputation_score if user.reputation_sample >= MIN_PUBLIC_SAMPLE else None,
        "sample": user.reputation_sample,
    }


def _person(user):
    return {
        "id": str(user.pk),
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "avatar_url": avatar_url(user),
    }


def profile_data(user, viewer):
    """`GET /api/v1/users/{username}/`; `user` comes from `profile_queryset`."""
    return {
        **_person(user),
        "created_at": iso(user.created_at),
        "counts": {
            "followers": user.followers_n,
            "following": user.following_n,
            "posts": user.posts_n,
            "verified": user.verified_n,
            "false": user.false_n,
        },
        "reputation": reputation_block(user),
        "is_following": bool(user.is_following_n),
        "is_me": bool(viewer is not None and viewer.is_authenticated and viewer.pk == user.pk),
    }


def user_row(user, *, is_following, viewer):
    """One row of the followers and following lists."""
    return {
        **_person(user),
        "reputation": reputation_block(user),
        "is_following": is_following,
        "is_me": bool(viewer is not None and viewer.is_authenticated and viewer.pk == user.pk),
    }


class CommentCreateSerializer(serializers.Serializer):
    """`POST /api/v1/posts/{id}/comments/`. The text rules are the posts' (trimmed, 1 to 500 code
    points, the same messages); undeclared fields are ignored."""

    content = content_field()


def comment_data(comment, viewer):
    """A comment object (ARCHITECTURE §9): five keys, and nothing about moderation."""
    return {
        "id": str(comment.pk),
        "author": user_summary(comment.author),
        "content": comment.content,
        "is_mine": bool(viewer and viewer.is_authenticated and comment.author_id == viewer.pk),
        "created_at": iso(comment.created_at),
    }
