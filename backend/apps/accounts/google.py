"""Pre-checks for `POST auth/provider/token` ("Continue with Google", ARCHITECTURE §7).

allauth verifies the ID token itself (signature, `iss`, `aud`, `exp`, `iat`, `jti` replay). Two
shapes of forged token crash it with a 500 instead of a 400: a header without `kid` (KeyError) and
an HS256 header checked against Google's RSA key (TypeError). This module rejects every request
that isn't shaped like a real Google sign-in before allauth, without any network call.
"""

import json
import logging

import jwt
from django.conf import settings
from django.core.exceptions import RequestDataTooBig

logger = logging.getLogger(__name__)

PROVIDER = "google"
ALGORITHM = "RS256"  # what Google signs ID tokens with
MAX_ID_TOKEN_LENGTH = 4096
MAX_KID_LENGTH = 200
TOKEN_PARAM = "token"
INVALID_TOKEN_MESSAGE = "Invalid token."


def _header_ok(id_token):
    try:
        header = jwt.get_unverified_header(id_token)
    except jwt.PyJWTError:
        return False
    kid = header.get("kid")
    return (
        header.get("alg") == ALGORITHM and isinstance(kid, str) and 0 < len(kid) <= MAX_KID_LENGTH
    )


def check_provider_token_request(request):
    """True when `request` looks like a Google ID-token login that allauth can verify safely."""
    try:
        data = json.loads(request.body)
    except (ValueError, RequestDataTooBig):
        return False
    if not isinstance(data, dict) or data.get("provider") != PROVIDER:
        return False
    # Linking Google to a logged-in account (`connect`) is Part 14's, not this endpoint's.
    if data.get("process") != "login":
        return False
    token = data.get(TOKEN_PARAM)
    if not isinstance(token, dict):
        return False
    client_id = token.get("client_id")
    if client_id != settings.GOOGLE_OAUTH_CLIENT_ID:
        if isinstance(client_id, str):
            # Usually the frontend and backend env disagree. Names only, never the values.
            logger.warning(
                "A Google sign-in used a client_id that differs from GOOGLE_OAUTH_CLIENT_ID; "
                "check that NEXT_PUBLIC_GOOGLE_CLIENT_ID holds the same value"
            )
        return False
    id_token = token.get("id_token")
    if not isinstance(id_token, str) or not 0 < len(id_token) <= MAX_ID_TOKEN_LENGTH:
        return False
    return _header_ok(id_token)
