"""PATCH /api/v1/me/ (ARCHITECTURE §9; Part 14)."""

import pytest

from apps.accounts import services
from apps.accounts.models import User
from apps.accounts.tests.conftest import access_token_for, run_together
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/"


def verified(**fields):
    return UserFactory(is_email_verified=True, **fields)


def patch(client, user, body, token=None):
    token = token or access_token_for(user)
    return client.patch(URL, body, format="json", HTTP_AUTHORIZATION=f"Bearer {token}")


def test_it_saves_the_three_fields_and_answers_the_me_object(api_client):
    user = verified(username="ada_old")
    response = patch(
        api_client, user, {"display_name": "Ada L.", "username": "ada_new", "bio": "Maths."}
    )

    assert response.status_code == 200
    data = response.json()
    assert (data["display_name"], data["username"], data["bio"]) == ("Ada L.", "ada_new", "Maths.")
    assert data["id"] == str(user.pk) and data["email"] == user.email
    assert "no-cache" in response["Cache-Control"]
    user.refresh_from_db()
    assert (user.display_name, user.username, user.bio) == ("Ada L.", "ada_new", "Maths.")


def test_a_partial_body_changes_only_what_it_names(api_client):
    user = verified(display_name="Before", bio="Keep me")
    assert patch(api_client, user, {"display_name": "After"}).status_code == 200
    user.refresh_from_db()
    assert (user.display_name, user.bio) == ("After", "Keep me")


def test_an_empty_body_changes_nothing_and_writes_nothing(api_client, django_assert_num_queries):
    user = verified(display_name="Same")
    token = access_token_for(user)
    with django_assert_num_queries(2):  # the Me object's two reads; nothing written
        response = patch(api_client, user, {}, token)
    assert response.status_code == 200 and response.json()["display_name"] == "Same"


def test_values_are_normalised(api_client):
    user = verified()
    response = patch(
        api_client,
        user,
        {"display_name": "  Ada  ", "username": " ＡDA_Ｎew ", "bio": "  one\r\ntwo\rthree  \n"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Ada"
    assert data["username"] == "ada_new"
    assert data["bio"] == "one\ntwo\nthree"


def test_clearing_the_display_name_and_bio_is_allowed(api_client):
    user = verified(display_name="Name", bio="Bio")
    assert patch(api_client, user, {"display_name": "", "bio": "  "}).status_code == 200
    user.refresh_from_db()
    assert (user.display_name, user.bio) == ("", "")


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"username": "ab"}, "username"),
        ({"username": "has space"}, "username"),
        ({"username": "x" * 31}, "username"),
        ({"username": "x" * 65}, "username"),
        ({"username": "admin"}, "username"),
        ({"username": "ROOT"}, "username"),
        ({"username": ""}, "username"),
        ({"username": None}, "username"),
        ({"username": 42}, "username"),
        ({"display_name": "x" * 51}, "display_name"),
        ({"display_name": "two\nlines"}, "display_name"),
        ({"display_name": "tab\there"}, "display_name"),
        ({"display_name": "sneaky‮evil"}, "display_name"),
        ({"display_name": "para graph"}, "display_name"),
        ({"display_name": None}, "display_name"),
        ({"bio": "x" * 281}, "bio"),
        ({"bio": "bell\x07"}, "bio"),
        ({"bio": "sneaky‮evil"}, "bio"),
        ({"bio": None}, "bio"),
        ({"bio": ["a"]}, "bio"),
    ],
)
def test_bad_values_are_a_400_on_their_field(api_client, body, field):
    user = verified(username="ada_old", display_name="Keep", bio="Keep")
    response = patch(api_client, user, body)
    assert response.status_code == 400
    assert list(response.json()) == [field]
    user.refresh_from_db()
    assert (user.username, user.display_name, user.bio) == ("ada_old", "Keep", "Keep")


def test_the_limits_count_code_points_exactly(api_client):
    user = verified()
    body = {"display_name": "é" * 50, "bio": "𝔸" * 280, "username": "a" * 30}
    assert patch(api_client, user, body).status_code == 200


def test_a_bio_of_exactly_280_after_crlf_is_fine(api_client):
    user = verified()
    bio = "a\r\n" * 90 + "b" * 9  # 279 characters once each CRLF counts as one
    assert patch(api_client, user, {"bio": bio}).status_code == 200


