"""Post search (Part 12): query cleaning and the queryset the view and the EXPLAIN test share."""

import re
import unicodedata

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F

from apps.posts.models import Post

MAX_QUERY_LENGTH = 200
SEARCH_CONFIG = "english"

# One token of a websearch query: `-"a phrase"`, `"a phrase"`, `-word` or `word`.
_TOKEN = re.compile(r'-?"[^"]*"?|\S+')
_WORD_CHARACTER = re.compile(r"\w")


class QueryTooLong(ValueError):
    pass


def strip_control_characters(value):
    """Controls are removed (NUL would be a Postgres error); tab and line breaks become spaces."""
    out = []
    for char in value:
        category = unicodedata.category(char)
        if category in ("Cc", "Cs"):
            if char in "\t\n\r\x0b\x0c":
                out.append(" ")
            continue
        out.append(char)
    return "".join(out)


def clean_post_query(raw):
    """The trimmed text to search for, "" when nothing is left. Raises `QueryTooLong` past 200
    code points."""
    query = strip_control_characters(raw).strip()
    if len(query) > MAX_QUERY_LENGTH:
        raise QueryTooLong
    return query


def has_positive_term(query):
    """Whether a websearch query has a term that can match. `-foo` alone is `!'foo'`, which GIN
    answers by walking the whole index (and matches nearly every post), so the view skips the
    database for it. `or` and a lone `-` are not terms; the client's highlighter drops the same
    tokens."""
    for token in _TOKEN.findall(query):
        if token.lower() == "or" or token.startswith("-"):
            continue
        if _WORD_CHARACTER.search(token):
            return True
    return False


def search_posts(query, viewer, *, post_type=None, status=None):
    """Visible posts matching `query`, best rank first, then newest. One SELECT.

    `visible()` is never removed or deleted; nothing else is excluded (pending, under review and
    emergency posts are found, as in the feeds). The rank takes `F("search_vector")`: a string
    would be wrapped in `SearchVector` and re-parse the stored vector's text with the wrong
    configuration.
    """
    search = SearchQuery(query, search_type="websearch", config=SEARCH_CONFIG)
    queryset = Post.objects.visible().filter(search_vector=search)
    if post_type:
        queryset = queryset.filter(post_type=post_type)
    if status:
        queryset = queryset.filter(status=status)
    return (
        queryset.annotate(rank=SearchRank(F("search_vector"), search))
        .order_by("-rank", "-created_at", "-id")
        .for_list(viewer)
    )
