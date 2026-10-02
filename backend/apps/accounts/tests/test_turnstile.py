"""verify_turnstile against a mocked siteverify (no network in tests)."""

import io
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs

import pytest

from apps.accounts import turnstile
from apps.accounts.turnstile import TurnstileResult, verify_turnstile

TOKEN = "XXXX.DUMMY.TOKEN.XXXX"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Siteverify:
    """Plays back one answer per call: a dict (JSON body), an exception, or raw bytes."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, bytes):
            return FakeResponse(answer)
        return FakeResponse(json.dumps(answer).encode())

    def form(self, index=0):
        return {k: v[0] for k, v in parse_qs(self.requests[index][0].data.decode()).items()}


@pytest.fixture
def siteverify(monkeypatch):
    def install(*answers):
        fake = Siteverify(*answers)
        monkeypatch.setattr(turnstile, "urlopen", fake)
        return fake

    return install


def http_error(code, body=b""):
    return HTTPError(turnstile.SITEVERIFY_URL, code, "error", {}, io.BytesIO(body))


def test_a_passing_token(siteverify, settings):
    fake = siteverify({"success": True, "hostname": "localhost", "action": "signup"})
    assert verify_turnstile(TOKEN, "203.0.113.7") is TurnstileResult.OK

    request, timeout = fake.requests[0]
    assert request.full_url == "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    assert request.get_method() == "POST"
    assert timeout == 5
    form = fake.form()
    assert form["secret"] == settings.TURNSTILE_SECRET_KEY
    assert form["response"] == TOKEN
    assert form["remoteip"] == "203.0.113.7"
    assert len(form["idempotency_key"]) == 36


def test_no_remote_ip_is_sent_when_unknown(siteverify):
    fake = siteverify({"success": True})
    verify_turnstile(TOKEN, "")
    assert "remoteip" not in fake.form()


@pytest.mark.parametrize(
    "codes",
    [["invalid-input-response"], ["timeout-or-duplicate"], ["missing-input-response"], [], None],
)
def test_a_rejected_token_fails(siteverify, codes):
    answer = {"success": False}
    if codes is not None:
        answer["error-codes"] = codes
    siteverify(answer)
    assert verify_turnstile(TOKEN, "") is TurnstileResult.FAILED


@pytest.mark.parametrize("code", ["invalid-input-secret", "missing-input-secret"])
def test_a_rejected_secret_is_unavailable_and_logged_by_name(siteverify, settings, caplog, code):
    siteverify({"success": False, "error-codes": [code]})
    with caplog.at_level(logging.WARNING, logger="apps.accounts.turnstile"):
        assert verify_turnstile(TOKEN, "") is TurnstileResult.UNAVAILABLE
    assert "TURNSTILE_SECRET_KEY" in caplog.text
    assert caplog.records[0].levelno == logging.ERROR
    assert settings.TURNSTILE_SECRET_KEY not in caplog.text
    assert TOKEN not in caplog.text


def test_cloudflare_internal_error_is_unavailable(siteverify):
    siteverify({"success": False, "error-codes": ["internal-error"]})
    assert verify_turnstile(TOKEN, "") is TurnstileResult.UNAVAILABLE


@pytest.mark.parametrize(
    "first",
    [URLError("dns"), TimeoutError("slow"), ConnectionResetError("reset"), http_error(502)],
    ids=["dns", "timeout", "reset", "http-502"],
)
def test_one_retry_with_the_same_key_after_a_network_error_or_5xx(siteverify, first):
    fake = siteverify(first, {"success": True})
    assert verify_turnstile(TOKEN, "") is TurnstileResult.OK
    assert len(fake.requests) == 2
    assert fake.form(0)["idempotency_key"] == fake.form(1)["idempotency_key"]


def test_two_network_errors_fail_closed(siteverify, caplog, settings):
    fake = siteverify(URLError("down"), TimeoutError("slow"))
    with caplog.at_level(logging.WARNING, logger="apps.accounts.turnstile"):
        assert verify_turnstile(TOKEN, "") is TurnstileResult.UNAVAILABLE
    assert len(fake.requests) == 2
    assert "unreachable" in caplog.text
    assert settings.TURNSTILE_SECRET_KEY not in caplog.text
    assert TOKEN not in caplog.text


def test_a_4xx_with_a_json_body_is_read(siteverify):
    body = json.dumps({"success": False, "error-codes": ["bad-request"]}).encode()
    siteverify(http_error(400, body))
    assert verify_turnstile(TOKEN, "") is TurnstileResult.FAILED


@pytest.mark.parametrize("answer", [b"<html>oops</html>", b"[1, 2]", http_error(403, b"nope")])
def test_an_unreadable_answer_fails_closed(siteverify, answer):
    siteverify(answer)
    assert verify_turnstile(TOKEN, "") is TurnstileResult.UNAVAILABLE


def test_tests_never_reach_the_real_siteverify():
    with pytest.raises(AssertionError, match="must not call Cloudflare"):
        verify_turnstile(TOKEN, "")
