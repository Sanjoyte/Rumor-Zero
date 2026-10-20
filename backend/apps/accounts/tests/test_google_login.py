"""`POST auth/provider/token`: "Continue with Google" (ARCHITECTURE §7, Part 3).

The `google` fixture mints real RS256 ID tokens and serves the signing certificate, so allauth's own
`aud`, `iss`, `exp`, `iat`, signature and `jti` checks run unpatched.
"""

import json
import logging

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core import mail
from django.test import Client

from apps.accounts.models import Role, User
from apps.accounts.tests.conftest import (
    PROVIDER_TOKEN_URL,
    SITE_HEADERS,
    TEST_GOOGLE_CLIENT_ID,
    access_token_for,
    assert_no_secrets,
    login,
    post_json,
    refresh,
    refresh_cookie,
    use_refresh_cookie,
)
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def body(response):
    return json.loads(response.content)


def first_error(response):
    return body(response)["errors"][0]


def verified_address(user, email=None):
    return EmailAddress.objects.create(
        user=user, email=email or user.email, verified=True, primary=True
    )


def assert_no_session(client, response):
    assert response.status_code == 400
    assert "rz_refresh" not in client.cookies
    assert "rz_session" not in client.cookies
    assert "meta" not in body(response)


# ---------- a new Google user ----------