def test_a_taken_username_is_a_400_that_names_it(api_client):
    UserFactory(username="taken_name")
    user = verified(username="mine")
    response = patch(api_client, user, {"username": "Taken_Name"})
    assert response.status_code == 400
    assert response.json() == {"username": ["That username is taken."]}


def test_keeping_your_own_username_is_not_a_conflict(api_client):
    user = verified(username="mine")
    response = patch(api_client, user, {"username": "MINE", "bio": "x"})
    assert response.status_code == 200 and response.json()["username"] == "mine"


def test_the_old_username_is_free_for_someone_else(api_client):
    user = verified(username="first_name")
    assert patch(api_client, user, {"username": "second_name"}).status_code == 200
    other = verified()
    assert patch(api_client, other, {"username": "first_name"}).status_code == 200


def test_other_keys_are_ignored(api_client):
    user = verified()
    other_email = user.email
    response = patch(
        api_client,
        user,
        {
            "bio": "Only this",
            "email": "new@example.test",
            "role": "senior_moderator",
            "is_email_verified": False,
            "is_staff": True,
            "is_superuser": True,
            "reputation_score": 100,
            "reputation_sample": 99,
            "emergency_blocked_until": "2030-01-01T00:00:00Z",
            "avatar_version": "v9",
            "id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.bio == "Only this"
    assert user.email == other_email
    assert (user.role, user.is_email_verified, user.is_staff, user.is_superuser) == (
        "user",
        True,
        False,
        False,
    )
    assert (user.reputation_score, user.reputation_sample) == (50, 0)
    assert user.emergency_blocked_until is None and user.avatar_version is None


def test_only_the_changed_fields_are_written_back(api_client):
    """The save lists its fields: a score, a verification or a role that moved after the user was
    loaded survives (a full save would write the stale copy back)."""
    user = UserFactory()
    stale = User.objects.get(pk=user.pk)
    User.objects.filter(pk=user.pk).update(
        reputation_score=80, reputation_sample=7, is_email_verified=True, display_name="Moved"
    )

    services.update_profile(stale, {"bio": "changed"})

    user.refresh_from_db()
    assert (user.bio, user.reputation_score, user.reputation_sample) == ("changed", 80, 7)
    assert user.is_email_verified is True and user.display_name == "Moved"


def test_it_returns_what_changed():
    user = verified(display_name="A", bio="B")
    assert services.update_profile(user, {"display_name": "A", "bio": "C"}) == ["bio"]
    assert services.update_profile(user, {}) == []


def test_an_unverified_account_is_refused(api_client):
    user = UserFactory(display_name="Same")
    response = patch(api_client, user, {"display_name": "New"})
    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"
    user.refresh_from_db()
    assert user.display_name == "Same"


def test_anonymous_is_401(api_client):
    response = api_client.patch(URL, {"bio": "x"}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_two_renames_to_one_name_at_once_give_one_winner_and_one_400(api_client):
    first, second = verified(), verified()
    tokens = [access_token_for(first), access_token_for(second)]

    def rename(user, token):
        from rest_framework.test import APIClient

        return patch(APIClient(), user, {"username": "the_prize"}, token).status_code

    codes = run_together(
        lambda: rename(first, tokens[0]),
        lambda: rename(second, tokens[1]),
    )

    assert sorted(codes) == [200, 400]
    assert User.objects.filter(username="the_prize").count() == 1


def test_the_integrity_error_of_a_lost_race_is_a_username_taken(monkeypatch):
    """The unique index is the last word when the pre-check passed."""
    user = verified(username="mine")
    UserFactory(username="their_name")
    monkeypatch.setattr(
        "apps.accounts.services.User.objects.filter",
        lambda *args, **kwargs: type(
            "Empty", (), {"exclude": lambda self, **kw: self, "exists": lambda self: False}
        )(),
    )
    with pytest.raises(services.UsernameTaken):
        services.update_profile(user, {"username": "their_name"})


def test_thirty_updates_an_hour_then_429(api_client):
    user = verified()
    token = access_token_for(user)
    codes = [patch(api_client, user, {"bio": f"b{n}"}, token).status_code for n in range(31)]
    assert codes[:30] == [200] * 30
    assert codes[30] == 429


def test_a_get_never_uses_up_the_update_allowance(api_client):
    user = verified()
    token = access_token_for(user)
    for _ in range(35):
        assert api_client.get(URL, HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 200
    assert patch(api_client, user, {"bio": "ok"}, token).status_code == 200
