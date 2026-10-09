from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.core.pagination import CursorPagination


class FeedPagination(CursorPagination):
    """Feed pages: newest first, ties broken by id, with the §9 feed envelope.

    DRF filters on the first ordering key and counts equal values with an offset, so posts that
    share a timestamp neither repeat nor go missing. One case degrades: a *whole page* sharing one
    timestamp falls back to a plain offset (which can't happen with microsecond timestamps).

    The cursor's position is user input that reaches a `created_at__lt=` filter, so it is checked
    here: a crafted one would otherwise raise Django's ValidationError and answer 500.
    """

    ordering = ("-created_at", "-id")

    def decode_cursor(self, request):
        cursor = super().decode_cursor(request)
        if cursor is not None and cursor.position is not None:
            try:
                moment = parse_datetime(cursor.position)
            except ValueError:
                moment = None
            if moment is None or moment.tzinfo is None:
                raise NotFound(self.invalid_cursor_message)
        return cursor

    def get_paginated_response(self, data):
        # `pinned` stays empty until emergency posts (Part 11C).
        return Response(
            {"pinned": [], "pinned_total": 0, "results": data, "next_cursor": self.get_next_link()}
        )