def test_a_new_google_user_is_created_verified_and_logged_in(site_client, google):
    id_token = google.token(email="ada@example.org", given_name="Ada", sub="sub-ada")
    response = google.login(site_client, id_token)

    assert response.status_code == 200
    access = body(response)["meta"]["access_token"]
    assert access != id_token
    assert_no_secrets(response, id_token)  # Google's token is never echoed back
    assert refresh_cookie(site_client)
    assert site_client.cookies["rz_session"].value == "1"
    assert site_client.cookies["rz_refresh"]["httponly"]

    user = User.objects.get(email="ada@example.org")
    assert user.username == "ada"
    assert user.is_email_verified
    assert user.display_name == ""
    assert not user.has_usable_password()
    address = EmailAddress.objects.get(user=user)
    assert (address.email, address.verified, address.primary) == ("ada@example.org", True, True)
    account = SocialAccount.objects.get(user=user)
    assert (account.provider, account.uid) == ("google", "sub-ada")
    # Only the claims we use are stored: no name, picture or locale.
    assert set(account.extra_data) == {"sub", "email", "email_verified"}

    me = site_client.get("/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
    assert me.json()["google_connected"] is True
    assert me.json()["is_email_verified"] is True


def test_a_google_workspace_claim_is_kept(site_client, google):
    response = google.login(site_client, email="ada@corp.example", hd="corp.example")
    assert response.status_code == 200
    assert SocialAccount.objects.get().extra_data["hd"] == "corp.example"


def test_the_username_comes_from_the_first_name_and_is_unique(site_client, google):
    assert google.login(site_client, given_name="Ada").status_code == 200
    second = Client(headers=SITE_HEADERS)
    assert google.login(second, given_name="Ada").status_code == 200
    names = sorted(User.objects.values_list("username", flat=True))
    assert names[0] == "ada"
    assert names[1].startswith("ada_") and len(names[1]) == 8


@pytest.mark.parametrize("given_name", ["李", None, "Admin"])
def test_an_unusable_first_name_gets_a_member_handle(site_client, google, given_name):
    assert google.login(site_client, given_name=given_name).status_code == 200
    assert User.objects.get().username.startswith("member_")


def test_the_email_address_is_never_the_username(site_client, google):
    google.login(site_client, email="john.smith1987@gmail.com", given_name="John")
    assert "smith1987" not in User.objects.get().username


# ---------- linking to an existing account ----------


def test_a_verified_gmail_account_is_the_same_account(site_client, google):
    user = UserFactory(email="ada@gmail.com")
    verified_address(user)
    before = User.objects.count()

    response = google.login(site_client, email="ada@gmail.com", sub="sub-link")

    assert response.status_code == 200
    assert User.objects.count() == before
    account = SocialAccount.objects.get(uid="sub-link")
    assert account.user_id == user.pk
    user.refresh_from_db()
    assert user.is_email_verified
    assert user.check_password(DEFAULT_PASSWORD)  # a verified address keeps its password


def test_an_unverified_account_links_loses_its_password_and_other_sessions(site_client, google):
    user = UserFactory(email="bob@gmail.com")
    old_browser = Client(headers=SITE_HEADERS)
    assert login(old_browser, user.email).status_code == 200
    old_token = refresh_cookie(old_browser)

    response = google.login(site_client, email="bob@gmail.com", sub="sub-bob")

    assert response.status_code == 200
    assert SocialAccount.objects.get(uid="sub-bob").user_id == user.pk
    user.refresh_from_db()
    assert not user.has_usable_password()  # whoever signed up with this address is locked out
    assert user.is_email_verified
    address = EmailAddress.objects.get(user=user)
    assert address.verified and address.primary
    # The old browser's refresh token stops working (the session's auth hash changed).
    stale = Client(headers=SITE_HEADERS)
    use_refresh_cookie(stale, old_token)
    assert refresh(stale).status_code == 400


def test_an_existing_unverified_address_row_is_marked_verified(site_client, google):
    user = UserFactory(email="cy@gmail.com")
    EmailAddress.objects.create(user=user, email="cy@gmail.com", verified=False, primary=True)
    assert google.login(site_client, email="cy@gmail.com").status_code == 200
    assert EmailAddress.objects.get(user=user).verified


def test_a_workspace_address_links(site_client, google):
    user = UserFactory(email="dee@corp.example")
    response = google.login(site_client, email="dee@corp.example", hd="corp.example", sub="s-dee")
    assert response.status_code == 200
    assert SocialAccount.objects.get(uid="s-dee").user_id == user.pk


def test_the_email_match_ignores_case(site_client, google):
    user = UserFactory(email="eve@gmail.com")
    response = google.login(site_client, email="Eve@Gmail.com", sub="s-eve")
    assert response.status_code == 200
    assert SocialAccount.objects.get(uid="s-eve").user_id == user.pk


def test_another_domain_does_not_link_but_may_sign_up_new(site_client, google):
    user = UserFactory(email="fay@example.org")
    response = google.login(site_client, email="fay@example.org", sub="s-fay")

    assert_no_session(site_client, response)
    assert first_error(response)["code"] == "google_link_requires_password"
    assert "param" not in first_error(response)
    assert not SocialAccount.objects.exists()
    user.refresh_from_db()
    assert user.check_password(DEFAULT_PASSWORD)  # no wipe either
    assert User.objects.count() == 1


@pytest.mark.parametrize("kwargs", [{"role": Role.MODERATOR}, {"is_superuser": True}])
def test_staff_are_not_linked_by_email(site_client, google, kwargs):
    staff = UserFactory(email="mod@gmail.com", **kwargs)
    response = google.login(site_client, email="mod@gmail.com")

    assert_no_session(site_client, response)
    assert first_error(response)["code"] == "staff_password_login"
    assert not SocialAccount.objects.exists()
    staff.refresh_from_db()
    assert staff.check_password(DEFAULT_PASSWORD)


def test_staff_who_linked_google_before_can_still_sign_in(site_client, google):
    staff = UserFactory(email="old@gmail.com", role=Role.MODERATOR)
    SocialAccount.objects.create(user=staff, provider="google", uid="s-staff")
    response = google.login(site_client, email="other@example.org", sub="s-staff")
    assert response.status_code == 200
    assert User.objects.count() == 1


def test_an_inactive_account_is_not_linked_or_wiped(site_client, google):
    user = UserFactory(email="gus@gmail.com", is_active=False)
    response = google.login(site_client, email="gus@gmail.com")

    assert_no_session(site_client, response)
    assert first_error(response)["code"] == "account_inactive"
    assert not SocialAccount.objects.exists()
    user.refresh_from_db()
    assert user.check_password(DEFAULT_PASSWORD)


def test_an_inactive_account_with_a_google_link_cannot_sign_in(site_client, google):
    user = UserFactory(is_active=False)
    SocialAccount.objects.create(user=user, provider="google", uid="s-off")
    response = google.login(site_client, sub="s-off")
    assert_no_session(site_client, response)
    assert first_error(response)["code"] == "account_inactive"


def test_a_returning_google_user_signs_in_even_with_a_new_email(site_client, google):
    user = UserFactory()
    SocialAccount.objects.create(user=user, provider="google", uid="s-back")
    response = google.login(site_client, email="moved@example.net", sub="s-back")
    assert response.status_code == 200
    assert User.objects.count() == 1
    user.refresh_from_db()
    assert user.check_password(DEFAULT_PASSWORD)  # nothing about the account changed


# ---------- the Google address must be verified ----------


@pytest.mark.parametrize("claims", [{"email_verified": False}, {"email": None}])
def test_an_unverified_or_missing_google_email_is_refused(site_client, google, claims):
    response = google.login(site_client, **claims)
    assert_no_session(site_client, response)
    assert first_error(response)["code"] == "google_email_unverified"
    assert not User.objects.exists()
    assert not SocialAccount.objects.exists()


def test_an_unverified_google_email_never_matches_an_account(site_client, google):
    user = UserFactory(email="hal@gmail.com")
    response = google.login(site_client, email="hal@gmail.com", email_verified=False)
    assert first_error(response)["code"] == "google_email_unverified"
    user.refresh_from_db()
    assert user.check_password(DEFAULT_PASSWORD)


# ---------- tokens that are not good ----------


def now():
    import time

    return int(time.time())


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "someone-else.apps.googleusercontent.com"},
        {"iss": "https://evil.example"},
        {"iat": 0, "exp": 1},  # expired
        {"iat": now() + 7200, "exp": now() + 9000},  # issued in the future
    ],
)
def test_a_token_that_fails_allauths_claim_checks_is_400(site_client, google, claims):
    response = google.login(site_client, **claims)
    assert_no_session(site_client, response)
    assert first_error(response)["code"] == "invalid_token"
    assert first_error(response)["param"] == "token"
    assert not User.objects.exists()


