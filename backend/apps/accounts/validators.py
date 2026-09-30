"""Username and email rules (ARCHITECTURE §2). Reused by Part 1's availability endpoint."""

import re
import unicodedata

from django.core.exceptions import ValidationError

USERNAME_PATTERN = r"^[a-z0-9_]{3,30}$"
_USERNAME_RE = re.compile(USERNAME_PATTERN)

# Exact match, after lowercasing. "ada_admin" is fine; "admin" is not.
RESERVED_USERNAMES = frozenset(
    {
        # routes and system
        *[
            "admin",
            "administrator",
            "api",
            "auth",
            "login",
            "logout",
            "signin",
            "signout",
            "signup",
            "register",
            "settings",
            "account",
            "accounts",
            "home",
            "feed",
            "search",
            "explore",
            "notifications",
            "bookmarks",
            "messages",
            "profile",
            "user",
            "users",
            "post",
            "posts",
            "static",
            "media",
            "brand",
            "dev",
            "health",
            "internal",
            "privacy",
            "terms",
            "about",
            "help",
            "support",
            "contact",
            "status",
            "security",
            "abuse",
            "legal",
            "www",
            "mail",
            "email",
            "noreply",
            "no_reply",
            "postmaster",
            "webmaster",
            "hostmaster",
            "root",
            "system",
            "null",
            "undefined",
            "none",
            "anonymous",
            "unknown",
            "deleted",
            "removed",
        ],
        # staff and brand
        *[
            "mod",
            "mods",
            "moderator",
            "moderators",
            "moderation",
            "senior_moderator",
            "staff",
            "team",
            "official",
            "rumorzero",
            "rumor_zero",
            "factcheck",
            "fact_check",
            "factchecker",
            "fact_checker",
        ],
        # labels
        *["verified", "false", "true", "emergency", "pipeline", "fact", "facts", "opinion"],
    }
)


def normalize_username(value):
    return unicodedata.normalize("NFKC", value).strip().lower()


def normalize_email(value):
    return value.strip().lower()


def validate_username(value):
    """Validate a username after normalising it (so "Ada" passes and "ADMIN" is reserved)."""
    value = normalize_username(value)
    if not _USERNAME_RE.fullmatch(value):
        raise ValidationError(
            "Usernames are 3–30 characters: lowercase letters, numbers and underscores only.",
            code="invalid_username",
        )
    if value in RESERVED_USERNAMES:
        raise ValidationError("This username is reserved.", code="reserved_username")
