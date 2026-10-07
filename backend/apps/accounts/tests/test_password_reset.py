"""Password reset: request (no enumeration, capped), key check, reset that logs in (§7)."""

import json
from datetime import datetime, timedelta

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import Client

from apps.accounts.tests.conftest import (
    PASSWORD_REQUEST_URL,
    PASSWORD_RESET_URL,
    REFRESH_URL,
    SITE_HEADERS,
    access_token_for,
    assert_no_secrets,
    key_from_email,
    login,
    post_json,
    refresh_cookie,
    use_refresh_cookie,
)
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.accounts.tokens import session_key_of

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "a-brand-new-passphrase-77"
DAY = 86400
RELAY_SECRET = "test-relay-secret"


def body(response):
    return json.loads(response.content)


def first_error(response):
    return body(response)["errors"][0]


def request_reset(client, email):
    return post_json(client, PASSWORD_REQUEST_URL, {"email": email})


def reset(client, key, password=NEW_PASSWORD, **extra):
    return post_json(client, PASSWORD_RESET_URL, {"key": key, "password": password}, **extra)


def check_key(client, key, **extra):
    return client.get(PASSWORD_RESET_URL, headers={"X-Password-Reset-Key": key}, **extra)


def reset_key_for(client, user):
    mail.outbox.clear()
    assert request_reset(client, user.email).status_code == 200
    return key_from_email(mail.outbox[-1], "reset-password")


def from_ip(ip, settings):
    """A browser at `ip`, behind the relay (which adds the secret and the client IP)."""
    settings.PROXY_SHARED_SECRET = RELAY_SECRET
    return Client(headers={**SITE_HEADERS, "X-RZ-Proxy-Secret": RELAY_SECRET, "X-RZ-Client-IP": ip})


# ---------- request: the same answer for every address ----------


def test_existing_unknown_and_inactive_addresses_get_identical_answers(site_client):
    existing = UserFactory(email="exists@example.test")
    inactive = UserFactory(email="inactive@example.test", is_active=False)
    addresses = [existing.email, "nobody@example.test", inactive.email]

    responses = [request_reset(site_client, address) for address in addresses]

    assert {r.status_code for r in responses} == {200}
    assert len({r.content for r in responses}) == 1, [r.content for r in responses]
    assert body(responses[0]) == {"status": 200}
    for header in ("Content-Type", "Cache-Control", "Content-Length"):
        assert len({r[header] for r in responses}) == 1, header
    assert all(not r.cookies for r in responses)
    # Only the real, active account gets an email; the others get nothing at all.
    assert [m.to for m in mail.outbox] == [[existing.email]]


def test_an_unverified_address_gets_the_email_too(site_client):
    user = UserFactory(is_email_verified=False)
    assert request_reset(site_client, user.email).status_code == 200
    assert [m.to for m in mail.outbox] == [[user.email]]


def test_the_address_case_and_spaces_do_not_matter(site_client):
    user = UserFactory(email="mixed@example.test")
    assert request_reset(site_client, "  Mixed@Example.TEST ").status_code == 200
    assert [m.to for m in mail.outbox] == [[user.email]]


@pytest.mark.parametrize("email", ["not-an-email", "", "   ", "a@", None, 42], ids=repr)
def test_a_malformed_email_is_a_400_whoever_asks(site_client, email):
    UserFactory(email="exists@example.test")
    data = {} if email is None else {"email": email}
    response = post_json(site_client, PASSWORD_REQUEST_URL, data)
    assert response.status_code == 400
    assert first_error(response)["param"] == "email"
    assert mail.outbox == []


def test_a_non_object_body_is_a_400(site_client):
    response = site_client.post(PASSWORD_REQUEST_URL, data="[]", content_type="application/json")
    assert response.status_code == 400


def test_the_reset_email_links_to_the_frontend_with_a_plain_key(site_client):
    user = UserFactory()
    key = reset_key_for(site_client, user)
    assert mail.outbox[-1].subject == "[Rumor Zero] Reset your password"
    parts = key.split("-")
    assert len(parts) == 3  # <uuid hex>-<timestamp>-<hash>
    assert check_key(site_client, key).status_code == 200


# ---------- request: rate limits ----------


def test_the_6th_request_in_a_minute_for_one_address_is_refused(site_client):
    UserFactory(email="busy@example.test")
    for _ in range(5):
        assert request_reset(site_client, "busy@example.test").status_code == 200
    response = request_reset(site_client, "busy@example.test")
    assert response.status_code == 429
    assert body(response) == {"status": 429}
    assert request_reset(site_client, "other@example.test").status_code == 200


