from rest_framework.response import Response

from apps.core.pagination import CursorPagination, TimestampCursorMixin


class FeedPagination(TimestampCursorMixin, CursorPagination):
    """Feed pages: newest first, ties broken by id, with the §9 feed envelope.

    DRF filters on the first ordering key and counts equal values with an offset, so posts that
    share a timestamp neither repeat nor go missing. One case degrades: a *whole page* sharing one
    timestamp falls back to a plain offset (which can't happen with microsecond timestamps).

    The cursor's position is user input that reaches a `created_at__lt=` filter, so
    `TimestampCursorMixin` checks it: a crafted one would otherwise answer 500.
    """

    ordering = ("-created_at", "-id")

    @staticmethod
    def envelope(results, next_cursor, *, pinned=(), pinned_total=0):
        """The §9 feed shape. `pinned` is filled on the first page of Recent and Following only
        (Part 11C); profiles and bookmarks keep it empty."""
        return Response(
            {
                "pinned": list(pinned),
                "pinned_total": pinned_total,
                "results": results,
                "next_cursor": next_cursor,
            }
        )

    def get_paginated_response(self, data):
        return self.envelope(data, self.get_next_link())


class EmergencyPagination(TimestampCursorMixin, CursorPagination):
    """`GET /api/v1/posts/emergencies/`: the active emergencies, newest first, 20 a page (up to
    50), `{results, next_cursor}`. A crafted cursor is a 404 (`TimestampCursorMixin`)."""

    ordering = ("-created_at", "-id")
