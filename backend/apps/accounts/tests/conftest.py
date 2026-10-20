"""Helpers for the auth API tests: a same-site client, a fake Turnstile and token helpers."""

import datetime
import json
import re
import threading
import time
import uuid
from urllib.parse import unquote

import jwt
import pytest
import requests
from allauth.headless.tokens.strategies.jwt import internal
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.contrib.sessions.backends.db import SessionStore
from django.db import connection
from django.test import Client

from apps.accounts import middleware
from apps.accounts.tests.factories import DEFAULT_PASSWORD
from apps.accounts.turnstile import TurnstileResult

# The root conftest fixes settings.FRONTEND_ORIGIN to this value.
TEST_FRONTEND_ORIGIN = "http://localhost:3000"
# Likewise the Google client ID the root conftest configures.
TEST_GOOGLE_CLIENT_ID = "rz-test-client.apps.googleusercontent.com"
LOGIN_URL = middleware.LOGIN_PATH
SIGNUP_URL = middleware.SIGNUP_PATH
REFRESH_URL = middleware.REFRESH_PATH
LOGOUT_URL = middleware.LOGOUT_PATH
VERIFY_URL = middleware.VERIFY_EMAIL_PATH
PASSWORD_REQUEST_URL = middleware.PASSWORD_REQUEST_PATH
PASSWORD_RESET_URL = middleware.PASSWORD_RESET_PATH
PROVIDER_TOKEN_URL = middleware.PROVIDER_TOKEN_PATH
RESEND_URL = "/api/v1/me/verification-email/"
SITE_HEADERS = {"Origin": TEST_FRONTEND_ORIGIN, "X-Requested-With": "rumor-zero"}
DUMMY_TURNSTILE_TOKEN = "XXXX.DUMMY.TOKEN.XXXX"
STRONG_PASSWORD = "correct-horse-battery-staple-42"


class FakeTurnstile:
    """Stands in for verify_turnstile: records each call and returns `result`."""

    def __init__(self):
        self.result = TurnstileResult.OK
        self.calls = []

    def __call__(self, token, remote_ip):
        self.calls.append((token, remote_ip))
        return self.result


@pytest.fixture
def turnstile(monkeypatch):
    fake = FakeTurnstile()
    monkeypatch.setattr("apps.accounts.middleware.verify_turnstile", fake)
    return fake


@pytest.fixture
def clock(monkeypatch):
    """Moves time.time() forward (`clock["seconds"] = 61`).

    allauth's rate limits and Django's signed keys read time.time(). PyJWT's own expiry check uses
    datetime and is unaffected.
    """
    real = time.time
    offset = {"seconds": 0}
    monkeypatch.setattr(time, "time", lambda: real() + offset["seconds"])
    return offset


@pytest.fixture
def site_client():
    """A browser on the frontend origin, as the relay forwards it."""
    return Client(headers=SITE_HEADERS)


def post_json(client, url, data=None, **extra):
    return client.post(url, data=json.dumps(data or {}), content_type="application/json", **extra)


def signup(client, *, email="ada@example.test", username="ada", password=STRONG_PASSWORD, **extra):
    data = {
        "email": email,
        "username": username,
        "password": password,
        "turnstile_token": DUMMY_TURNSTILE_TOKEN,
    }
    return post_json(client, SIGNUP_URL, data, **extra)


def login(client, email, password=DEFAULT_PASSWORD, **extra):
    return post_json(client, LOGIN_URL, {"email": email, "password": password}, **extra)


def sign_in(user, password=DEFAULT_PASSWORD):
    """A browser (own cookies) logged in for real, with its own token session: (client, token)."""
    browser = Client(headers=SITE_HEADERS)
    response = login(browser, user.email, password)
    assert response.status_code == 200
    return browser, response.json()["meta"]["access_token"]


def refresh(client, **extra):
    return post_json(client, REFRESH_URL, **extra)


def refresh_cookie(client):
    morsel = client.cookies.get("rz_refresh")
    return morsel.value if morsel else ""


def use_refresh_cookie(client, token):
    client.cookies["rz_refresh"] = token


def access_token_for(user):
    """A valid access token without going through login (they are validated statelessly)."""
    session = SessionStore()
    session.create()
    return internal.create_access_token(user, session, {})


