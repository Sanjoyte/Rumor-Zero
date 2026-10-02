"""GET /api/v1/auth/username-available/?u= (the live check on the sign-up form)."""

import pytest

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/auth/username-available/"


def check(client, value, **extra):
    return client.get(URL, {"u": value}, **extra)


@pytest.mark.parametrize(
    ("value", "username", "available", "reason"),
    [
        ("ada", "ada", True, None),
        ("Ada", "ada", True, None),
        ("  ADA_99  ", "ada_99", True, None),
        ("Ａｄａ", "ada", True, None),  # fullwidth letters fold to ASCII (NFKC)
        ("ab", "ab", False, "invalid"),
        ("ada-lovelace", "ada-lovelace", False, "invalid"),
        ("ada lovelace", "ada lovelace", False, "invalid"),
        ("émile", "émile", False, "invalid"),
        ("a" * 31, "a" * 31, False, "invalid"),
        ("", "", False, "invalid"),
        ("admin", "admin", False, "reserved"),
        ("Moderator", "moderator", False, "reserved"),
        ("ada_admin", "ada_admin", True, None),
    ],
)
def test_format_case_and_reserved_words(api_client, value, username, available, reason):
    response = check(api_client, value)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == username
    assert data["available"] is available
    assert data["reason"] == reason
    assert data["message"]


def test_a_taken_username_whatever_the_case_or_width(api_client):
    UserFactory(username="grace")
    for value in ("grace", "GRACE", "Ｇｒａｃｅ"):
        data = check(api_client, value).json()
        assert (data["available"], data["reason"]) == (False, "taken")
        assert data["message"] == "That username is taken."


def test_over_64_characters_is_invalid_without_normalising_it_all(api_client):
    data = check(api_client, "a" * 65).json()
    assert (data["available"], data["reason"]) == (False, "invalid")


def test_the_query_parameter_is_required(api_client):
    response = api_client.get(URL)
    assert response.status_code == 400
    assert response.json() == {"u": ["This query parameter is required."]}


def test_it_is_one_query_never_cached_and_needs_no_login(api_client, django_assert_num_queries):
    with django_assert_num_queries(1):
        response = check(api_client, "ada", HTTP_AUTHORIZATION="Bearer not-a-token")
    assert response.status_code == 200
    assert "no-cache" in response["Cache-Control"]


def test_an_invalid_name_needs_no_query(api_client, django_assert_num_queries):
    with django_assert_num_queries(0):
        check(api_client, "no")


def test_thirty_checks_per_minute_per_ip(api_client, settings):
    settings.PROXY_SHARED_SECRET = "test-relay-secret"
    relay = {"HTTP_X_RZ_PROXY_SECRET": "test-relay-secret"}
    for n in range(30):
        response = check(api_client, f"name_{n}", HTTP_X_RZ_CLIENT_IP="203.0.113.1", **relay)
        assert response.status_code == 200
    response = check(api_client, "one_more", HTTP_X_RZ_CLIENT_IP="203.0.113.1", **relay)
    assert response.status_code == 429
    assert response.json()["code"] == "throttled"
    assert "Retry-After" in response
    other = check(api_client, "one_more", HTTP_X_RZ_CLIENT_IP="203.0.113.2", **relay)
    assert other.status_code == 200
