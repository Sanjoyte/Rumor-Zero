import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from apps.core.middleware import ClientIPMiddleware

RELAY_SECRET = "relay-secret-for-tests"
PROXY_ADDRESS = "10.0.0.1"


@pytest.fixture(autouse=True)
def _proxy_secret(settings):
    settings.PROXY_SHARED_SECRET = RELAY_SECRET


def run(**meta):
    """Send a request through the middleware and return the request the view received."""
    seen = {}

    def view(request):
        seen["request"] = request
        return HttpResponse()

    request = RequestFactory().get("/", REMOTE_ADDR=PROXY_ADDRESS, **meta)
    ClientIPMiddleware(view)(request)
    return seen["request"]


def relay(secret=RELAY_SECRET, ip="203.0.113.7", **meta):
    return run(HTTP_X_RZ_PROXY_SECRET=secret, HTTP_X_RZ_CLIENT_IP=ip, **meta)


def test_client_ip_is_used_when_the_secret_matches():
    assert relay().META["REMOTE_ADDR"] == "203.0.113.7"


def test_ipv6_client_ip_is_used_when_the_secret_matches():
    assert relay(ip="2001:db8::1").META["REMOTE_ADDR"] == "2001:db8::1"


def test_wrong_secret_ignores_the_client_ip_and_uses_the_rightmost_forwarded_entry():
    request = relay(secret="wrong", HTTP_X_FORWARDED_FOR="198.51.100.9, 192.0.2.44")
    assert request.META["REMOTE_ADDR"] == "192.0.2.44"


def test_missing_secret_ignores_the_client_ip():
    request = run(HTTP_X_RZ_CLIENT_IP="203.0.113.7")
    assert request.META["REMOTE_ADDR"] == PROXY_ADDRESS


def test_missing_secret_and_no_forwarded_header_keeps_remote_addr():
    assert run().META["REMOTE_ADDR"] == PROXY_ADDRESS


def test_a_spoofed_leftmost_forwarded_entry_never_wins():
    request = run(HTTP_X_FORWARDED_FOR="6.6.6.6, 192.0.2.44")
    assert request.META["REMOTE_ADDR"] == "192.0.2.44"


def test_invalid_rightmost_forwarded_entry_leaves_remote_addr_alone():
    request = run(HTTP_X_FORWARDED_FOR="6.6.6.6, not-an-ip")
    assert request.META["REMOTE_ADDR"] == PROXY_ADDRESS


def test_valid_secret_with_an_invalid_ip_falls_back():
    assert relay(ip="not-an-ip").META["REMOTE_ADDR"] == PROXY_ADDRESS
    fallback = relay(ip="not-an-ip", HTTP_X_FORWARDED_FOR="192.0.2.44")
    assert fallback.META["REMOTE_ADDR"] == "192.0.2.44"


def test_non_ascii_secret_is_untrusted_not_a_crash():
    request = relay(secret="séc")
    assert request.META["REMOTE_ADDR"] == PROXY_ADDRESS


def test_an_empty_configured_secret_never_matches(settings):
    settings.PROXY_SHARED_SECRET = ""
    assert relay(secret="").META["REMOTE_ADDR"] == PROXY_ADDRESS


@pytest.mark.parametrize("secret", [RELAY_SECRET, "wrong", ""])
def test_both_relay_headers_are_removed_from_the_request(secret):
    request = relay(secret=secret)
    assert "HTTP_X_RZ_PROXY_SECRET" not in request.META
    assert "HTTP_X_RZ_CLIENT_IP" not in request.META
    assert RELAY_SECRET not in repr(request.META)
