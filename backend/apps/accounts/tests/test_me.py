"""GET /api/v1/me/ (ARCHITECTURE §9)."""

import pytest
from django.conf import settings

from apps.accounts.models import Role
from apps.accounts.tests.conftest import access_token_for
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/"
FIELDS = {
    "id",
    "username",
    "display_name",
    "email",
    "is_email_verified",
    "role",
    "has_usable_password",
    "google_connected",
    "avatar_url",
}


def get_me(client, user, token=None):
    token = token or access_token_for(user)
    return client.get(URL, HTTP_AUTHORIZATION=f"Bearer {token}")


def test_the_fields_for_an_ordinary_user(api_client, django_assert_num_queries):
    user = UserFactory(display_name="Ada Lovelace")
    token = access_token_for(user)
    with django_assert_num_queries(2):  # the user, and the SocialAccount check
        response = get_me(api_client, user, token)

    assert response.status_code == 200
    data = response.json()
    assert set(data) == FIELDS
    assert data == {
        "id": str(user.pk),
        "username": user.username,
        "display_name": "Ada Lovelace",
        "email": user.email,
        "is_email_verified": False,
        "role": "user",
        "has_usable_password": True,
        "google_connected": False,
        "avatar_url": None,
    }
    assert "no-cache" in response["Cache-Control"]


def test_google_connected_follows_the_social_account(api_client):
    from allauth.socialaccount.models import SocialAccount

    user = UserFactory()
    SocialAccount.objects.create(user=user, provider="google", uid="sub-1")
    assert get_me(api_client, user).json()["google_connected"] is True
    other = UserFactory()
    SocialAccount.objects.create(user=other, provider="github", uid="x")
    assert get_me(api_client, other).json()["google_connected"] is False


def test_an_unusable_password_and_a_photo(api_client):
    user = UserFactory(password=None, avatar_version="v3")
    data = get_me(api_client, user).json()
    assert data["has_usable_password"] is False
    assert data["avatar_url"] == f"/api/v1/avatars/{user.pk}/v3-96.webp"


@pytest.mark.parametrize(
    "kwargs", [{"role": Role.MODERATOR}, {"role": Role.SENIOR_MODERATOR}, {"is_superuser": True}]
)
def test_staff_also_get_the_admin_url(api_client, kwargs):
    user = UserFactory(**kwargs)
    data = get_me(api_client, user).json()
    assert set(data) == FIELDS | {"admin_url"}
    assert data["admin_url"] == f"http://testserver/{settings.ADMIN_URL_PATH}"


def test_anonymous_is_401(api_client):
    response = api_client.get(URL)
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"
    assert response["WWW-Authenticate"] == "Bearer"
