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