def test_a_token_signed_with_another_key_is_400(site_client, google):
    response = google.login(site_client, key="other")
    assert_no_session(site_client, response)
    assert first_error(response)["code"] == "invalid_token"


def test_an_unknown_key_id_is_400(site_client, google):
    response = google.login(site_client, kid="not-a-google-key")
    assert_no_session(site_client, response)
    assert first_error(response)["code"] == "invalid_token"


def test_a_replayed_token_is_400(site_client, google):
    token = google.token(email="ivy@example.org")
    assert google.login(site_client, token).status_code == 200
    second = Client(headers=SITE_HEADERS)
    response = google.login(second, token)
    assert_no_session(second, response)
    assert first_error(response)["code"] == "invalid_token"


def test_a_failure_to_fetch_googles_certificates_is_400(site_client, google):
    google.fetch_error = True
    response = google.login(site_client)
    assert_no_session(site_client, response)
    assert first_error(response)["code"] == "invalid_token"
    assert not User.objects.exists()


@pytest.mark.parametrize(
    "token_kwargs",
    [
        {"algorithm": "HS256"},  # allauth would answer a TypeError (500) against Google's RSA key
        {"algorithm": "none"},
        {"kid": None},  # allauth would answer a KeyError (500)
        {"kid": "k" * 201},  # longer than any real key id
    ],
)
def test_forged_headers_are_refused_before_allauth_sees_them(site_client, google, token_kwargs):
    response = google.login(site_client, google.token(**token_kwargs))
    assert_no_session(site_client, response)
    assert first_error(response)["code"] == "invalid_token"
    assert google.fetches == 0  # Google was never asked


# ---------- requests that are not a Google sign-in ----------


def valid_body(google, **token_overrides):
    token = {"client_id": TEST_GOOGLE_CLIENT_ID, "id_token": google.token(), **token_overrides}
    return {"provider": "google", "process": "login", "token": token}


@pytest.mark.parametrize(
    "change",
    [
        {"provider": "github"},
        {"provider": None},
        {"process": "connect"},
        {"process": "redirect"},
        {"process": None},
        {"token": None},
        {"token": "a-string"},
        {"token": ["x"]},
        {"token": {}},
        {"token": {"client_id": TEST_GOOGLE_CLIENT_ID}},
        {"token": {"client_id": TEST_GOOGLE_CLIENT_ID, "id_token": 12}},
        {"token": {"client_id": TEST_GOOGLE_CLIENT_ID, "id_token": ""}},
        {"token": {"client_id": TEST_GOOGLE_CLIENT_ID, "id_token": "x" * 5000}},
        {"token": {"client_id": TEST_GOOGLE_CLIENT_ID, "id_token": "not.a.jwt"}},
        {"token": {"client_id": None, "id_token": "x"}},
    ],
)
def test_a_request_that_is_not_a_google_login_is_400(site_client, google, change):
    data = {**valid_body(google), **change}
    response = post_json(site_client, PROVIDER_TOKEN_URL, data)
    assert_no_session(site_client, response)
    assert first_error(response)["code"] == "invalid_token"
    assert google.fetches == 0


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", "null", ""])
def test_a_body_that_is_not_a_json_object_is_400(site_client, google, raw):
    response = site_client.post(PROVIDER_TOKEN_URL, data=raw, content_type="application/json")
    assert response.status_code == 400
    assert "rz_refresh" not in site_client.cookies


