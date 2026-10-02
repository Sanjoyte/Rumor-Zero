"""Cloudflare Turnstile server-side check for sign-up (ARCHITECTURE §7).

Uses the standard library, so no HTTP client dependency is added. It fails closed (user decision
2026-10-01): if siteverify can't be reached, or rejects our secret, sign-up is refused.
The token and the secret are never logged.
"""

import enum
import json
import logging
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TIMEOUT_SECONDS = 5
# Cloudflare's tokens are at most 2048 characters.
MAX_TOKEN_LENGTH = 2048
# Our configuration or Cloudflare is at fault, not the visitor.
_UNAVAILABLE_CODES = {"missing-input-secret", "invalid-input-secret", "internal-error"}
_SECRET_CODES = {"missing-input-secret", "invalid-input-secret"}


class TurnstileResult(enum.Enum):
    OK = "ok"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class _Retryable(Exception):
    """A network error or a 5xx: worth one more try with the same idempotency key."""


def _post(data):
    request = Request(
        SITEVERIFY_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code >= 500:
            raise _Retryable(f"HTTP {exc.code}") from None
        try:
            return json.loads(exc.read().decode("utf-8"))
        except (ValueError, OSError):
            return None
    except (URLError, TimeoutError, OSError) as exc:
        raise _Retryable(type(exc).__name__) from None
    except ValueError:
        return None


def verify_turnstile(token, remote_ip):
    """Ask siteverify about a widget token. Returns a TurnstileResult."""
    fields = {
        "secret": settings.TURNSTILE_SECRET_KEY,
        "response": token,
        "idempotency_key": str(uuid.uuid4()),
    }
    if remote_ip:
        fields["remoteip"] = remote_ip
    data = urlencode(fields).encode()

    outcome = None
    for attempt in (1, 2):
        try:
            outcome = _post(data)
            break
        except _Retryable as exc:
            if attempt == 2:
                logger.warning("Turnstile siteverify unreachable (%s)", exc)
                return TurnstileResult.UNAVAILABLE

    if not isinstance(outcome, dict):
        logger.warning("Turnstile siteverify sent an unreadable answer")
        return TurnstileResult.UNAVAILABLE
    if outcome.get("success") is True:
        return TurnstileResult.OK

    codes = outcome.get("error-codes")
    codes = {code for code in codes if isinstance(code, str)} if isinstance(codes, list) else set()
    if codes & _SECRET_CODES:
        logger.error("Turnstile siteverify rejected TURNSTILE_SECRET_KEY: check the variable")
        return TurnstileResult.UNAVAILABLE
    if codes & _UNAVAILABLE_CODES:
        logger.warning("Turnstile siteverify reported an internal error")
        return TurnstileResult.UNAVAILABLE
    return TurnstileResult.FAILED
