"""Likes, comments, reposts, bookmarks and reports as annotations on a post queryset (§9).

`PostQuerySet.for_list(viewer)` calls `with_engagement`, so every list and the detail page get
`like_count`, `comment_count`, `repost_count`, `liked_by_me`, `reposted_by_me`, `bookmarked_by_me`
and `reported_by_me` in the same query as the posts: correlated subqueries, no N+1.
`PostSerializer` reads them strictly (a list that forgot them fails loudly instead of showing
zeros); a post that was just created has none yet, so `engagement_defaults` sets the zeros
explicitly. Bookmarks and reports have no count anywhere: only the viewer's own flag.
"""

from django.db.models import Count, Exists, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from apps.reports.models import Report
from apps.social.models import Bookmark, Comment, Like, Repost


def count_subquery(queryset, key):
    """A correlated `COUNT(*)` of `queryset` (already filtered on `OuterRef`), 0 when empty."""
    grouped = queryset.order_by().values(key).annotate(n=Count("pk")).values("n")
    return Coalesce(Subquery(grouped, output_field=IntegerField()), 0)


def shown_comments():
    """The comments the public sees: neither hidden by a moderator nor deleted by their author.

    This is the predicate of `comments_post_visible_idx`; keep the two in step.
    """
    return Comment.objects.filter(is_hidden=False, deleted_at__isnull=True)


def with_engagement(queryset, viewer=None):
    """Annotate a `Post` queryset with the counts and, for a signed-in `viewer`, the four
    `*_by_me` flags (all false for a visitor)."""
    post = OuterRef("pk")
    signed_in = viewer is not None and viewer.is_authenticated

    def mine(model, person="user"):
        if not signed_in:
            return Value(False)
        return Exists(model.objects.filter(post=post, **{person: viewer}))

    return queryset.annotate(
        like_count=count_subquery(Like.objects.filter(post=post), "post"),
        comment_count=count_subquery(shown_comments().filter(post=post), "post"),
        repost_count=count_subquery(Repost.objects.filter(post=post), "post"),
        liked_by_me=mine(Like),
        reposted_by_me=mine(Repost),
        bookmarked_by_me=mine(Bookmark),
        reported_by_me=mine(Report, "reporter"),
    )


def engagement_defaults(post):
    """A new post has no likes, comments, reposts or reports yet: say so on the instance."""
    post.like_count = 0
    post.comment_count = 0
    post.repost_count = 0
    post.liked_by_me = False
    post.reposted_by_me = False
    post.bookmarked_by_me = False
    post.reported_by_me = False
    return post
