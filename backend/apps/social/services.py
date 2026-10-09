"""Following and unfollowing (ARCHITECTURE §2, §9). No HTTP here: the views map the errors.

Only this module writes `Follow` rows. Each change forgets the follower's cached Following feed
(`feed.bust_following_feed`); the people you follow reach you after at most `FEED_CACHE_SECONDS`.
"""

import re

from apps.accounts.models import User
from apps.accounts.validators import normalize_username
from apps.social.feed import bust_following_feed
from apps.social.models import Follow

# A longer name can't be a username (30 at most), so it is cut before it is normalised.
MAX_LOOKUP_LENGTH = 64


class SelfFollow(Exception):
    """You can't follow yourself."""


_USERNAME_RE = re.compile(r"[a-z0-9_]{3,30}")


def lookup_name(raw):
    """The stored form of a username typed in a URL, or None if it can't be one.

    Anything that isn't a valid username is refused here, before the database: a NUL byte, for
    one, makes Postgres raise (a 500), and a valid name never contains one.
    """
    if not isinstance(raw, str):
        return None
    username = normalize_username(raw[:MAX_LOOKUP_LENGTH])
    return username if _USERNAME_RE.fullmatch(username) else None


def find_active_user(raw):
    """The active user called `raw` (case-insensitive), or None.

    Usernames are stored lowercase, so this is an exact hit on the unique index.
    """
    username = lookup_name(raw)
    if username is None:
        return None
    return User.objects.filter(username=username, is_active=True).first()


def follow(*, follower, target):
    """Follow `target`. True if this created the follow, False if it already existed.

    `get_or_create` survives two simultaneous requests: the unique pair refuses the second insert
    and Django reads the row back.
    """
    if follower.pk == target.pk:
        raise SelfFollow
    _, created = Follow.objects.get_or_create(follower=follower, following=target)
    bust_following_feed(follower.pk)
    return created


def unfollow(*, follower, target):
    """Stop following `target`. Quietly does nothing if you weren't."""
    Follow.objects.filter(follower=follower, following=target).delete()
    bust_following_feed(follower.pk)
