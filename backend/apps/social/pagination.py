from apps.core.pagination import CursorPagination, TimestampCursorMixin


class UserListPagination(TimestampCursorMixin, CursorPagination):
    """Followers and following: the newest follow first, `{results, next_cursor}`.

    The position is the follow's `created_at`, so the mixin's cursor check applies.
    """

    ordering = ("-created_at", "-id")


class CommentPagination(TimestampCursorMixin, CursorPagination):
    """Comments on a post, **oldest first** (`{results, next_cursor}`).

    Ascending, so DRF filters on `created_at > position`; the mixin checks the position as for
    the descending lists, and the id breaks ties.
    """

    ordering = ("created_at", "id")


class BookmarkPagination(TimestampCursorMixin, CursorPagination):
    """Your bookmarks, the newest bookmark first (`{results, next_cursor}`, §9 envelope)."""

    ordering = ("-created_at", "-id")
