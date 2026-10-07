"""Every request under /api/auth/ passes through here (ARCHITECTURE §7).

allauth's app views are CSRF-exempt and read any body as JSON, and their responses carry the
refresh token and the raw session key. So, before allauth runs:
1. only the allow-listed endpoints answer (everything else is 404);
2. unsafe methods need `Origin: FRONTEND_ORIGIN` and `X-Requested-With: rumor-zero` (403);
3. login, signup, refresh, verify and the password-reset calls ignore any Authorization /
   X-Session-Token header;
4. sign-up must pass Turnstile first, so a bot learns nothing (not even "email taken");
5. refresh takes its token from the `rz_refresh` cookie only;
6. a password-reset request is also capped per day per address and per IP (a separate allauth
   action, because allauth keeps one history per action and "per" type).

And afterwards:
- every body becomes JSON (an HTML error page is replaced), with no token secret left in it;
- a new refresh token goes into the cookie, and a rejected refresh deletes the cookies;
- a verification that succeeded answers 200 (allauth says 401 because nobody is logged in);
- `Cache-Control: no-store`.
"""

import io
import json

from allauth.core import ratelimit
from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.utils.cache import add_never_cache_headers

from apps.accounts import cookies
from apps.accounts.turnstile import MAX_TOKEN_LENGTH, TurnstileResult, verify_turnstile

AUTH_PREFIX = "/api/auth/"
_APP = "/api/auth/app/v1/"
LOGIN_PATH = _APP + "auth/login"
SIGNUP_PATH = _APP + "auth/signup"
REFRESH_PATH = _APP + "tokens/refresh"
VERIFY_EMAIL_PATH = _APP + "auth/email/verify"
PASSWORD_REQUEST_PATH = _APP + "auth/password/request"
PASSWORD_RESET_PATH = _APP + "auth/password/reset"
LOGOUT_PATH = "/api/auth/logout/"

# path → allowed methods. The only allauth endpoints that answer; Part 3 adds its own.
# (Resend is ours: POST /api/v1/me/verification-email/. allauth's `auth/email/verify/resend` is the
# code-flow view and stays unlisted.)
ALLAUTH_ENDPOINTS = {
    LOGIN_PATH: {"POST"},
    SIGNUP_PATH: {"POST"},
    REFRESH_PATH: {"POST"},
    VERIFY_EMAIL_PATH: {"POST"},
    PASSWORD_REQUEST_PATH: {"POST"},
    PASSWORD_RESET_PATH: {"GET", "POST"},
}
# These never run "as" a token the request carries: login, signup, refresh and reset issue fresh
# tokens, and a verification link or reset key works for whoever holds it, so a stale Bearer must
# not turn into allauth's 410.
_ANONYMOUS_ENDPOINTS = set(ALLAUTH_ENDPOINTS)
_ISSUING_ENDPOINTS = {LOGIN_PATH, SIGNUP_PATH, PASSWORD_RESET_PATH}
_COOKIE_ENDPOINTS = {REFRESH_PATH, LOGOUT_PATH}

CSRF_HEADER_VALUE = "rumor-zero"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# A refresh answered with one of these leaves the browser nothing to keep.
REJECTED_REFRESH = {400, 401, 410}
TURNSTILE_PARAM = "turnstile_token"
TURNSTILE_FAILED = "The bot check didn't pass. Try it again."
TURNSTILE_UNAVAILABLE = "We couldn't run the bot check. Try again in a minute."
RESET_DAILY_ACTION = "reset_password_daily"


def error_response(status, code=None, message=None, param=None):
    """allauth's envelope, `{"status", "errors": [{code, param?, message}]}`."""
    body = {"status": status}
    if code:
        error = {"code": code, "message": message}
        if param:
            error["param"] = param
        body["errors"] = [error]
    return JsonResponse(body, status=status)


def _json_body(response):
    if "json" in response.get("Content-Type", ""):
        try:
            body = json.loads(response.content)
        except ValueError:
            body = None
        if isinstance(body, dict):
            return body
    # e.g. Django's HTML error pages: the DEBUG one prints the request's cookies.
    return {"status": response.status_code}


def _replace_body(request, data):
    body = json.dumps(data).encode()
    request._body = body
    request._stream = io.BytesIO(body)
    request._read_started = False
    for parsed in ("_post", "_files"):
        if hasattr(request, parsed):
            delattr(request, parsed)
    request.META["CONTENT_TYPE"] = "application/json"
    request.META["CONTENT_LENGTH"] = str(len(body))
    request.content_type = "application/json"
    request.content_params = {}


class AuthApiMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if not path.startswith(AUTH_PREFIX):
            return self.get_response(request)
        response = self._before(request, path)
        if response is None:
            response = self.get_response(request)
        return self._after(request, path, response)

    # ---------- request phase ----------

    def _before(self, request, path):
        if path != LOGOUT_PATH and request.method not in ALLAUTH_ENDPOINTS.get(path, ()):
            return error_response(404, "not_found", "Not found.")
        # Before the safe-method return: a GET carrying a stale Bearer would get allauth's 410.
        if path in _ANONYMOUS_ENDPOINTS:
            request.META.pop("HTTP_AUTHORIZATION", None)
            request.META.pop("HTTP_X_SESSION_TOKEN", None)
        if request.method in SAFE_METHODS:
            return None
        if not self._same_site(request):
            return error_response(403, "csrf_failed", "Reload the page and try again.")
        if path in _COOKIE_ENDPOINTS:
            copies = cookies.count_cookie(
                request.META.get("HTTP_COOKIE", ""), cookies.REFRESH_COOKIE
            )
            if copies > 1:
                return error_response(400, "invalid_cookie", "Log in again.")
        if path == SIGNUP_PATH:
            return self._check_turnstile(request)
        if path == PASSWORD_REQUEST_PATH:
            return self._check_reset_daily_cap(request)
        if path == REFRESH_PATH:
            return self._inject_refresh_token(request)
        return None

    @staticmethod
    def _same_site(request):
        return (
            request.META.get("HTTP_ORIGIN") == settings.FRONTEND_ORIGIN
            and request.META.get("HTTP_X_REQUESTED_WITH") == CSRF_HEADER_VALUE
        )

    @staticmethod
    def _turnstile_token(request):
        try:
            data = json.loads(request.body)
        except (ValueError, RequestDataTooBig):
            return None
        token = data.get(TURNSTILE_PARAM) if isinstance(data, dict) else None
        if not isinstance(token, str) or not token.strip() or len(token) > MAX_TOKEN_LENGTH:
            return None
        return token

    def _check_turnstile(self, request):
        # Same IP bucket as allauth's own signup limit; when it is full, Cloudflare isn't asked.
        if not ratelimit.consume(request, action="signup", dry_run=True):
            return error_response(429)
        token = self._turnstile_token(request)
        if token is None:
            result = TurnstileResult.FAILED
        else:
            result = verify_turnstile(token, request.META.get("REMOTE_ADDR", ""))
        if result is TurnstileResult.OK:
            return None  # allauth's view counts this attempt itself
        ratelimit.consume(request, action="signup")
        if result is TurnstileResult.UNAVAILABLE:
            return error_response(
                400, "turnstile_unavailable", TURNSTILE_UNAVAILABLE, TURNSTILE_PARAM
            )
        return error_response(400, "turnstile_failed", TURNSTILE_FAILED, TURNSTILE_PARAM)

    @staticmethod
    def _reset_request_key(request):
        """The rate-limit key allauth uses for a reset request: the lowercased email, or None."""
        try:
            data = json.loads(request.body)
        except (ValueError, RequestDataTooBig):
            return None
        email = data.get("email") if isinstance(data, dict) else None
        # A per-key rate with no key raises; allauth answers a missing or odd email with 400.
        return email.strip().lower() if isinstance(email, str) else None

    def _check_reset_daily_cap(self, request):
        key = self._reset_request_key(request)
        request.rz_reset_key = key
        if key is not None and not ratelimit.consume(
            request, action=RESET_DAILY_ACTION, key=key, dry_run=True
        ):
            return error_response(429)
        return None

    @staticmethod
    def _inject_refresh_token(request):
        token = request.COOKIES.get(cookies.REFRESH_COOKIE, "")
        if not token:
            return error_response(401)
        # Whatever the client sent as the body is discarded: the cookie is the only source.
        _replace_body(request, {"refresh_token": token})
        return None

    # ---------- response phase ----------

    def _after(self, request, path, response):
        if getattr(response, "streaming", False):
            return response
        if response.status_code not in (204, 304):
            body, refresh_token = cookies.extract_tokens(_json_body(response))
            if (
                path == VERIFY_EMAIL_PATH
                and request.method == "POST"
                and response.status_code == 401
            ):
                # allauth answers 401 when a verification succeeds with nobody logged in. That is
                # the only way this endpoint succeeds here (the auth headers were dropped).
                response.status_code = 200
                body = {"status": 200}
            response.content = json.dumps(body).encode()
            response["Content-Type"] = "application/json"
            if response.has_header("Content-Length"):
                response["Content-Length"] = str(len(response.content))
            if refresh_token:
                if path in _ISSUING_ENDPOINTS:
                    # A new login replaces whatever session the browser's old cookie belonged to.
                    cookies.revoke_refresh_token_session(
                        request.COOKIES.get(cookies.REFRESH_COOKIE, "")
                    )
                cookies.set_auth_cookies(response, refresh_token)
        if path in _COOKIE_ENDPOINTS and response.status_code in REJECTED_REFRESH:
            cookies.delete_auth_cookies(response)
        if path == PASSWORD_REQUEST_PATH and response.status_code == 200:
            # Only an accepted request counts towards the daily cap (a 400 or 429 doesn't).
            key = getattr(request, "rz_reset_key", None)
            if key is not None:
                ratelimit.consume(request, action=RESET_DAILY_ACTION, key=key)
        add_never_cache_headers(response)
        return response
