"""`IPScopedRateThrottle` (Part 12): a scoped throttle counted per client IP, signed in or not."""

from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.tests.conftest import access_token_for
from apps.accounts.tests.factories import UserFactory
from apps.core.throttles import IPScopedRateThrottle


def key_for(user, address):
    request = APIRequestFactory().get("/", REMOTE_ADDR=address)
    request.user = user
    throttle = IPScopedRateThrottle()
    throttle.scope = "search"
    return throttle.get_cache_key(request, view=None)


def test_the_key_is_the_scope_and_the_address():
    assert key_for(SimpleNamespace(is_authenticated=False, pk=None), "203.0.113.5") == (
        "throttle_search_203.0.113.5"
    )


def test_a_signed_in_user_is_still_counted_by_address():
    one = key_for(SimpleNamespace(is_authenticated=True, pk=1), "203.0.113.5")
    two = key_for(SimpleNamespace(is_authenticated=True, pk=2), "203.0.113.5")
    anonymous = key_for(SimpleNamespace(is_authenticated=False, pk=None), "203.0.113.5")
    assert one == two == anonymous


def test_another_address_has_its_own_bucket():
    user = SimpleNamespace(is_authenticated=False, pk=None)
    assert key_for(user, "203.0.113.5") != key_for(user, "203.0.113.6")


@pytest.mark.django_db
def test_sixty_requests_a_minute_per_address_then_429(api_client, settings):
    settings.PROXY_SHARED_SECRET = "test-relay-secret"
    relay = {"HTTP_X_RZ_PROXY_SECRET": "test-relay-secret"}
    for _ in range(60):
        response = api_client.get(
            "/api/v1/search/?q=x", HTTP_X_RZ_CLIENT_IP="203.0.113.21", **relay
        )
        assert response.status_code == 200
    response = api_client.get("/api/v1/search/?q=x", HTTP_X_RZ_CLIENT_IP="203.0.113.21", **relay)
    assert response.status_code == 429
    assert response.json()["code"] == "throttled"
    assert "Retry-After" in response
    other = api_client.get("/api/v1/search/?q=x", HTTP_X_RZ_CLIENT_IP="203.0.113.22", **relay)
    assert other.status_code == 200


RELAY_SECRET = "test-relay-secret"


def relay(address):
    return {"HTTP_X_RZ_PROXY_SECRET": RELAY_SECRET, "HTTP_X_RZ_CLIENT_IP": address}


@pytest.mark.django_db
def test_signed_in_and_anonymous_requests_from_one_address_share_the_bucket(api_client, settings):
    settings.PROXY_SHARED_SECRET = RELAY_SECRET
    signed_in = APIClient()
    signed_in.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token_for(UserFactory())}")
    for n in range(60):
        client = signed_in if n % 2 else api_client
        assert client.get("/api/v1/search/?q=x", **relay("203.0.113.31")).status_code == 200
    assert signed_in.get("/api/v1/search/?q=x", **relay("203.0.113.31")).status_code == 429
    assert api_client.get("/api/v1/search/?q=x", **relay("203.0.113.31")).status_code == 429


@pytest.mark.django_db
def test_a_stale_token_401_does_not_count_but_a_400_does(api_client, settings):
    settings.PROXY_SHARED_SECRET = RELAY_SECRET
    address = relay("203.0.113.41")
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
    for _ in range(70):
        assert api_client.get("/api/v1/search/?q=x", **address).status_code == 401
    api_client.credentials()
    for _ in range(60):
        assert api_client.get("/api/v1/search/", **address).status_code == 400  # no q
    assert api_client.get("/api/v1/search/?q=x", **address).status_code == 429


@pytest.mark.django_db
def test_the_other_scopes_are_untouched(api_client, settings):
    settings.PROXY_SHARED_SECRET = RELAY_SECRET
    address = relay("203.0.113.51")
    for _ in range(61):
        api_client.get("/api/v1/search/?q=x", **address)
    assert api_client.get("/api/v1/posts/status/?ids=", **address).status_code != 429
