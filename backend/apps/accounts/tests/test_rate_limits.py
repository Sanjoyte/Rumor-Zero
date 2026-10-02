"""allauth's rate limits on the real client IP, sent the way the relay sends it (§3)."""

import json

import pytest
from django.test import Client

from apps.accounts.tests.conftest import SITE_HEADERS, login, signup
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.accounts.turnstile import TurnstileResult

pytestmark = pytest.mark.django_db

RELAY_SECRET = "test-relay-secret"


@pytest.fixture(autouse=True)
def _relay_secret(settings):
    settings.PROXY_SHARED_SECRET = RELAY_SECRET


def from_ip(ip):
    """A browser at `ip`, behind the relay (which adds the secret and the client IP)."""
    return Client(headers={**SITE_HEADERS, "X-RZ-Proxy-Secret": RELAY_SECRET, "X-RZ-Client-IP": ip})


def codes(response):
    return [error["code"] for error in json.loads(response.content).get("errors", [])]


def test_ten_failures_from_one_ip_lock_that_ip_but_not_another():
    client_a = from_ip("203.0.113.10")
    for n in range(10):
        response = login(client_a, f"nobody{n}@example.test", "wrong-password")
        assert codes(response) == ["email_password_mismatch"]

    # The 11th attempt from IP A is refused before the password is checked: even a right one.
    user = UserFactory()
    response = login(client_a, user.email, DEFAULT_PASSWORD)
    assert response.status_code == 400
    assert codes(response) == ["too_many_login_attempts"]
    assert "rz_refresh" not in response.cookies

    # IP B is unaffected.
    response = login(from_ip("198.51.100.20"), "fresh@example.test", "wrong-password")
    assert codes(response) == ["email_password_mismatch"]
    assert login(from_ip("198.51.100.20"), user.email).status_code == 200


def test_five_failures_on_one_account_lock_it_from_every_ip():
    user = UserFactory()
    for n in range(5):
        response = login(from_ip(f"203.0.113.{n + 1}"), user.email, "wrong-password")
        assert codes(response) == ["email_password_mismatch"]

    response = login(from_ip("198.51.100.99"), user.email, DEFAULT_PASSWORD)
    assert codes(response) == ["too_many_login_attempts"]
    # The per-account key is the email, whatever its case.
    response = login(from_ip("198.51.100.98"), user.email.upper(), DEFAULT_PASSWORD)
    assert codes(response) == ["too_many_login_attempts"]


def test_a_successful_login_does_not_use_up_the_failure_budget():
    user = UserFactory()
    client = from_ip("203.0.113.30")
    for _ in range(12):
        assert login(client, user.email).status_code == 200


def test_without_the_relay_secret_the_client_ip_header_is_ignored():
    spoofed = Client(headers={**SITE_HEADERS, "X-RZ-Client-IP": "203.0.113.40"})
    for n in range(10):
        login(spoofed, f"nobody{n}@example.test", "wrong-password")
    # The attempts were counted against the real peer address, not the spoofed one.
    response = login(from_ip("127.0.0.1"), "someone@example.test", "wrong-password")
    assert codes(response) == ["too_many_login_attempts"]
    response = login(from_ip("203.0.113.40"), "someone@example.test", "wrong-password")
    assert codes(response) == ["email_password_mismatch"]


def test_twenty_signups_per_minute_per_ip(turnstile):
    client = from_ip("203.0.113.50")
    for n in range(20):
        response = signup(client, email=f"user{n}@example.test", username=f"user_{n}")
        assert response.status_code == 200, response.content
        client.cookies.clear()

    response = signup(client, email="one-more@example.test", username="one_more")
    assert response.status_code == 429
    assert len(turnstile.calls) == 20  # Cloudflare isn't asked once the limit is reached

    other = signup(from_ip("198.51.100.50"), email="elsewhere@example.test", username="elsewhere")
    assert other.status_code == 200


def test_failed_bot_checks_count_toward_the_signup_limit(turnstile):
    client = from_ip("203.0.113.60")
    turnstile.result = TurnstileResult.FAILED
    for n in range(20):
        assert signup(client, email=f"bot{n}@example.test", username=f"bot_{n}").status_code == 400

    turnstile.result = TurnstileResult.OK
    response = signup(client, email="real@example.test", username="real_person")
    assert response.status_code == 429
    assert len(turnstile.calls) == 20
