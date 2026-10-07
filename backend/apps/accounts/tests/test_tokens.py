"""RumorZeroJWTTokenStrategy: locked, graceful rotation (ARCHITECTURE §7)."""

import threading
import time

import jwt
import pytest
from allauth.headless.tokens.strategies.jwt import internal
from allauth.headless.tokens.strategies.jwt.strategy import JWTTokenStrategy
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.accounts.cookies import revoke_refresh_token_session
from apps.accounts.tests.conftest import SITE_HEADERS, access_token_for, login, refresh_cookie
from apps.accounts.tests.factories import UserFactory
from apps.accounts.tokens import ROTATION_GRACE_SECONDS, RumorZeroJWTTokenStrategy

strategy = RumorZeroJWTTokenStrategy()


def logged_in_token():
    client = Client(headers=SITE_HEADERS)
    assert login(client, UserFactory().email).status_code == 200
    return refresh_cookie(client)


def claims(token):
    # Unverified on purpose: with the `clock` fixture, a new token's iat is "in the future" for
    # PyJWT, which checks it with the real clock.
    return jwt.decode(token, options={"verify_signature": False})


def refresh_state(token):
    session_key = internal.session_key_from_sid(claims(token)["sid"])
    return SessionStore(session_key)["headless_refresh_tokens"]


def jti_of(token):
    return claims(token)["jti"]


@pytest.mark.django_db
class TestRotation:
    def test_refresh_returns_a_new_pair_and_locks_the_session_row(self):
        token = logged_in_token()
        with CaptureQueriesContext(connection) as queries:
            access, new = strategy.refresh_token(token)

        assert new != token
        assert internal.decode_token(access, "access")["sub"]
        assert any(
            "FOR UPDATE" in query["sql"] and "django_session" in query["sql"]
            for query in queries.captured_queries
        )

    def test_the_used_token_gets_a_grace_period_then_dies(self, clock):
        token = logged_in_token()
        strategy.refresh_token(token)
        exp = refresh_state(token)[jti_of(token)]
        assert exp <= int(time.time()) + ROTATION_GRACE_SECONDS

        assert strategy.refresh_token(token) is not None
        clock["seconds"] = ROTATION_GRACE_SECONDS + 1
        assert strategy.refresh_token(token) is None

    def test_using_it_again_never_extends_the_grace(self, clock):
        token = logged_in_token()
        strategy.refresh_token(token)
        first_cap = refresh_state(token)[jti_of(token)]
        clock["seconds"] = 30
        strategy.refresh_token(token)
        assert refresh_state(token)[jti_of(token)] == first_cap

    def test_expired_ids_are_pruned(self, clock):
        token = logged_in_token()
        _, second = strategy.refresh_token(token)
        clock["seconds"] = ROTATION_GRACE_SECONDS + 1
        _, third = strategy.refresh_token(second)
        assert set(refresh_state(third)) == {jti_of(second), jti_of(third)}

    @pytest.mark.parametrize("token", ["", "garbage", "a.b.c"])
    def test_garbage_is_refused(self, token):
        assert strategy.refresh_token(token) is None

    def test_an_access_token_is_not_a_refresh_token(self):
        assert strategy.refresh_token(access_token_for(UserFactory())) is None

    def test_a_deleted_session_is_refused(self):
        token = logged_in_token()
        Session.objects.all().delete()
        assert strategy.refresh_token(token) is None

    def test_an_update_error_is_a_plain_failure(self, monkeypatch):
        token = logged_in_token()

        def fail(self, must_create=False):
            raise UpdateError

        monkeypatch.setattr(SessionStore, "save", fail)
        assert strategy.refresh_token(token) is None


# ---------- real concurrency: separate threads, separate database connections ----------


@pytest.fixture
def slow_rotation(monkeypatch):
    """Hold each refresh inside its critical section long enough for another one to collide."""
    original = internal.create_refresh_token

    def slow(user, session):
        token = original(user, session)
        time.sleep(0.3)
        return token

    monkeypatch.setattr(internal, "create_refresh_token", slow)
    return monkeypatch


def run_together(*tasks):
    barrier = threading.Barrier(len(tasks))
    results = [None] * len(tasks)
    errors = []

    def runner(index, task):
        try:
            barrier.wait()
            results[index] = task()
        except Exception as exc:  # collected and asserted on below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=runner, args=item) for item in enumerate(tasks)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert errors == []
    return results


@pytest.mark.django_db(transaction=True)
def test_two_refreshes_of_one_token_at_once_both_succeed(slow_rotation):
    token = logged_in_token()
    first, second = run_together(
        lambda: strategy.refresh_token(token), lambda: strategy.refresh_token(token)
    )
    assert first and second
    slow_rotation.undo()

    # Both tabs' new tokens are still valid: neither save overwrote the other.
    assert first[1] != second[1]
    assert strategy.refresh_token(first[1]) is not None
    assert strategy.refresh_token(second[1]) is not None


@pytest.mark.django_db(transaction=True)
def test_without_the_lock_one_tab_loses_its_token(slow_rotation):
    """Control run: allauth's own strategy, same timing. One new token is overwritten."""
    token = logged_in_token()
    plain = JWTTokenStrategy()
    first, second = run_together(
        lambda: plain.refresh_token(token), lambda: plain.refresh_token(token)
    )
    assert first and second
    slow_rotation.undo()

    survivors = [pair[1] for pair in (first, second) if strategy.refresh_token(pair[1])]
    assert len(survivors) == 1


@pytest.mark.django_db(transaction=True)
def test_a_refresh_racing_a_logout_leaves_no_live_token(slow_rotation):
    token = logged_in_token()

    def late_logout():
        time.sleep(0.1)  # the refresh holds the row lock by now; the delete waits for it
        return revoke_refresh_token_session(token)

    refreshed, revoked = run_together(lambda: strategy.refresh_token(token), late_logout)
    slow_rotation.undo()

    assert revoked is True
    assert Session.objects.count() == 0
    assert strategy.refresh_token(token) is None
    if refreshed:
        assert strategy.refresh_token(refreshed[1]) is None


@pytest.mark.django_db(transaction=True)
def test_a_refresh_after_a_logout_fails_cleanly(slow_rotation):
    token = logged_in_token()

    def late_refresh():
        time.sleep(0.1)
        return strategy.refresh_token(token)

    revoked, refreshed = run_together(lambda: revoke_refresh_token_session(token), late_refresh)
    assert revoked is True
    assert refreshed is None
