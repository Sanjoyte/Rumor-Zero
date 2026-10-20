import base64
from urllib import parse

from django.utils.dateparse import parse_datetime
from rest_framework import pagination
from rest_framework.exceptions import NotFound
from rest_framework.response import Response


class CursorPagination(pagination.CursorPagination):
    """Cursor pagination returning {"results": [...], "next_cursor": token | null}.

    The cursor is a bare, URL-safe token: no absolute `next` URL, which would point past the
    API relay (ARCHITECTURE §9). Views override `ordering` for their own sort key.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50
    ordering = "-created_at"

    def encode_cursor(self, cursor):
        tokens = {}
        if cursor.offset != 0:
            tokens["o"] = str(cursor.offset)
        if cursor.reverse:
            tokens["r"] = "1"
        if cursor.position is not None:
            tokens["p"] = cursor.position
        querystring = parse.urlencode(tokens, doseq=True)
        return base64.urlsafe_b64encode(querystring.encode("ascii")).decode("ascii").rstrip("=")

    def decode_cursor(self, request):
        token = request.query_params.get(self.cursor_query_param)
        if token is None:
            return None
        try:
            padded = token + "=" * (-len(token) % 4)
            querystring = base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")
            tokens = parse.parse_qs(querystring, keep_blank_values=True)
            offset = pagination._positive_int(tokens.get("o", ["0"])[0], cutoff=self.offset_cutoff)
            reverse = bool(int(tokens.get("r", ["0"])[0]))
            position = tokens.get("p", [None])[0]
        except (TypeError, ValueError):
            raise NotFound(self.invalid_cursor_message) from None
        return pagination.Cursor(offset=offset, reverse=reverse, position=position)

    def get_paginated_response(self, data):
        # get_next_link() builds the link from encode_cursor(), so it is the bare token here.
        return Response({"results": data, "next_cursor": self.get_next_link()})

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": ["results", "next_cursor"],
            "properties": {
                "results": schema,
                "next_cursor": {"type": "string", "nullable": True},
            },
        }


class TimestampCursorMixin:
    """For a list ordered by a timestamp first (`-created_at`, or `created_at` for comments):
    check the cursor's position.

    DRF passes the position straight into a `created_at__lt=…` filter, so a crafted cursor would
    raise Django's ValidationError and answer 500. Put it before `CursorPagination` in the bases.
    """

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


OFFSET_PAGE_SIZE = 20
OFFSET_MAX_PAGES = 5


def offset_page_number(request, *, max_pages=OFFSET_MAX_PAGES):
    """The page asked for by `?cursor=`: 1 when it is missing or empty, otherwise the string of
    a number from 2 to `max_pages`. Anything else ("1", "0", "6", "02", "abc") is a 404 like
    every crafted cursor, so the client restarts from the top."""
    token = request.query_params.get("cursor")
    if token is None or token == "":
        return 1
    if token not in {str(number) for number in range(2, max_pages + 1)}:
        raise NotFound(pagination.CursorPagination.invalid_cursor_message)
    return int(token)


def paginate_offset(queryset, request, *, page_size=OFFSET_PAGE_SIZE, max_pages=OFFSET_MAX_PAGES):
    """`(rows, next_cursor)` for a list ordered by relevance, which has no timestamp to put in a
    cursor (ARCHITECTURE §9: the documented deviation): a bounded offset, at most `max_pages`
    pages. `next_cursor` is the next page number as a plain string, null when there is no
    further row (one extra is read to know) or the cap is reached. Results can shift between
    pages while posts arrive; that is accepted."""
    page = offset_page_number(request, max_pages=max_pages)
    start = (page - 1) * page_size
    rows = list(queryset[start : start + page_size + 1])
    has_more = len(rows) > page_size and page < max_pages
    return rows[:page_size], str(page + 1) if has_more else None
