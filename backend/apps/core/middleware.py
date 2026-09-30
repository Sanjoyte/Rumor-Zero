import hmac
import ipaddress

from django.conf import settings


def _parse_ip(value):
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


class ClientIPMiddleware:
    """Set REMOTE_ADDR to the real client address (ARCHITECTURE §1).

    The API relay sends X-RZ-Client-IP with X-RZ-Proxy-Secret. The address is trusted only when
    the secret matches; otherwise the right-most X-Forwarded-For entry (added by the platform's
    own proxy) is used. Both X-RZ-* headers are removed from request.META so no later code, log
    line or error report can see them.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        secret = request.META.pop("HTTP_X_RZ_PROXY_SECRET", "")
        client_ip = request.META.pop("HTTP_X_RZ_CLIENT_IP", "")

        if self._secret_matches(secret):
            address = _parse_ip(client_ip) or self._forwarded_address(request)
        else:
            address = self._forwarded_address(request)
        if address:
            request.META["REMOTE_ADDR"] = address
        return self.get_response(request)

    @staticmethod
    def _secret_matches(secret):
        expected = settings.PROXY_SHARED_SECRET
        return bool(expected) and hmac.compare_digest(secret.encode(), expected.encode())

    @staticmethod
    def _forwarded_address(request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if not forwarded_for:
            return None
        # Only the right-most entry is trustworthy; everything left of it is client-supplied.
        return _parse_ip(forwarded_for.rsplit(",", 1)[-1])
