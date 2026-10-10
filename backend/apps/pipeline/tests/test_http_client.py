"""The HTTP client for a real pipeline (ARCHITECTURE §6), against a fake HTTP layer: no test ever
opens a socket (the root conftest forbids the default opener)."""

import io
import json
import logging
import uuid
from decimal import Decimal
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.request import BaseHandler
from urllib.response import addinfourl

import pytest

from apps.pipeline import clients
from apps.pipeline.clients import (
    HttpPipelineClient,
    PipelineError,
    StubPipelineClient,
    build_opener_without_redirects,
    get_client,
)
from apps.pipeline.contract import PipelineRequest, PipelineResult

URL = "https://pipeline.example.test/v1/check"
KEY = "test-pipeline-key-5e1c9a7f"
POST_ID = uuid.UUID("7d9b2a40-3c1e-4f5a-8b6d-0e2f4a6c8e10")
GOOD = {"verdict": "true", "confidence_score": 93.25, "raw_result": {"model": "m1", "cites": 3}}


def request(sources=("https://example.org/report", "10.1000/xyz")):
    return PipelineRequest(POST_ID, "Water boils at 100 °C at sea level.", tuple(sources))


class FakeResponse:
    def __init__(self, body=b"", *, chunks=None):
        self.chunks = list(chunks) if chunks is not None else None
        self.stream = io.BytesIO(body)

    def read(self, size=-1):
        if self.chunks is not None:
            return self.chunks.pop(0) if self.chunks else b""
        return self.stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    """Records what would be sent; answers with `respond(request)` (which may raise)."""

    def __init__(self, respond):
        self.respond = respond
        self.calls = []

    def open(self, http_request, timeout=None):
        self.calls.append((http_request, timeout))
        return self.respond(http_request)


def answering(payload):
    return FakeOpener(lambda req: FakeResponse(json.dumps(payload).encode()))


def raising(exc):
    def respond(req):
        raise exc

    return FakeOpener(respond)


def client(opener):
    return HttpPipelineClient(URL, KEY, opener=opener)


def test_the_request_is_a_json_post_with_the_bearer_key_and_the_sources_in_order():
    opener = answering(GOOD)
    client(opener).check(request())

    [(sent, timeout)] = opener.calls
    assert sent.full_url == URL
    assert sent.get_method() == "POST"
    assert sent.get_header("Authorization") == f"Bearer {KEY}"
    assert sent.get_header("Content-type") == "application/json"
    assert sent.get_header("Accept") == "application/json"
    assert json.loads(sent.data) == {
        "post_id": str(POST_ID),
        "content": "Water boils at 100 °C at sea level.",
        "sources": ["https://example.org/report", "10.1000/xyz"],
    }
    assert timeout == 10  # per socket operation; the whole call is capped at 20 s


def test_a_request_without_sources_sends_an_empty_list():
    opener = answering(GOOD)
    client(opener).check(request(sources=()))
    assert json.loads(opener.calls[0][0].data)["sources"] == []


def test_the_only_address_ever_opened_is_the_pipeline_even_when_sources_are_links():
    opener = answering(GOOD)
    client(opener).check(request(sources=("https://evil.example/fetch-me", "http://a.example")))
    assert [sent.full_url for sent, _ in opener.calls] == [URL]


def test_a_good_answer_becomes_a_result():
    result = client(answering(GOOD)).check(request())
    assert result == PipelineResult("true", Decimal("93.25"), {"model": "m1", "cites": 3})


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (HTTPError(URL, 503, "Service Unavailable", Message(), None), "http_status"),
        (HTTPError(URL, 401, "Unauthorized", Message(), None), "http_status"),
        (TimeoutError("timed out"), "timeout"),
        (URLError(TimeoutError("timed out")), "timeout"),
        (URLError(ConnectionRefusedError(111, "refused")), "network"),
        (URLError("Name or service not known"), "network"),
        (ConnectionResetError(104, "reset"), "network"),
    ],
)
def test_transport_failures_become_pipeline_errors(exc, kind):
    with pytest.raises(PipelineError) as raised:
        client(raising(exc)).check(request())
    assert raised.value.kind == kind


def test_an_error_status_names_only_the_code():
    with pytest.raises(PipelineError) as raised:
        client(raising(HTTPError(URL, 503, "x", Message(), None))).check(request())
    assert raised.value.detail == "HTTP 503"


