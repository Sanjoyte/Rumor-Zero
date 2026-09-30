import logging

import pytest
from django.core.cache.backends.locmem import LocMemCache
from django.urls import reverse

from apps.core import views

pytestmark = pytest.mark.django_db

CRON_SECRET = "cron-secret-for-tests"


@pytest.fixture
def cron_headers(settings):
    settings.INTERNAL_CRON_SECRET = CRON_SECRET
    return {"X-RZ-Cron-Secret": CRON_SECRET}


def test_health_returns_ok_with_zero_queries(client, django_assert_num_queries):
    with django_assert_num_queries(0):
        response = client.get(reverse("health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "no-store" in response["Cache-Control"]


def test_health_stays_at_zero_queries_with_a_logged_in_session(
    client, user, django_assert_num_queries
):
    client.force_login(user)
    with django_assert_num_queries(0):
        response = client.get(reverse("health"))
    assert response.status_code == 200


def test_health_path_is_under_api():
    assert reverse("health") == "/api/health/"
    assert reverse("health-deep") == "/api/health/deep/"


@pytest.mark.parametrize("headers", [{}, {"X-RZ-Cron-Secret": "wrong"}, {"X-RZ-Cron-Secret": ""}])
def test_deep_health_needs_the_cron_secret(client, cron_headers, headers):
    response = client.get(reverse("health-deep"), headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_deep_health_with_a_non_ascii_secret_is_403_not_a_crash(client, cron_headers):
    response = client.get(reverse("health-deep"), HTTP_X_RZ_CRON_SECRET="séc")
    assert response.status_code == 403


def test_deep_health_ok_with_the_secret_runs_exactly_one_query(
    client, cron_headers, django_assert_num_queries
):
    with django_assert_num_queries(1):
        response = client.get(reverse("health-deep"), headers=cron_headers)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "cache": "ok"}


def test_deep_health_reports_a_broken_cache_as_503(client, cron_headers, monkeypatch, caplog):
    def broken_set(*args, **kwargs):
        raise ConnectionError("redis://user:hunter2@cache.internal is down")

    monkeypatch.setattr(LocMemCache, "set", broken_set)
    with caplog.at_level(logging.WARNING):
        response = client.get(reverse("health-deep"), headers=cron_headers)

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "ok", "cache": "error"}
    # Only the exception class is logged; its message can hold connection strings.
    assert "ConnectionError" in caplog.text
    assert "hunter2" not in caplog.text
    assert "hunter2" not in response.content.decode()


def test_deep_health_reports_a_broken_database_as_503(client, cron_headers, monkeypatch):
    def broken_check():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(views, "_check_database", broken_check)
    response = client.get(reverse("health-deep"), headers=cron_headers)
    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "error", "cache": "ok"}
