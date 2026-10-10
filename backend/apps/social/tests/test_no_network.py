"""Nothing in Parts 6, 7 and 7B reaches the network: no profile, follow, feed, like, comment,
repost or bookmark call fetches anything."""

import http.client
import re
import socket
import urllib.request
from pathlib import Path

import pytest
import requests

import apps.social
from apps.social.tests.factories import FollowFactory, PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def blocked(monkeypatch):
    calls = []

    def blocker(name):
        def refuse(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"network access attempted: {name}")

        return refuse

    monkeypatch.setattr(socket.socket, "connect", blocker("socket.connect"))
    monkeypatch.setattr(socket, "create_connection", blocker("socket.create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", blocker("socket.getaddrinfo"))
    monkeypatch.setattr(urllib.request, "urlopen", blocker("urlopen"))
    monkeypatch.setattr(requests.Session, "request", blocker("requests"))
    monkeypatch.setattr(http.client.HTTPConnection, "connect", blocker("http.client"))
    return calls


def test_profiles_follows_lists_and_the_feed_make_no_network_request(blocked, auth_client):
    ada, bo = VerifiedUserFactory(username="ada"), VerifiedUserFactory(username="bob")
    PostFactory(author=bo, fact=True, sources=["https://example.org/report"])
    client = auth_client(ada)
    assert client.post("/api/v1/users/bob/follow/").status_code == 201
    assert client.get("/api/v1/users/bob/").status_code == 200
    assert client.get("/api/v1/users/bob/posts/").status_code == 200
    assert client.get("/api/v1/users/bob/followers/").status_code == 200
    assert client.get("/api/v1/users/ada/following/").status_code == 200
    assert client.get("/api/v1/feed/").json()["results"]
    assert client.delete("/api/v1/users/bob/follow/").status_code == 204
    assert blocked == []


def test_likes_and_comments_make_no_network_request(blocked, auth_client):
    ada = VerifiedUserFactory(username="ada")
    post = PostFactory(fact=True, sources=["https://example.org/report"])
    client = auth_client(ada)
    assert client.post(f"/api/v1/posts/{post.pk}/like/").status_code == 201
    created = client.post(
        f"/api/v1/posts/{post.pk}/comments/",
        {"content": "See https://example.org/x"},
        format="json",
    )
    assert created.status_code == 201
    assert client.get(f"/api/v1/posts/{post.pk}/comments/").json()["results"]
    assert client.delete(f"/api/v1/comments/{created.json()['id']}/").status_code == 204
    assert client.delete(f"/api/v1/posts/{post.pk}/like/").status_code == 204
    assert blocked == []


def test_reposts_and_bookmarks_make_no_network_request(blocked, auth_client):
    ada, bo = VerifiedUserFactory(username="ada"), VerifiedUserFactory(username="bob")
    post = PostFactory(author=bo, fact=True, sources=["https://example.org/report"])
    client = auth_client(ada)
    assert client.post("/api/v1/users/bob/follow/").status_code == 201
    assert client.post(f"/api/v1/posts/{post.pk}/repost/").status_code == 201
    assert client.post(f"/api/v1/posts/{post.pk}/bookmark/").status_code == 201
    assert client.get("/api/v1/me/bookmarks/").json()["results"]
    assert client.get("/api/v1/feed/").json()["results"]
    assert client.get("/api/v1/users/ada/posts/").json()["results"]
    assert client.delete(f"/api/v1/posts/{post.pk}/repost/").status_code == 204
    assert client.delete(f"/api/v1/posts/{post.pk}/bookmark/").status_code == 204
    assert blocked == []


def test_the_social_code_imports_nothing_that_can_fetch():
    forbidden = re.compile(
        r"^\s*(?:import|from)\s+(?:urllib\.request|urllib3|requests|httpx|aiohttp|socket|http\.client)\b",
        re.MULTILINE,
    )
    package = Path(apps.social.__file__).parent
    offenders = [p.name for p in package.glob("*.py") if forbidden.search(p.read_text())]
    assert offenders == []
    assert FollowFactory  # the factory module imports cleanly