def test_a_client_id_mismatch_is_logged_without_the_values(site_client, google, caplog):
    wrong = "attacker-app.apps.googleusercontent.com"
    with caplog.at_level(logging.WARNING, logger="apps.accounts.google"):
        data = valid_body(google, client_id=wrong)
        response = post_json(site_client, PROVIDER_TOKEN_URL, data)
    assert response.status_code == 400
    text = caplog.text
    assert "GOOGLE_OAUTH_CLIENT_ID" in text
    assert wrong not in text
    assert TEST_GOOGLE_CLIENT_ID not in text
    assert data["token"]["id_token"] not in text


def test_the_endpoint_is_a_404_while_google_is_disabled(site_client, google, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = ""
    response = google.login(site_client)
    assert response.status_code == 404
    assert first_error(response)["code"] == "not_found"
    assert not User.objects.exists()
    assert google.fetches == 0


def test_a_get_is_404(site_client):
    assert site_client.get(PROVIDER_TOKEN_URL).status_code == 404


# ---------- sessions ----------


def test_a_stale_bearer_token_is_ignored(site_client, google):
    other = UserFactory()
    response = post_json(
        site_client,
        PROVIDER_TOKEN_URL,
        valid_body(google),
        HTTP_AUTHORIZATION=f"Bearer {access_token_for(other)}",
        HTTP_X_SESSION_TOKEN="bogus",
    )
    assert response.status_code == 200
    assert User.objects.count() == 2


def test_logging_in_again_revokes_the_session_behind_the_old_cookie(site_client, google):
    user = UserFactory()
    assert login(site_client, user.email).status_code == 200
    old_token = refresh_cookie(site_client)

    assert google.login(site_client, email="jo@example.org").status_code == 200

    assert refresh_cookie(site_client) != old_token
    stale = Client(headers=SITE_HEADERS)
    use_refresh_cookie(stale, old_token)
    assert refresh(stale).status_code == 400


def test_the_new_session_can_refresh_and_has_no_secret_in_the_body(site_client, google):
    response = google.login(site_client, email="kim@example.org")
    assert_no_secrets(response)
    again = refresh(site_client)
    assert again.status_code == 200
    assert body(again)["data"]["access_token"]


# ---------- rate limit ----------


def test_thirty_sign_ins_a_minute_then_429(site_client, google):
    garbage = {**valid_body(google), "provider": "github"}
    for _ in range(30):
        assert post_json(site_client, PROVIDER_TOKEN_URL, garbage).status_code == 400
    response = google.login(site_client)
    assert response.status_code == 429
    assert body(response) == {"status": 429}
    assert google.fetches == 0


# ---------- Part 14: the "Google connected" email ----------


def connected_emails():
    return [m for m in mail.outbox if "Continue with Google is now connected" in m.subject]


def test_linking_to_an_existing_account_tells_its_owner(
    site_client, google, django_capture_on_commit_callbacks
):
    user = UserFactory(email="ada@gmail.com")
    verified_address(user)
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        assert google.login(site_client, email="ada@gmail.com", sub="sub-mail").status_code == 200

    (message,) = connected_emails()
    assert message.to == ["ada@gmail.com"]
    assert "removed your old password" not in message.body  # the verified address kept it
    assert user.check_password(DEFAULT_PASSWORD)


def test_when_the_link_wiped_the_password_the_email_says_so(
    site_client, google, django_capture_on_commit_callbacks
):
    user = UserFactory(email="bob@gmail.com")  # no verified address row: allauth wipes the password
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        assert google.login(site_client, email="bob@gmail.com").status_code == 200

    user.refresh_from_db()
    assert not user.has_usable_password()
    (message,) = connected_emails()
    assert "hadn't been verified" in message.body
    assert "It no longer works" in message.body
    assert "/forgot-password" in message.body
    assert "hadn't been verified" in message.alternatives[0][0]


def test_a_new_google_user_and_a_returning_one_get_no_such_email(
    site_client, google, django_capture_on_commit_callbacks
):
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert google.login(site_client, email="new@gmail.com", sub="sub-new").status_code == 200
    with django_capture_on_commit_callbacks(execute=True):
        assert google.login(Client(headers=SITE_HEADERS), email="new@gmail.com", sub="sub-new")
    assert connected_emails() == []