def test_the_11th_request_in_a_day_for_one_address_is_refused(site_client, clock):
    UserFactory(email="busy@example.test")
    for minute in range(2):
        clock["seconds"] = minute * 61
        for _ in range(5):
            assert request_reset(site_client, "busy@example.test").status_code == 200
    assert len(mail.outbox) == 10

    clock["seconds"] = 3 * 61  # the minute limit has cleared; the daily one hasn't
    response = request_reset(site_client, "busy@example.test")
    assert response.status_code == 429
    assert body(response) == {"status": 429}
    assert len(mail.outbox) == 10
    # Same answer for an address that doesn't exist: the cap leaks nothing either.
    for _ in range(5):
        request_reset(site_client, "ghost@example.test")
    clock["seconds"] = 5 * 61
    assert request_reset(site_client, "ghost@example.test").status_code == 200

    clock["seconds"] = DAY + 1  # the first requests have left the window
    assert request_reset(site_client, "busy@example.test").status_code == 200


def test_the_51st_request_in_a_day_from_one_ip_is_refused(site_client, clock):
    sent = 0
    for batch, size in enumerate([15, 15, 15, 5]):  # the per-minute IP limit is 20
        clock["seconds"] = batch * 61
        for _ in range(size):
            sent += 1
            assert request_reset(site_client, f"user{sent}@example.test").status_code == 200
    assert sent == 50

    clock["seconds"] = 4 * 61
    assert request_reset(site_client, "user51@example.test").status_code == 429

    clock["seconds"] = DAY + 1
    assert request_reset(site_client, "user51@example.test").status_code == 200


def test_another_ip_has_its_own_daily_cap(settings, clock):
    first = from_ip("203.0.113.10", settings)
    second = from_ip("198.51.100.20", settings)
    sent = 0
    for batch, size in enumerate([15, 15, 15, 5]):
        clock["seconds"] = batch * 61
        for _ in range(size):
            sent += 1
            assert request_reset(first, f"user{sent}@example.test").status_code == 200
    clock["seconds"] = 4 * 61
    assert request_reset(first, "user51@example.test").status_code == 429
    assert request_reset(second, "user51@example.test").status_code == 200


def test_a_400_does_not_count_towards_any_limit(site_client):
    for _ in range(60):  # more than the 50 daily and 20 per-minute per-IP limits
        assert request_reset(site_client, "bad").status_code == 400
    user = UserFactory()
    for _ in range(5):
        assert request_reset(site_client, user.email).status_code == 200
    assert len(mail.outbox) == 5


def test_a_429_does_not_count_either(site_client, clock):
    UserFactory(email="busy@example.test")
    for _ in range(5):
        assert request_reset(site_client, "busy@example.test").status_code == 200
    for _ in range(30):
        assert request_reset(site_client, "busy@example.test").status_code == 429
    clock["seconds"] = 61
    for _ in range(5):  # still 10 per day: the refused attempts took nothing from the cap
        assert request_reset(site_client, "busy@example.test").status_code == 200
    assert request_reset(site_client, "busy@example.test").status_code == 429


# ---------- the key pre-check ----------


def test_a_good_key_passes_the_check(site_client):
    user = UserFactory()
    key = reset_key_for(site_client, user)
    response = check_key(site_client, key)
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert not response.cookies
    assert_no_secrets(response)
    assert body(response)["status"] == 200


@pytest.mark.parametrize("key", ["", "garbage", "abc-def-ghi", "0" * 32 + "-xxxx-yyyy"], ids=repr)
def test_a_bad_key_fails_the_check(site_client, key):
    response = check_key(site_client, key)
    assert response.status_code == 400
    # An empty header is "required"; the reset page never sends one (it checks the key's format).
    expected = "required" if key == "" else "invalid_password_reset"
    assert first_error(response)["code"] == expected


def test_the_check_ignores_a_stale_authorization_header(site_client):
    user = UserFactory()
    key = reset_key_for(site_client, user)
    for extra in (
        {"HTTP_AUTHORIZATION": "Bearer not.a.token"},
        {"HTTP_AUTHORIZATION": f"Bearer {access_token_for(UserFactory())}"},
        {"HTTP_X_SESSION_TOKEN": "no-such-session"},
    ):
        assert check_key(site_client, key, **extra).status_code == 200


def test_the_check_does_not_use_the_key_up(site_client):
    key = reset_key_for(site_client, UserFactory())
    assert check_key(site_client, key).status_code == 200
    assert check_key(site_client, key).status_code == 200
    assert reset(site_client, key).status_code == 200


# ---------- reset ----------


def test_a_reset_logs_the_user_in(site_client):
    user = UserFactory()
    key = reset_key_for(site_client, user)

    response = reset(site_client, key)

    assert response.status_code == 200
    data = body(response)
    assert data["data"]["user"]["email"] == user.email
    assert data["meta"]["access_token"]
    assert_no_secrets(response)
    assert refresh_cookie(site_client)
    assert response.cookies["rz_refresh"]["httponly"]
    assert response.cookies["rz_session"].value == "1"
    assert "no-store" in response["Cache-Control"]

    assert login(Client(headers=SITE_HEADERS), user.email, NEW_PASSWORD).status_code == 200
    assert login(Client(headers=SITE_HEADERS), user.email, DEFAULT_PASSWORD).status_code == 400
    # The cookie from the reset is a working refresh token.
    assert post_json(site_client, REFRESH_URL).status_code == 200


