import pytest
from django.contrib.sessions.models import Session
from django.http import HttpResponse

from apps.accounts import cookies
from apps.accounts.tests.conftest import login, refresh_cookie
from apps.accounts.tests.factories import UserFactory


def test_extract_tokens_removes_every_secret_and_keeps_the_access_token():
    body = {
        "status": 200,
        "data": {"user": {"id": "u1"}},
        "meta": {
            "is_authenticated": True,
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "session_token": "raw-session-key",
        },
    }
    cleaned, refresh_token = cookies.extract_tokens(body)
    assert refresh_token == "refresh-1"
    assert cleaned["meta"] == {"is_authenticated": True, "access_token": "access-1"}
    assert cleaned["data"] == {"user": {"id": "u1"}}


def test_extract_tokens_reads_the_refresh_response_shape():
    cleaned, refresh_token = cookies.extract_tokens(
        {"status": 200, "data": {"access_token": "access-2", "refresh_token": "refresh-2"}}
    )
    assert refresh_token == "refresh-2"
    assert cleaned == {"status": 200, "data": {"access_token": "access-2"}}


@pytest.mark.parametrize(
    "body",
    [
        # allauth's 409 / 410 / 401 shapes can carry a session token in meta.
        {"status": 409, "meta": {"session_token": "raw-session-key"}},
        {"status": 410, "data": {"flows": []}, "meta": {"session_token": "raw-session-key"}},
        {"status": 401, "data": {"flows": [{"id": "login"}]}, "meta": {"is_authenticated": False}},
    ],
)
def test_extract_tokens_strips_session_tokens_from_error_bodies(body):
    cleaned, refresh_token = cookies.extract_tokens(body)
    assert refresh_token is None
    assert "session_token" not in cleaned.get("meta", {})


@pytest.mark.parametrize("body", [None, [], "text", {"meta": "x", "data": ["y"]}])
def test_extract_tokens_ignores_odd_shapes(body):
    assert cookies.extract_tokens(body) == (body, None)


def test_an_empty_refresh_token_is_not_a_token():
    _, refresh_token = cookies.extract_tokens({"meta": {"refresh_token": ""}})
    assert refresh_token is None


@pytest.mark.parametrize(
    ("header", "count"),
    [
        ("", 0),
        ("rz_refresh=a", 1),
        (" rz_refresh=a ; other=1", 1),
        ("rz_refresh=a; rz_refresh=b", 2),
        ("rz_refreshx=a; xrz_refresh=b; rz_session=1", 0),
        ("rz_refresh", 0),
    ],
)
def test_count_cookie(header, count):
    assert cookies.count_cookie(header, "rz_refresh") == count


def _morsels(response):
    return response.cookies["rz_refresh"], response.cookies["rz_session"]


@pytest.mark.parametrize("secure", [False, True])
def test_auth_cookie_attributes(settings, secure):
    settings.AUTH_COOKIE_SECURE = secure
    response = HttpResponse()
    cookies.set_auth_cookies(response, "refresh.token.value")
    refresh, hint = _morsels(response)

    assert refresh.value == "refresh.token.value"
    assert refresh["httponly"] is True
    assert refresh["samesite"] == "Lax"
    assert refresh["path"] == "/api/auth/"
    assert refresh["max-age"] == 14 * 86400
    assert refresh["domain"] == ""
    assert bool(refresh["secure"]) is secure

    assert hint.value == "1"
    assert not hint["httponly"]
    assert hint["samesite"] == "Lax"
    assert hint["path"] == "/"
    assert hint["max-age"] == 14 * 86400
    assert hint["domain"] == ""
    assert bool(hint["secure"]) is secure

    # One Set-Cookie line each, the token unquoted.
    header = refresh.OutputString()
    assert header.startswith("rz_refresh=refresh.token.value;")
    assert ("Secure" in header) is secure


@pytest.mark.parametrize("secure", [False, True])
def test_deleting_the_cookies_uses_the_same_attributes(settings, secure):
    settings.AUTH_COOKIE_SECURE = secure
    response = HttpResponse()
    cookies.delete_auth_cookies(response)
    refresh, hint = _morsels(response)
    for morsel, path in ((refresh, "/api/auth/"), (hint, "/")):
        assert morsel.value == ""
        assert morsel["max-age"] == 0
        assert morsel["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"
        assert morsel["path"] == path
        assert morsel["samesite"] == "Lax"
        assert bool(morsel["secure"]) is secure
    assert refresh["httponly"] is True
    assert not hint["httponly"]


@pytest.mark.django_db
def test_revoking_a_refresh_token_deletes_its_session(site_client):
    user = UserFactory()
    assert login(site_client, user.email).status_code == 200
    token = refresh_cookie(site_client)
    assert Session.objects.count() == 1

    assert cookies.revoke_refresh_token_session(token) is True
    assert Session.objects.count() == 0
    assert cookies.revoke_refresh_token_session(token) is False


@pytest.mark.django_db
@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c"])
def test_revoking_garbage_does_nothing(token):
    assert cookies.revoke_refresh_token_session(token) is False
