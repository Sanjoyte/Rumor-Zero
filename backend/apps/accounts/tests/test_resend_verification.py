"""POST /api/v1/me/verification-email/: resend with a 60 s cooldown and a daily cap (§7)."""

import pytest
from allauth.account.models import EmailAddress
from django.core import mail

from apps.accounts.tests.conftest import (
    RESEND_URL,
    access_token_for,
    email_links,
    signup,
)
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

COOLDOWN = 60
DAILY_CAP = 10


class Resender:
    """Resends as `user`. The access token is made once, before a test moves the `clock`: PyJWT
    checks `iat` against the real clock, so a token minted at a shifted time would be refused."""

    def __init__(self, api_client, user=None):
        self.api_client = api_client
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {access_token_for(user)}"} if user else {}

    def __call__(self):
        return self.api_client.post(RESEND_URL, **self.headers)


def resend(api_client, user=None):
    return Resender(api_client, user)()


def test_a_resend_sends_the_verification_email_not_the_welcome_one(api_client):
    user = UserFactory()  # no EmailAddress row yet: allauth syncs it

    response = resend(api_client, user)

    assert response.status_code == 204
    assert response.content == b""
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [user.email]
    assert message.subject == "[Rumor Zero] Verify your email"
    assert "Welcome" not in message.body
    assert email_links(message)[0].startswith("http://localhost:3000/verify-email/")
    assert EmailAddress.objects.filter(user=user, email=user.email, verified=False).exists()


def test_the_response_sets_no_cookie_and_is_not_cached(api_client):
    response = resend(api_client, UserFactory())
    assert response.status_code == 204
    assert not response.cookies
    assert "no-store" in response["Cache-Control"]


def test_the_signup_email_blocks_a_resend_for_60_seconds(site_client, api_client, turnstile, clock):
    token = signup(site_client).json()["meta"]["access_token"]
    assert len(mail.outbox) == 1

    def resend_now():
        return api_client.post(RESEND_URL, HTTP_AUTHORIZATION=f"Bearer {token}")

    response = resend_now()
    assert response.status_code == 429
    assert response.json() == {
        "detail": "We sent one recently. Wait a little before asking again.",
        "code": "verification_email_throttled",
    }
    assert "Retry-After" not in response  # the full bucket may be the minute one or the day one
    assert len(mail.outbox) == 1

    clock["seconds"] = COOLDOWN - 1
    assert resend_now().status_code == 429

    clock["seconds"] = COOLDOWN + 1
    assert resend_now().status_code == 204
    assert len(mail.outbox) == 2


def test_the_11th_resend_in_a_day_is_refused(api_client, clock):
    resend_now = Resender(api_client, UserFactory())
    for number in range(DAILY_CAP):
        clock["seconds"] = number * (COOLDOWN + 1)
        assert resend_now().status_code == 204, number
    assert len(mail.outbox) == DAILY_CAP

    clock["seconds"] = DAILY_CAP * (COOLDOWN + 1)  # well past the cooldown, still the same day
    response = resend_now()
    assert response.status_code == 429
    assert response.json()["code"] == "verification_email_throttled"
    assert len(mail.outbox) == DAILY_CAP

    clock["seconds"] = 86400 + 1  # the first resend left the window
    assert resend_now().status_code == 204


def test_a_throttled_attempt_does_not_use_up_the_daily_cap(api_client, clock):
    resend_now = Resender(api_client, UserFactory())
    assert resend_now().status_code == 204
    for _ in range(25):  # all inside the cooldown
        assert resend_now().status_code == 429
    for number in range(1, DAILY_CAP):
        clock["seconds"] = number * (COOLDOWN + 1)
        assert resend_now().status_code == 204, number


def test_the_cap_is_per_address(api_client, clock):
    first, second = Resender(api_client, UserFactory()), Resender(api_client, UserFactory())
    for number in range(DAILY_CAP):
        clock["seconds"] = number * (COOLDOWN + 1)
        assert first().status_code == 204
    assert first().status_code == 429
    assert second().status_code == 204


def test_a_verified_user_gets_409_and_no_email(api_client):
    user = UserFactory(is_email_verified=True)
    response = resend(api_client, user)
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Your email is already verified.",
        "code": "already_verified",
    }
    assert mail.outbox == []


def test_a_verified_address_with_the_flag_off_repairs_the_flag(api_client):
    user = UserFactory()
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    assert user.is_email_verified is False

    response = resend(api_client, user)

    assert response.status_code == 409
    assert response.json()["code"] == "already_verified"
    assert mail.outbox == []
    user.refresh_from_db()
    assert user.is_email_verified is True


def test_anonymous_gets_401(api_client):
    response = resend(api_client)
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"
    assert mail.outbox == []


def test_a_garbage_bearer_gets_401(api_client):
    response = api_client.post(RESEND_URL, HTTP_AUTHORIZATION="Bearer not.a.token")
    assert response.status_code == 401


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_only_post_is_allowed(api_client, method):
    user = UserFactory()
    response = getattr(api_client, method)(
        RESEND_URL, HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}"
    )
    assert response.status_code == 405
    assert mail.outbox == []


def test_a_provider_failure_still_answers_204(api_client, settings):
    """The adapter logs a failed send and swallows it, as at sign-up (a documented follow-up)."""
    settings.EMAIL_BACKEND = "apps.accounts.tests.test_resend_verification.FailingBackend"
    assert resend(api_client, UserFactory()).status_code == 204


class FailingBackend:
    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise OSError("provider unreachable")
