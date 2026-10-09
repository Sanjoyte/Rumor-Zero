import re

import pytest
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class UserSerializer(serializers.Serializer):
    username = serializers.CharField()


class UserList(ListAPIView):
    """Uses the project's default pagination class and its default ordering (-created_at)."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    authentication_classes = []
    permission_classes = []


def get_page(**params):
    response = UserList.as_view()(APIRequestFactory().get("/", params))
    response.render()
    return response


def test_default_pagination_shape_and_cursor_walk():
    UserFactory.create_batch(25)

    first = get_page()
    assert first.status_code == 200
    assert set(first.data) == {"results", "next_cursor"}
    assert len(first.data["results"]) == 20

    token = first.data["next_cursor"]
    assert isinstance(token, str)
    # A bare token: no absolute URL (it would point past the API relay), nothing to escape.
    assert "http" not in token and "?" not in token
    assert re.fullmatch(r"[A-Za-z0-9_-]+", token)

    second = get_page(cursor=token)
    assert len(second.data["results"]) == 5
    assert second.data["next_cursor"] is None

    usernames = [row["username"] for row in first.data["results"] + second.data["results"]]
    assert len(set(usernames)) == 25


def test_a_single_page_has_a_null_cursor():
    UserFactory.create_batch(3)
    page = get_page()
    assert len(page.data["results"]) == 3
    assert page.data["next_cursor"] is None


def test_page_size_can_be_lowered_and_is_capped_at_50():
    UserFactory.create_batch(55)
    assert len(get_page(page_size=5).data["results"]) == 5
    capped = get_page(page_size=500)
    assert len(capped.data["results"]) == 50
    assert capped.data["next_cursor"] is not None


def test_an_invalid_cursor_is_a_404_with_a_code():
    page = get_page(cursor="%%not-a-cursor%%")
    assert page.status_code == 404
    assert page.data["code"] == "not_found"


# ---------- TimestampCursorMixin (Part 6): the guard FeedPagination used to own ----------


class GuardedList(UserList):
    from apps.core.pagination import CursorPagination, TimestampCursorMixin

    class pagination_class(TimestampCursorMixin, CursorPagination):
        ordering = ("-created_at", "-id")


def guarded_page(cursor):
    response = GuardedList.as_view()(APIRequestFactory().get("/", {"cursor": cursor}))
    response.render()
    return response


def encoded(**tokens):
    import base64
    from urllib.parse import urlencode

    return base64.urlsafe_b64encode(urlencode(tokens).encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "position",
    ["not a date", "2026-01-01T00:00:00", "9999-99-99T00:00:00+00:00", "", "12"],
)
def test_the_mixin_turns_a_crafted_position_into_a_404(position):
    UserFactory.create_batch(3)
    assert guarded_page(encoded(p=position)).status_code == 404


def test_the_mixin_lets_a_real_position_through():
    UserFactory.create_batch(3)
    assert guarded_page(encoded(p="2999-01-01T00:00:00+00:00")).status_code == 200


def test_the_unguarded_default_class_would_have_failed_on_the_same_cursor():
    """Control: without the mixin a crafted position raises instead of answering 404."""
    UserFactory.create_batch(3)
    cursor = encoded(p="not a date")
    with pytest.raises(Exception) as caught:  # noqa: PT011 (Django's ValidationError)
        get_page(cursor=cursor)
    assert caught.value.__class__.__name__ == "ValidationError"
