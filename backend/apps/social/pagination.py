from apps.core.pagination import CursorPagination, TimestampCursorMixin


class UserListPagination(TimestampCursorMixin, CursorPagination):
    """Followers and following: the newest follow first, `{results, next_cursor}`.

    The position is the follow's `created_at`, so the mixin's cursor check applies.
    """

    ordering = ("-created_at", "-id")
