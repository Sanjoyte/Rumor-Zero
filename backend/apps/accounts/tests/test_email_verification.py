"""Email verification: link → POST auth/email/verify → is_email_verified (ARCHITECTURE §7)."""

import json

import pytest
from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from django.core import mail
from django.test import Client

from apps.accounts.models import User
from apps.accounts.tests.conftest import (
    SITE_HEADERS,
    VERIFY_URL,
    access_token_for,
    assert_no_secrets,
    email_links,
    key_from_email,
    post_json,
    signup,
)
from apps.accounts.tests.factories import UserFactory
from apps.accounts.tests.test_permissions import call as call_verified_only_view

pytestmark = pytest.mark.django_db

DAY = 86400


def body(response):
    return json.loads(response.content)


def sign_up_and_read_key(client, **kwargs):
    """Sign up (Turnstile mocked by the caller) and return the key from the email's link."""
    assert signup(client, **kwargs).status_code == 200
    return key_from_email(mail.outbox[-1], "verify-email")


def verify(client, key, **extra):
    return post_json(client, VERIFY_URL, {"key": key}, **extra)


@pytest.fixture
def key(site_client, turnstile):
    return sign_up_and_read_key(site_client)


def test_the_signup_email_link_verifies_the_account(site_client, turnstile):
    assert signup(site_client).status_code == 200
    link = email_links(mail.outbox[0])[0]
    # The ":" separators arrive percent-encoded; the page decodes the route parameter once.
    assert link.startswith("http://localhost:3000/verify-email/")
    assert "%3A" in link
    key = key_from_email(mail.outbox[0], "verify-email")
    assert key.count(":") == 2

    user = User.objects.get(email="ada@example.test")
    assert user.is_email_verified is False
    assert call_verified_only_view(user).status_code == 403

    response = verify(site_client, key)

    assert response.status_code == 200
    assert body(response) == {"status": 200}
    assert response["Content-Type"] == "application/json"
    assert "no-store" in response["Cache-Control"]
    assert "rz_refresh" not in response.cookies  # a link never logs anyone in
    assert_no_secrets(response)
    user.refresh_from_db()
    assert user.is_email_verified is True
    assert EmailAddress.objects.get(user=user).verified is True
    assert call_verified_only_view(user).status_code == 201


def test_the_link_works_from_a_browser_that_is_not_logged_in(key):
    stranger = Client(headers=SITE_HEADERS)  # no cookies at all
    assert verify(stranger, key).status_code == 200
    assert User.objects.get(email="ada@example.test").is_email_verified is True


def test_a_used_link_is_refused(site_client, key):
    assert verify(site_client, key).status_code == 200
    response = verify(site_client, key)
    assert response.status_code == 400
    error = body(response)["errors"][0]
    assert (error["code"], error["param"]) == ("invalid_or_expired_key", "key")
    assert User.objects.get(email="ada@example.test").is_email_verified is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda key: key[:-1] + ("a" if key[-1] != "a" else "b"),  # a changed signature
        lambda key: "x" + key,  # a changed payload
        lambda key: key.rsplit(":", 1)[0],  # no signature
        lambda key: "not-a-key",
        lambda key: "",
    ],
    ids=["signature", "payload", "unsigned", "garbage", "empty"],
)
def test_a_forged_key_is_refused(site_client, key, mutate):
    response = verify(site_client, mutate(key))
    assert response.status_code == 400
    assert body(response)["errors"][0]["code"] in ("invalid_or_expired_key", "required")
    assert User.objects.get(email="ada@example.test").is_email_verified is False


def test_a_missing_key_is_a_400(site_client):
    response = post_json(site_client, VERIFY_URL, {})
    assert response.status_code == 400


def test_a_link_lasts_exactly_24_hours(site_client, turnstile, clock):
    key = sign_up_and_read_key(site_client)
    clock["seconds"] = DAY + 1  # signed 86 401 s ago
    response = verify(site_client, key)
    assert response.status_code == 400
    assert body(response)["errors"][0]["code"] == "invalid_or_expired_key"
    assert User.objects.get(email="ada@example.test").is_email_verified is False

    clock["seconds"] = DAY - 1  # signed 86 399 s ago
    assert verify(site_client, key).status_code == 200
    assert User.objects.get(email="ada@example.test").is_email_verified is True


def test_an_authorization_header_is_ignored(site_client, key):
    """A Bearer for another user (or a stale one) must neither fail the call nor change who is
    verified: the link belongs to whoever it was sent to."""
    other = UserFactory(email="other@example.test")
    response = verify(site_client, key, HTTP_AUTHORIZATION=f"Bearer {access_token_for(other)}")
    assert response.status_code == 200
    other.refresh_from_db()
    assert other.is_email_verified is False
    assert User.objects.get(email="ada@example.test").is_email_verified is True


@pytest.mark.parametrize(
    "extra",
    [
        {"HTTP_AUTHORIZATION": "Bearer not.a.token"},
        {"HTTP_X_SESSION_TOKEN": "no-such-session"},
    ],
    ids=["stale-bearer", "session-token"],
)
def test_stale_credentials_do_not_break_verification(site_client, key, extra):
    # Not allauth's 410 (unknown session) or 401.
    assert verify(site_client, key, **extra).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [{}, {"Origin": "https://evil.example", "X-Requested-With": "rumor-zero"}],
    ids=["no-headers", "other-origin"],
)
def test_verification_needs_the_same_site_headers(key, headers):
    response = verify(Client(headers=headers), key)
    assert response.status_code == 403
    assert body(response)["errors"][0]["code"] == "csrf_failed"
    assert User.objects.get(email="ada@example.test").is_email_verified is False


def test_the_receiver_ignores_an_address_that_is_not_the_users_email():
    user = UserFactory(email="current@example.test")
    old_address = EmailAddress(
        user=user, email="previous@example.test", verified=True, primary=False
    )
    email_confirmed.send(sender=EmailAddress, request=None, email_address=old_address)
    user.refresh_from_db()
    assert user.is_email_verified is False


def test_the_receiver_matches_the_email_whatever_its_case():
    user = UserFactory(email="mixed@example.test")
    address = EmailAddress(user=user, email="Mixed@Example.test", verified=True, primary=True)
    email_confirmed.send(sender=EmailAddress, request=None, email_address=address)
    user.refresh_from_db()
    assert user.is_email_verified is True
