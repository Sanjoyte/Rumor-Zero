"""JWTAuthentication: Bearer access tokens; a deleted or inactive user is 401, never a 500."""

import jwt
import pytest

from apps.accounts.models import User
from apps.accounts.tests.conftest import access_token_for
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/"


def get_me(client, token, scheme="Bearer"):
    return client.get(URL, HTTP_AUTHORIZATION=f"{scheme} {token}")


def test_a_valid_token_costs_the_user_load_and_the_google_check(
    api_client, django_assert_num_queries
):
    # Loading the user, plus `google_connected` (a SocialAccount exists() in the /me serializer).
    user = UserFactory()
    token = access_token_for(user)
    with django_assert_num_queries(2):
        assert get_me(api_client, token).status_code == 200


def test_a_deleted_users_token_is_401(api_client):
    user = UserFactory()
    token = access_token_for(user)
    User.objects.filter(pk=user.pk).delete()
    response = get_me(api_client, token)
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_failed"


def test_an_inactive_users_token_is_401(api_client):
    user = UserFactory()
    token = access_token_for(user)
    User.objects.filter(pk=user.pk).update(is_active=False)
    assert get_me(api_client, token).status_code == 401


@pytest.mark.parametrize("token", ["garbage", "a.b.c"])
def test_a_bad_token_is_401(api_client, token):
    assert get_me(api_client, token).status_code == 401


def test_a_token_signed_with_another_key_is_401(api_client, settings):
    user = UserFactory()
    claims = jwt.decode(access_token_for(user), options={"verify_signature": False})
    forged = jwt.encode(claims, "some-other-key-that-is-long-enough!!", algorithm="HS256")
    assert get_me(api_client, forged).status_code == 401


def test_a_refresh_token_is_not_an_access_token(site_client, api_client):
    from apps.accounts.tests.conftest import login, refresh_cookie

    user = UserFactory()
    login(site_client, user.email)
    assert get_me(api_client, refresh_cookie(site_client)).status_code == 401


def test_another_scheme_is_ignored(api_client):
    token = access_token_for(UserFactory())
    response = get_me(api_client, token, scheme="Token")
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"
