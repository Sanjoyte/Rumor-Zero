"""Every request under /api/auth/ passes through here (ARCHITECTURE §7).

allauth's app views are CSRF-exempt and read any body as JSON, and their responses carry the
refresh token and the raw session key. So, before allauth runs:
1. only the allow-listed endpoints answer (everything else is 404);
2. unsafe methods need `Origin: FRONTEND_ORIGIN` and `X-Requested-With: rumor-zero` (403);
3. login, signup and refresh ignore any Authorization / X-Session-Token header;
4. sign-up must pass Turnstile first, so a bot learns nothing (not even "email taken");
5. refresh takes its token from the `rz_refresh` cookie only.

And afterwards:
- every body becomes JSON (an HTML error page is replaced), with no token secret left in it;
- a new refresh token goes into the cookie, and a rejected refresh deletes the cookies;
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
LOGOUT_PATH = "/api/auth/logout/"

# path → allowed methods. The only allauth endpoints that answer; Parts 2 and 3 add their own.
ALLAUTH_ENDPOINTS = {
    LOGIN_PATH: {"POST"},
    SIGNUP_PATH: {"POST"},
    REFRESH_PATH: {"POST"},
}
# These issue fresh tokens, so they must never run "as" a token the request already carries.
_TOKEN_ENDPOINTS = {LOGIN_PATH, SIGNUP_PATH, REFRESH_PATH}
_ISSUING_ENDPOINTS = {LOGIN_PATH, SIGNUP_PATH}
_COOKIE_ENDPOINTS = {REFRESH_PATH, LOGOUT_PATH}

CSRF_HEADER_VALUE = "rumor-zero"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# A refresh answered with one of these leaves the browser nothing to keep.
REJECTED_REFRESH = {400, 401, 410}
TURNSTILE_PARAM = "turnstile_token"
TURNSTILE_FAILED = "The bot check didn't pass. Try it again."
TURNSTILE_UNAVAILABLE = "We couldn't run the bot check. Try again in a minute."


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
        if request.method in SAFE_METHODS:
            return None
        if not self._same_site(request):
            return error_response(403, "csrf_failed", "Reload the page and try again.")
        if path in _TOKEN_ENDPOINTS:
            request.META.pop("HTTP_AUTHORIZATION", None)
            request.META.pop("HTTP_X_SESSION_TOKEN", None)
        if path in _COOKIE_ENDPOINTS:
            copies = cookies.count_cookie(
                request.META.get("HTTP_COOKIE", ""), cookies.REFRESH_COOKIE
            )
            if copies > 1:
                return error_response(400, "invalid_cookie", "Log in again.")
        if path == SIGNUP_PATH:
            return self._check_turnstile(request)
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
        add_never_cache_headers(response)
        return response
