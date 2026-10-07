import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.scrubber import DEFAULT_DENYLIST
from sentry_sdk.utils import AnnotatedValue

from rumor_zero.sentry import init_sentry, sentry_options

DSN = "https://public@example.invalid/1"  # never contacted: sentry_sdk.init is replaced below
RELAY_HEADERS = ("X-Rz-Proxy-Secret", "X-Rz-Cron-Secret", "X-Rz-Client-Ip")
# A live password-reset link travels in this header (Part 2).
RESET_KEY_HEADER = "X-Password-Reset-Key"


def test_init_passes_the_hardened_options(monkeypatch):
    captured = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **options: captured.update(options))

    init_sentry(dsn=DSN, environment="test", traces_sample_rate=0.0)

    assert captured["dsn"] == DSN
    assert captured["environment"] == "test"
    assert captured["traces_sample_rate"] == 0.0
    assert captured["send_default_pii"] is False
    assert captured["max_request_body_size"] == "never"
    assert captured["include_local_variables"] is False
    assert any(isinstance(item, DjangoIntegration) for item in captured["integrations"])

    denylist = captured["event_scrubber"].denylist
    for header in (
        "x-rz-proxy-secret",
        "x-rz-cron-secret",
        "x-rz-client-ip",
        "x-password-reset-key",
    ):
        assert header in denylist
    assert "authorization" in denylist  # the library defaults are kept


def test_extending_the_denylist_does_not_mutate_the_library_default():
    sentry_options(DSN, "test", 0.0)
    assert "x-rz-proxy-secret" not in DEFAULT_DENYLIST


def test_scrubber_filters_the_relay_headers_and_keeps_harmless_ones():
    scrubber = sentry_options(DSN, "test", 0.0)["event_scrubber"]
    event = {
        "request": {
            "headers": {
                "X-Rz-Proxy-Secret": "proxy-secret-value",
                "X-Rz-Cron-Secret": "cron-secret-value",
                "X-Rz-Client-Ip": "203.0.113.7",
                "X-Password-Reset-Key": "reset-key-value",
                "Authorization": "Bearer token-value",
                "Accept": "application/json",
            }
        }
    }

    scrubber.scrub_event(event)

    headers = event["request"]["headers"]
    for name in (*RELAY_HEADERS, RESET_KEY_HEADER, "Authorization"):
        assert isinstance(headers[name], AnnotatedValue), name
    assert headers["Accept"] == "application/json"
    leaked = repr(headers)
    for value in (
        "proxy-secret-value",
        "cron-secret-value",
        "203.0.113.7",
        "token-value",
        "reset-key-value",
    ):
        assert value not in leaked