def walk_strings(value):
    """Every key and string value in a JSON body, however deeply nested."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)
    elif isinstance(value, str):
        yield value


def assert_no_secrets(response, *secrets):
    """No refresh/session token field, and none of `secrets`, anywhere in the body."""
    assert response["Content-Type"].startswith("application/json")
    strings = list(walk_strings(json.loads(response.content)))
    assert "refresh_token" not in strings
    assert "session_token" not in strings
    for secret in secrets:
        if secret:
            assert secret not in response.content.decode()


def email_links(message):
    """Every http(s) URL in an email's plain-text body, in order."""
    return re.findall(r"https?://\S+", message.body)


def key_from_email(message, route):
    """The key in the first `<origin>/<route>/<key>` link of an email, decoded once like Next does.

    allauth percent-encodes the ":" of a verification key as %3A, and the frontend page decodes the
    route parameter before it sends the key to the API.
    """
    link = next(url for url in email_links(message) if f"/{route}/" in url)
    return unquote(link.split(f"/{route}/", 1)[1])


# ---------- Google ----------


def _make_google_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "rz-test-google")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    return key, cert.public_bytes(serialization.Encoding.PEM).decode()


_KEYS = {}


def google_key(name="real"):
    """RSA keys and certificates are slow to make, so each is made once per test run."""
    if name not in _KEYS:
        _KEYS[name] = _make_google_key()
    return _KEYS[name]


class FakeCertsSession:
    """Stands in for allauth's requests session: serves Google's `{kid: certificate}` document."""

    def __init__(self, fake):
        self.fake = fake

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, **kwargs):
        self.fake.fetches += 1
        if self.fake.fetch_error:
            raise requests.ConnectionError("no network in tests")
        return self

    def raise_for_status(self):
        return None

    def json(self):
        return {self.fake.kid: google_key()[1]}


class FakeGoogle:
    """Mints real RS256 ID tokens that allauth verifies unpatched (`aud`, `iss`, `exp`, `iat`,
    signature, `jti` replay); only the fetch of Google's certificates is faked."""

    kid = "rz-test-kid"

    def __init__(self):
        self.fetch_error = False
        self.fetches = 0
        self.counter = 0

    def claims(self, **overrides):
        self.counter += 1
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": TEST_GOOGLE_CLIENT_ID,
            "sub": f"google-sub-{self.counter}",
            "email": f"person{self.counter}@gmail.com",
            "email_verified": True,
            "given_name": "Ada",
            "family_name": "Lovelace",
            "name": "Ada Lovelace",
            "picture": "https://example.test/ada.png",
            "iat": now,
            "exp": now + 3600,
            "jti": uuid.uuid4().hex,
        }
        claims.update(overrides)
        return {key: value for key, value in claims.items() if value is not None}

    def token(self, *, key="real", algorithm="RS256", kid=kid, **claims):
        """A signed ID token. `key="other"` forges one; `kid=None` leaves the header's kid out."""
        headers = {"kid": kid} if kid else {}
        secret = google_key(key)[0] if algorithm == "RS256" else "x" * 40
        if algorithm == "none":
            secret = None
        return jwt.encode(self.claims(**claims), secret, algorithm=algorithm, headers=headers)

    def login(self, client, id_token=None, *, client_id=TEST_GOOGLE_CLIENT_ID, **claims):
        """POST the sign-in the way the frontend does."""
        if id_token is None:
            id_token = self.token(**claims)
        body = {
            "provider": "google",
            "process": "login",
            "token": {"client_id": client_id, "id_token": id_token},
        }
        return post_json(client, PROVIDER_TOKEN_URL, body)


@pytest.fixture
def google(monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(
        DefaultSocialAccountAdapter, "get_requests_session", lambda self: FakeCertsSession(fake)
    )
    return fake


def run_together(*tasks):
    barrier = threading.Barrier(len(tasks))
    results = [None] * len(tasks)
    errors = []

    def runner(index, task):
        try:
            barrier.wait()
            results[index] = task()
        except Exception as exc:  # collected and asserted on below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=runner, args=item) for item in enumerate(tasks)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert errors == []
    return results
