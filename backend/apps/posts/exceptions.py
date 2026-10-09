"""API errors for posts. They are `APIException`s so the core handler shapes them as
`{"detail", "code"}` (a validation error would carry no code), and DRF adds `Retry-After` for any
exception that has a `wait` (rest_framework/views.py, `exception_handler`)."""

import math

from rest_framework.exceptions import APIException


class EmergencyUnavailableError(APIException):
    status_code = 400
    default_code = "emergency_unavailable"
    default_detail = "Emergency posts aren't available yet."


class NotAuthorError(APIException):
    status_code = 403
    default_code = "not_author"
    default_detail = "Only the author can do that."


class FactPostsPausedError(APIException):
    status_code = 403
    default_code = "fact_posts_paused"
    default_detail = "Fact posts are paused right now. You can still post opinions."


class FactQuotaExceededError(APIException):
    """429 with `Retry-After`: a rate in a time window with a known retry time. Not a `Throttled`
    subclass, which would append "Expected available in N seconds."; the code tells it apart from
    the `post_create` throttle's 429 `throttled`."""

    status_code = 429
    default_code = "fact_quota_exceeded"

    def __init__(self, *, limit, next_slot_at, now):
        self.wait = max(1, math.ceil((next_slot_at - now).total_seconds()))
        super().__init__(
            f"You've used all {limit} of your fact posts for the last 24 hours. "
            f"You can post another at {next_slot_at:%H:%M} UTC."
        )
