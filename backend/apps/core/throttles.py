from rest_framework.throttling import ScopedRateThrottle


class IPScopedRateThrottle(ScopedRateThrottle):
    """A scoped throttle counted per client IP, signed in or not.

    DRF's `ScopedRateThrottle` keys on the user once someone is authenticated; this one always keys
    on the address `ClientIPMiddleware` put in REMOTE_ADDR, so a signed-in client can't multiply
    its allowance with accounts, and people behind one address share it (ARCHITECTURE §3).
    """

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
