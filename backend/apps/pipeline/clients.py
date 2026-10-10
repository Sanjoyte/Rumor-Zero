"""Pipeline clients (ARCHITECTURE §6): the deterministic stub and the HTTP client for a real one.

`get_client()` picks one from `settings.PIPELINE_BACKEND`. Both answer a `PipelineRequest` with a
`PipelineResult` or raise `PipelineError`; `max_seconds` is how long one `check` may take at worst
(the tick uses it to stay inside cron-job.org's 30 s).

This is the only module of `apps/pipeline` that may open a connection, and only to the configured
`PIPELINE_URL`: the sources in a request are passed on as text and never fetched (§4c).
"""

import hashlib
import json
import re
import time
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings

from apps.pipeline.contract import ContractError, PipelineRequest, PipelineResult

TIMEOUT_SECONDS = 20  # the whole call (§3)
SOCKET_TIMEOUT_SECONDS = 10  # each connect, send or read
MAX_RESPONSE_BYTES = 64 * 1024
_CHUNK_BYTES = 8192


class PipelineError(Exception):
    """A failed check. `kind` is one of `timeout`, `network`, `http_status`, `bad_response`,
    `contract`, `error` (anything unexpected) or `lease_expired` (the processor's: an earlier try
    died mid-call); `detail` is our own short text, never a response body or the key."""

    def __init__(self, kind, detail=""):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind
        self.detail = detail


class PipelineClient(Protocol):
    max_seconds: float

    def check(self, request: PipelineRequest) -> PipelineResult: ...


# The first of these tags in the text decides; a tag counts only as a whole word ("#True." yes,
# "#trueish" no). ASCII only, so no Unicode letter or digit is taken for part of a tag.
_TAG = re.compile(r"#(true|false|unsure)\b", re.IGNORECASE | re.ASCII)
_TAG_RESULTS = {"true": ("true", 95), "false": ("false", 92), "unsure": ("inconclusive", 40)}


class StubPipelineClient:
    """The built-in fake (`PIPELINE_BACKEND=stub`): deterministic, instant, and blind to `sources`.

    `#true` → (true, 95), `#false` → (false, 92), `#unsure` → (inconclusive, 40); any other text
    gets a confidence of 50–99 and true or false from the SHA-256 of its UTF-8 bytes (never
    Python's `hash()`, which changes with every process). Running it in production lets an author
    label their own post: a launch decision for Part 17 (§6).
    """

    max_seconds = 0

    def check(self, request):
        match = _TAG.search(request.content)
        if match:
            tag = match.group(1).lower()
            verdict, confidence = _TAG_RESULTS[tag]
            return PipelineResult(verdict, confidence, {"stub": True, "rule": f"#{tag}"})
        digest = hashlib.sha256(request.content.encode("utf-8")).digest()
        confidence = 50 + int.from_bytes(digest[:2], "big") % 50
        verdict = "true" if digest[2] % 2 == 0 else "false"
        return PipelineResult(verdict, confidence, {"stub": True, "rule": "hash"})


class _NoRedirect(HTTPRedirectHandler):
    """Follow no redirect: urllib then raises `HTTPError` with the 3xx code."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def build_opener_without_redirects():
    return build_opener(_NoRedirect())


def _default_opener():
    # A separate name so the test suite can forbid real connections (root conftest).
    return build_opener_without_redirects()


class HttpPipelineClient:
    """A real pipeline (`PIPELINE_BACKEND=http`, future): `POST PIPELINE_URL` with
    `{post_id, content, sources}` and `Authorization: Bearer PIPELINE_API_KEY`; the answer must be
    `{verdict, confidence_score, raw_result}`. Standard library only, like Turnstile's check."""

    def __init__(self, url, api_key, *, timeout=TIMEOUT_SECONDS, opener=None):
        self.url = url
        self._api_key = api_key
        self.timeout = timeout
        self.max_seconds = timeout
        self._opener = opener or _default_opener()

    def __repr__(self):
        return f"HttpPipelineClient(url={self.url!r})"  # never the key

    def check(self, request):
        started = time.monotonic()
        http_request = Request(
            self.url,
            data=json.dumps(request.to_json()).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        try:
            socket_timeout = min(SOCKET_TIMEOUT_SECONDS, self.timeout)
            with self._opener.open(http_request, timeout=socket_timeout) as response:
                body = self._read(response, started)
        except PipelineError:
            raise
        except HTTPError as exc:  # any status outside 2xx, a redirect included
            raise PipelineError("http_status", f"HTTP {exc.code}") from None
        except TimeoutError:
            raise PipelineError("timeout", "no answer in time") from None
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise PipelineError("timeout", "no answer in time") from None
            raise PipelineError("network", type(exc.reason).__name__) from None
        except OSError as exc:
            raise PipelineError("network", type(exc).__name__) from None
        try:
            payload = json.loads(body.decode("utf-8"))
        except ValueError:  # UnicodeDecodeError and JSONDecodeError both are
            raise PipelineError("bad_response", "the answer is not JSON") from None
        if not isinstance(payload, dict):
            raise PipelineError("bad_response", "the answer is not a JSON object")
        try:
            return PipelineResult.from_json(payload)
        except ContractError as exc:
            raise PipelineError("contract", str(exc)) from None

    def _read(self, response, started):
        """The body in chunks, within the size cap and the call's total time (each read can
        still block for one socket timeout; the DNS lookup has no timeout at all)."""
        chunks, size = [], 0
        while True:
            if time.monotonic() - started > self.timeout:
                raise PipelineError("timeout", f"no full answer in {self.timeout} s")
            chunk = response.read(_CHUNK_BYTES)
            if not chunk:
                return b"".join(chunks)
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise PipelineError("bad_response", "the answer is larger than 64 KB")
            chunks.append(chunk)


def get_client():
    """The client `settings.PIPELINE_BACKEND` names (read on every call, so tests can switch)."""
    if settings.PIPELINE_BACKEND == "http":
        return HttpPipelineClient(settings.PIPELINE_URL, settings.PIPELINE_API_KEY)
    return StubPipelineClient()
