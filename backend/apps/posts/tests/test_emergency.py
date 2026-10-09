from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.posts.emergency import is_active_emergency
from apps.posts.models import PostStatus

NOW = timezone.now()


def post(**overrides):
    fields = {
        "is_emergency": True,
        "emergency_demoted_at": None,
        "emergency_expires_at": NOW + timedelta(hours=1),
        "status": PostStatus.PENDING,
        "deleted_at": None,
    }
    return SimpleNamespace(**{**fields, **overrides})


def test_a_live_emergency_is_active():
    assert is_active_emergency(post(), NOW)


@pytest.mark.parametrize(
    "status", ["pending", "verified_true", "verified_false", "under_review", "published"]
)
def test_every_status_but_removed_keeps_the_priority(status):
    assert is_active_emergency(post(status=status), NOW)


@pytest.mark.parametrize(
    "overrides",
    [
        {"is_emergency": False},
        {"emergency_demoted_at": NOW - timedelta(minutes=1)},
        {"emergency_expires_at": NOW - timedelta(seconds=1)},
        {"emergency_expires_at": NOW},
        {"emergency_expires_at": None},
        {"status": PostStatus.REMOVED},
        {"deleted_at": NOW - timedelta(minutes=1)},
    ],
    ids=[
        "not_emergency",
        "demoted",
        "expired",
        "expires_this_instant",
        "no_expiry",
        "removed",
        "deleted",
    ],
)
def test_it_is_not_active(overrides):
    assert not is_active_emergency(post(**overrides), NOW)


def test_it_expires_at_the_exact_second():
    expires = NOW + timedelta(hours=24)
    assert is_active_emergency(
        post(emergency_expires_at=expires), expires - timedelta(microseconds=1)
    )
    assert not is_active_emergency(post(emergency_expires_at=expires), expires)