def test_another_browsers_refresh_token_stops_working(site_client):
    user = UserFactory()
    other_browser = Client(headers=SITE_HEADERS)
    assert login(other_browser, user.email).status_code == 200
    assert post_json(other_browser, REFRESH_URL).status_code == 200  # alive before the reset

    key = reset_key_for(site_client, user)
    assert reset(site_client, key).status_code == 200

    response = post_json(other_browser, REFRESH_URL)
    assert response.status_code == 400
    assert response.cookies["rz_refresh"]["max-age"] == 0


def test_this_browsers_previous_session_is_deleted(site_client):
    user = UserFactory()
    assert login(site_client, user.email).status_code == 200
    old_token = refresh_cookie(site_client)
    old_session = session_key_of(old_token)
    assert Session.objects.filter(session_key=old_session).exists()

    key = reset_key_for(site_client, user)
    assert reset(site_client, key).status_code == 200

    assert not Session.objects.filter(session_key=old_session).exists()
    new_token = refresh_cookie(site_client)
    assert new_token != old_token
    assert Session.objects.filter(session_key=session_key_of(new_token)).exists()
    # The old token is dead even if someone kept a copy.
    use_refresh_cookie(site_client, old_token)
    assert post_json(site_client, REFRESH_URL).status_code == 400


def test_a_used_key_is_refused(site_client):
    key = reset_key_for(site_client, UserFactory())
    assert reset(site_client, key).status_code == 200
    response = reset(Client(headers=SITE_HEADERS), key, password="another-passphrase-99")
    assert response.status_code == 400
    assert (first_error(response)["code"], first_error(response)["param"]) == (
        "invalid_password_reset",
        "key",
    )
    assert check_key(site_client, key).status_code == 400


def test_two_requests_give_two_keys_and_the_first_one_used_kills_the_other(site_client):
    """Both links work until one is used: the key covers the password, so it kills the other."""
    user = UserFactory()
    first = reset_key_for(site_client, user)
    second = reset_key_for(site_client, user)
    assert reset(site_client, first).status_code == 200
    assert reset(Client(headers=SITE_HEADERS), second).status_code == 400


@pytest.fixture
def reset_clock(monkeypatch):
    """Moves PasswordResetTokenGenerator's clock (a naive `datetime.now()`)."""
    offset = {"seconds": 0}
    monkeypatch.setattr(
        PasswordResetTokenGenerator,
        "_now",
        lambda self: datetime.now() + timedelta(seconds=offset["seconds"]),
    )
    return offset


def test_a_reset_link_lasts_24_hours(site_client, reset_clock):
    user = UserFactory()
    key = reset_key_for(site_client, user)

    reset_clock["seconds"] = DAY + 1  # 86 401 s later
    response = reset(site_client, key)
    assert response.status_code == 400
    assert first_error(response)["code"] == "invalid_password_reset"
    assert check_key(site_client, key).status_code == 400

    reset_clock["seconds"] = DAY - 1  # 86 399 s later
    assert check_key(site_client, key).status_code == 200
    assert reset(site_client, key).status_code == 200


def test_a_weak_password_names_the_password_field(site_client):
    key = reset_key_for(site_client, UserFactory())
    for weak in ("short", "12345678", "password", ""):
        response = reset(site_client, key, password=weak)
        assert response.status_code == 400, weak
        errors = body(response)["errors"]
        assert errors and all(error["param"] == "password" for error in errors), weak
    # The key survived the refused attempts.
    assert reset(site_client, key).status_code == 200


def test_a_bad_key_names_the_key_field(site_client):
    response = reset(site_client, "garbage")
    assert response.status_code == 400
    assert first_error(response)["param"] == "key"
    assert not response.cookies


def test_the_password_is_not_changed_by_a_refused_reset(site_client):
    user = UserFactory()
    reset(site_client, "garbage")
    assert login(Client(headers=SITE_HEADERS), user.email).status_code == 200


def test_reset_ignores_authorization_headers(site_client):
    """The key decides who is reset, whoever the request says it is."""
    victim, bystander = UserFactory(), UserFactory()
    key = reset_key_for(site_client, victim)
    response = reset(
        site_client,
        key,
        HTTP_AUTHORIZATION=f"Bearer {access_token_for(bystander)}",
        HTTP_X_SESSION_TOKEN="no-such-session",
    )
    assert response.status_code == 200
    assert body(response)["data"]["user"]["email"] == victim.email
    assert login(Client(headers=SITE_HEADERS), victim.email, NEW_PASSWORD).status_code == 200
    assert login(Client(headers=SITE_HEADERS), bystander.email).status_code == 200


def test_reset_is_rate_limited_per_ip(site_client):
    for _ in range(20):
        assert reset(site_client, "garbage").status_code == 400
    response = reset(site_client, "garbage")
    assert response.status_code == 429


def test_reset_needs_the_same_site_headers():
    key = reset_key_for(Client(headers=SITE_HEADERS), UserFactory())
    response = reset(Client(), key)
    assert response.status_code == 403
    assert first_error(response)["code"] == "csrf_failed"
