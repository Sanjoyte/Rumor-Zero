"""Sentry initialisation. `send_default_pii=False` alone is not enough (ARCHITECTURE §12)."""

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

# Header names as the scrubber compares them (lowercased). The client-IP and secret headers are
# also removed from request.META by ClientIPMiddleware; this is the second line of defence.
# x-password-reset-key is a live password-reset link (the reset page's key pre-check header).
EXTRA_DENYLIST = [
    "x-rz-proxy-secret",
    "x-rz-cron-secret",
    "x-rz-client-ip",
    "x-password-reset-key",
]


def sentry_options(dsn, environment, traces_sample_rate):
    return {
        "dsn": dsn,
        "integrations": [DjangoIntegration()],
        "send_default_pii": False,
        "max_request_body_size": "never",
        "include_local_variables": False,
        "event_scrubber": EventScrubber(denylist=DEFAULT_DENYLIST + EXTRA_DENYLIST),
        "environment": environment,
        "traces_sample_rate": traces_sample_rate,
    }


def init_sentry(dsn, environment, traces_sample_rate):
    sentry_sdk.init(**sentry_options(dsn, environment, traces_sample_rate))
