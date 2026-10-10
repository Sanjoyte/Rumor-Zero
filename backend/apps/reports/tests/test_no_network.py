"""Nothing in Part 8 reaches the network: a report fetches nothing, and nothing the reporter typed
(the details are plain text) is ever opened."""

import http.client
import re
import socket
import urllib.request
from pathlib import Path

import pytest
import requests
from django.utils import timezone

import apps.pipeline
import apps.reports
from apps.reports.tests.factories import aged_user
from apps.social.tests.factories import PostFactory

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


def test_reporting_makes_no_network_request(blocked, auth_client):
    post = PostFactory(fact=True, sources=["https://example.org/report", "10.1000/xyz"])
    client = auth_client(aged_user(now=timezone.now()))
    body = {"reason": "other", "details": "See https://evil.example/fetch-me and 10.1000/abc"}
    assert client.post(f"/api/v1/posts/{post.pk}/report/", body, format="json").status_code == 201
    assert client.get(f"/api/v1/posts/{post.pk}/").json()["reported_by_me"] is True
    assert blocked == []


def test_the_reports_and_pipeline_code_import_nothing_that_can_fetch():
    """Only the pipeline's HTTP client may open a connection (Part 9), and only to the configured
    `PIPELINE_URL`: no module fetches a user-supplied link. The allow-list must match exactly, so
    it can't silently go stale."""
    forbidden = re.compile(
        r"^\s*(?:import|from)\s+(?:urllib\.request|urllib3|requests|httpx|aiohttp|socket|http\.client)\b",
        re.MULTILINE,
    )
    importers = [
        f"{package.name}/{path.name}"
        for module in (apps.reports, apps.pipeline)
        for package in [Path(module.__file__).parent]
        for path in package.glob("*.py")
        if forbidden.search(path.read_text())
    ]
    assert importers == ["pipeline/clients.py"]
