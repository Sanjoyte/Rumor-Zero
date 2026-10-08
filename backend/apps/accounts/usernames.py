"""Usernames for new Google accounts (ARCHITECTURE §7; ANALYSIS c-29).

The handle comes from Google's first name, never from the email address (a public handle must not
reveal the inbox). Usernames can't be renamed until Settings (Part 14).
"""

import re
import secrets
import unicodedata
import uuid

from apps.accounts.models import User
from apps.accounts.validators import RESERVED_USERNAMES

SLUG_LENGTH = 20
MIN_SLUG_LENGTH = 3
MAX_TRIES = 10
FALLBACK_PREFIX = "member"
_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _is_taken(username):
    return User.objects.filter(username=username).exists()


def slugify_name(given_name):
    """ "Mary-Jane" → "mary_jane". Non-Latin letters have no ASCII form and are dropped."""
    ascii_name = (
        unicodedata.normalize("NFKD", given_name or "").encode("ascii", "ignore").decode("ascii")
    )
    slug = _NON_ALNUM.sub("_", ascii_name.lower())
    # Cut first and strip afterwards, so the cut can't leave a trailing "_".
    return slug[:SLUG_LENGTH].strip("_")


def generate_username(given_name, *, is_taken=_is_taken, rng=None):
    """A free, valid, non-reserved username. Every result matches USERNAME_PATTERN."""
    rng = rng or secrets.SystemRandom()
    slug = slugify_name(given_name)
    # A reserved slug ("admin") goes straight to the fallback: "admin_4821" would still read as
    # official. Slugs are at most 20 characters, so "<slug>_dddd" is at most 25.
    if slug and slug not in RESERVED_USERNAMES:
        if len(slug) >= MIN_SLUG_LENGTH and not is_taken(slug):
            return slug
        for _ in range(MAX_TRIES):
            candidate = f"{slug}_{rng.randrange(10000):04d}"
            if not is_taken(candidate):
                return candidate
    for _ in range(MAX_TRIES):
        candidate = FALLBACK_PREFIX + "_" + "".join(rng.choice(_ALPHABET) for _ in range(6))
        if not is_taken(candidate):
            return candidate
    return f"{FALLBACK_PREFIX}_{uuid.uuid4().hex[:12]}"
