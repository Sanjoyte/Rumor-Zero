"""A user-supplied source is validated and stored, never fetched (ARCHITECTURE §4c, §12)."""

import http.client
import re
import socket
import urllib.request
from pathlib import Path

import pytest
import requests

import apps.posts
from apps.posts.tests.factories import VerifiedUserFactory

pytestmark = pytest.mark.django_db

SOURCES = [
    "https://example.org/report",
    "https://bücher.example/über",
    "doi:10.1038/s41558-024-02102",
    "http://dx.doi.org/10.1000/xyz",
    "https://doi.org/10.1000/xyz?utm=1",
]


@pytest.fixture
def blocked(monkeypatch):
    """Every way Python code reaches the network records the attempt and fails."""
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


def test_creating_a_post_with_sources_makes_no_network_request(blocked, auth_client, fact_limit):
    client = auth_client(VerifiedUserFactory())
    response = client.post(
        "/api/v1/posts/",
        {"content": "A claim with sources", "post_type": "fact", "sources": SOURCES[:4]},
        format="json",
    )
    assert response.status_code == 201, response.content
    # Reading it back (list and sources display) is network-free too.
    assert client.get("/api/v1/posts/").status_code == 200
    assert blocked == []


def test_a_refused_source_makes_no_request_either(blocked, auth_client, fact_limit):
    client = auth_client(VerifiedUserFactory())
    response = client.post(
        "/api/v1/posts/",
        {"content": "x", "post_type": "fact", "sources": ["https://localhost/x", "10.1/bad"]},
        format="json",
    )
    assert response.status_code == 400
    assert blocked == []


def test_the_blocker_really_blocks(blocked):
    with pytest.raises(AssertionError):
        socket.getaddrinfo("example.org", 80)
    assert blocked == ["socket.getaddrinfo"]


def test_the_posts_code_imports_nothing_that_can_fetch():
    forbidden = re.compile(
        r"^\s*(?:import|from)\s+(?:urllib\.request|urllib3|requests|httpx|aiohttp|socket|http\.client)\b",
        re.MULTILINE,
    )
    package = Path(apps.posts.__file__).parent
    offenders = [
        path.name
        for path in package.glob("*.py")
        if forbidden.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
