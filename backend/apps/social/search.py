"""People search (Part 12): prefix match on the username, word-start match on the display name."""

import re
import unicodedata

from django.db.models import Case, Exists, IntegerField, OuterRef, Q, Value, When

from apps.accounts.models import User
from apps.accounts.validators import normalize_username
from apps.posts.search import strip_control_characters
from apps.social.models import Follow
from apps.social.serializers import verified_count

MAX_PEOPLE_QUERY_LENGTH = 64

_SPACES = re.compile(r"\s+")
# A display-name word starts at the beginning or after one of these.
_WORD_BREAKS = (" ", "-", "'", "’")


def clean_people_query(raw):
    """The text to match, "" when nothing searchable is left.

    Normalised like a username (NFKC, trimmed, lower-cased), spaces collapsed, a leading `@`
    dropped, and cut at 64 characters *after* normalising (NFKC can make text longer). Text with
    no letter, digit or underscore (`-`, `'`) would match every display name through `icontains`.
    """
    text = normalize_username(strip_control_characters(raw))
    text = _SPACES.sub(" ", text)
    text = text.removeprefix("@")
    text = text[:MAX_PEOPLE_QUERY_LENGTH].strip()
    if not any(char == "_" or unicodedata.category(char)[0] in ("L", "N") for char in text):
        return ""
    return text


def search_people(query, viewer):
    """Active users whose username starts with `query` or whose display name has a word that
    does. Exact username first, then username prefix, then name matches; A to Z by username
    inside each, never by credibility.

    Every arm is a Django lookup (`startswith` escapes `%`, `_` and `\\`, and `_` is a legal
    username character); no pattern is built from user text.
    """
    match = Q(username__startswith=query) | Q(display_name__istartswith=query)
    for lead in _WORD_BREAKS:
        match |= Q(display_name__icontains=lead + query)
    queryset = (
        User.objects.filter(is_active=True)
        .filter(match)
        .annotate(
            verified_n=verified_count(OuterRef("pk")),
            # Username matches first; an exact one sorts first among them by itself (the query is
            # a prefix of every other match), then the display-name matches.
            closeness=Case(
                When(username__startswith=query, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
        )
    )
    if viewer is not None and viewer.is_authenticated:
        queryset = queryset.annotate(
            viewer_follows=Exists(Follow.objects.filter(follower=viewer, following=OuterRef("pk")))
        )
    return queryset.order_by("closeness", "username")