@pytest.mark.parametrize(
    ("body", "kind"),
    [
        (b"<html>busy</html>", "bad_response"),
        (b"\xff\xfe", "bad_response"),
        (b"", "bad_response"),
        (b"[1, 2]", "bad_response"),
        (b'"true"', "bad_response"),
        (json.dumps({"verdict": "true", "raw_result": {}}).encode(), "contract"),
        (json.dumps({**GOOD, "verdict": "debunked"}).encode(), "contract"),
        (json.dumps({**GOOD, "confidence_score": 140}).encode(), "contract"),
        (json.dumps({**GOOD, "confidence_score": True}).encode(), "contract"),
        (json.dumps({**GOOD, "raw_result": "text"}).encode(), "contract"),
        (b'{"verdict": "true", "confidence_score": NaN, "raw_result": {}}', "contract"),
    ],
)
def test_a_malformed_answer_is_refused(body, kind):
    opener = FakeOpener(lambda req: FakeResponse(body))
    with pytest.raises(PipelineError) as raised:
        client(opener).check(request())
    assert raised.value.kind == kind


def test_an_answer_over_64_kb_is_refused_but_64_kb_is_read():
    limit = clients.MAX_RESPONSE_BYTES
    at_limit = FakeOpener(lambda req: FakeResponse(b" " * limit))
    with pytest.raises(PipelineError) as raised:
        client(at_limit).check(request())
    assert raised.value.detail == "the answer is not JSON"  # read in full, then parsed

    over = FakeOpener(lambda req: FakeResponse(b" " * (limit + 1)))
    with pytest.raises(PipelineError) as raised:
        client(over).check(request())
    assert (raised.value.kind, raised.value.detail) == (
        "bad_response",
        "the answer is larger than 64 KB",
    )


def test_a_slow_trickle_is_cut_off_after_the_whole_call_takes_too_long(monkeypatch):
    clock = {"now": 1000.0}

    def monotonic():
        clock["now"] += 6  # every look at the clock is 6 s later
        return clock["now"]

    monkeypatch.setattr(clients.time, "monotonic", monotonic)
    endless = FakeOpener(lambda req: FakeResponse(chunks=[b" "] * 100))
    with pytest.raises(PipelineError) as raised:
        client(endless).check(request())
    assert raised.value.kind == "timeout"


def test_the_key_never_appears_in_an_error_a_log_or_the_client_repr(caplog):
    failures = [
        raising(HTTPError(URL, 403, KEY, Message(), None)),
        raising(URLError(KEY)),
        raising(OSError(KEY)),
        FakeOpener(lambda req: FakeResponse(KEY.encode())),
        answering({**GOOD, "verdict": KEY}),
    ]
    with caplog.at_level(logging.DEBUG):
        for opener in failures:
            with pytest.raises(PipelineError) as raised:
                client(opener).check(request())
            assert KEY not in str(raised.value)
            assert KEY not in raised.value.detail
    assert KEY not in caplog.text
    assert KEY not in repr(client(answering(GOOD)))


class _FakeHttps(BaseHandler):
    """Stands in for the network inside a real urllib opener: answers every https request."""

    handler_order = 100  # before urllib's own HTTPSHandler

    def __init__(self, status, body=b"", location=None):
        self.status, self.body, self.location = status, body, location
        self.requests = []

    def https_open(self, req):
        self.requests.append(req.full_url)
        headers = Message()
        if self.location:
            headers["Location"] = self.location
        response = addinfourl(io.BytesIO(self.body), headers, req.full_url, code=self.status)
        response.msg = "fake"
        return response


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_a_redirect_is_not_followed(status):
    fake = _FakeHttps(status, location="https://elsewhere.example/steal")
    opener = build_opener_without_redirects()
    opener.add_handler(fake)
    with pytest.raises(PipelineError) as raised:
        client(opener).check(request())
    assert (raised.value.kind, raised.value.detail) == ("http_status", f"HTTP {status}")
    assert fake.requests == [URL]


def test_the_real_opener_stack_reads_a_good_answer():
    fake = _FakeHttps(200, body=json.dumps(GOOD).encode())
    opener = build_opener_without_redirects()
    opener.add_handler(fake)
    assert client(opener).check(request()).verdict == "true"


def test_the_client_says_how_long_a_check_may_take():
    assert HttpPipelineClient(URL, KEY, opener=answering(GOOD)).max_seconds == 20


def test_get_client_follows_the_backend_setting(settings, monkeypatch):
    assert isinstance(get_client(), StubPipelineClient)
    opener = answering(GOOD)
    monkeypatch.setattr(clients, "_default_opener", lambda: opener)
    settings.PIPELINE_BACKEND = "http"
    settings.PIPELINE_URL = URL
    settings.PIPELINE_API_KEY = KEY
    http = get_client()
    assert isinstance(http, HttpPipelineClient)
    http.check(request())
    assert opener.calls[0][0].full_url == URL


def test_the_default_opener_is_forbidden_in_tests():
    with pytest.raises(AssertionError, match="real pipeline"):
        HttpPipelineClient(URL, KEY)
