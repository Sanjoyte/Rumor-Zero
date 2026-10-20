"""Refresh-token rotation that survives two tabs and a lost response (ARCHITECTURE §7).

allauth's JWT strategy keeps the valid refresh-token ids (jti → exp) in the Django session and
removes a token the moment it is used, with no lock. Two concurrent refreshes then overwrite each
other's session save, and a response lost after the commit leaves the browser with a dead cookie.

This strategy changes only `refresh_token()`:
- the `django_session` row is locked for the whole refresh, so refreshes of one session run one
  after the other;
- a rotated token stays valid for ROTATION_GRACE_SECONDS instead of dying at once;
- a session deleted meanwhile (logout) is a plain failure, never a 500.

It reuses allauth's helpers in `headless/tokens/strategies/jwt/internal.py`. They are internal, so
re-check this module (and its tests) whenever django-allauth is upgraded.
"""

import time

from allauth.headless.tokens.strategies.jwt import internal
from allauth.headless.tokens.strategies.jwt.strategy import JWTTokenStrategy
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.models import Session
from django.db import transaction

ROTATION_GRACE_SECONDS = 60


def session_key_of(refresh_token):
    """The session key inside a refresh token with a valid signature and expiry, else None."""
    payload = internal.decode_token(refresh_token, "refresh")
    if payload is None:
        return None
    return internal.session_key_from_sid(payload["sid"]) or None


def session_key_of_payload(payload):
    """The session key behind a verified access-token payload (`request.auth`), else None."""
    sid = payload.get("sid") if isinstance(payload, dict) else None
    return (internal.session_key_from_sid(sid) or None) if isinstance(sid, str) else None


class RumorZeroJWTTokenStrategy(JWTTokenStrategy):
    def refresh_token(self, refresh_token):
        session_key = session_key_of(refresh_token)
        if session_key is None:
            return None
        try:
            with transaction.atomic():
                locked = Session.objects.select_for_update().filter(session_key=session_key)
                if not locked.exists():
                    return None
                # Reads the session again, now that no other refresh can change it.
                validated = internal.validate_refresh_token(refresh_token)
                if validated is None:
                    return None
                user, session, payload = validated

                access_token = internal.create_access_token(user, session, self.get_claims(user))
                now = int(time.time())
                state = internal.get_refresh_token_state(session)
                for jti, exp in list(state.items()):
                    if exp <= now:
                        del state[jti]
                # The used token keeps working for a short grace period (never longer than its own
                # expiry), so a retry after a lost response still succeeds.
                jti = payload["jti"]
                state[jti] = min(state.get(jti, now), now + ROTATION_GRACE_SECONDS)
                next_refresh_token = internal.create_refresh_token(user, session)
                session.save()
        except UpdateError:
            return None
        return access_token, next_refresh_token
