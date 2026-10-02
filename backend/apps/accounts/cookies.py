"""The refresh cookie and the session hint (ARCHITECTURE §7).

- `rz_refresh` holds the refresh token: HttpOnly, SameSite=Lax, Path=/api/auth/, no Domain. It
  arrives through the relay, so it is a host-only cookie of the frontend origin.
- `rz_session=1` is a non-secret hint the frontend can read (Path=/). It is set and cleared with
  `rz_refresh`, so anonymous page loads can skip the refresh call.

The token secrets allauth puts in its JSON bodies never reach the browser: `extract_tokens()`
removes them, and the middleware moves the refresh token into the cookie.
"""

from django.conf import settings
from django.contrib.sessions.models import Session

from apps.accounts.tokens import session_key_of

REFRESH_COOKIE = "rz_refresh"
REFRESH_COOKIE_PATH = "/api/auth/"
HINT_COOKIE = "rz_session"
HINT_COOKIE_PATH = "/"
_EPOCH = "Thu, 01 Jan 1970 00:00:00 GMT"

# Where allauth puts token secrets: login/signup use `meta`, refresh uses `data`.
_SECRET_FIELDS = {
    "meta": ("refresh_token", "session_token"),
    "data": ("refresh_token",),
}


def _cookie_kwargs():
    return {"secure": settings.AUTH_COOKIE_SECURE, "samesite": "Lax"}


def set_auth_cookies(response, refresh_token):
    max_age = settings.REFRESH_TOKEN_SECONDS
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=max_age,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        **_cookie_kwargs(),
    )
    response.set_cookie(
        HINT_COOKIE, "1", max_age=max_age, path=HINT_COOKIE_PATH, httponly=False, **_cookie_kwargs()
    )


def delete_auth_cookies(response):
    """Expire both cookies, with the same attributes they were set with."""
    for name, path, httponly in (
        (REFRESH_COOKIE, REFRESH_COOKIE_PATH, True),
        (HINT_COOKIE, HINT_COOKIE_PATH, False),
    ):
        response.set_cookie(
            name, "", max_age=0, expires=_EPOCH, path=path, httponly=httponly, **_cookie_kwargs()
        )


def extract_tokens(body):
    """Remove every token secret from an allauth body. Returns (body, refresh_token or None).

    The access token stays: the frontend keeps it in memory. The session token is the raw Django
    session key, so it never leaves the server.
    """
    if not isinstance(body, dict):
        return body, None
    refresh_token = None
    for section, fields in _SECRET_FIELDS.items():
        part = body.get(section)
        if not isinstance(part, dict):
            continue
        for field in fields:
            value = part.pop(field, None)
            if field == "refresh_token" and isinstance(value, str) and value:
                refresh_token = value
    return body, refresh_token


def count_cookie(header, name):
    """How many times `name` appears in a raw Cookie header (Django keeps only the last one)."""
    count = 0
    for pair in header.split(";"):
        key, sep, _ = pair.strip().partition("=")
        if sep and key.strip() == name:
            count += 1
    return count


def revoke_refresh_token_session(refresh_token):
    """Delete the session behind a refresh token, which ends every token issued for it.

    Only the signature and expiry are checked, so a rotated token still identifies its session.
    Returns True when a session was deleted.
    """
    session_key = session_key_of(refresh_token) if refresh_token else None
    if session_key is None:
        return False
    deleted, _ = Session.objects.filter(session_key=session_key).delete()
    return deleted > 0
