"""`POST /api/internal/tick/` (ARCHITECTURE §6, §9): the hourly pipeline sweeper cron-job.org
calls. It needs the cron secret, takes a small batch and answers quickly."""

import time

import pytest
from django.urls import reverse

from apps.pipeline import processor
from apps.pipeline.tests.conftest import FakeClient, fact, pipeline_cfg  # noqa: F401  (fixture)
from apps.posts.models import Post, PostStatus

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("pipeline_cfg")]

CRON_SECRET = "cron-secret-for-tests"
URL = "/api/internal/tick/"


@pytest.fixture
def cron_headers(settings):
    settings.INTERNAL_CRON_SECRET = CRON_SECRET
    return {"X-RZ-Cron-Secret": CRON_SECRET}


def tick(client, headers):
    return client.post(URL, headers=headers)


def test_the_tick_lives_under_api_internal():
    assert reverse("internal-tick") == URL


@pytest.mark.parametrize("headers", [{}, {"X-RZ-Cron-Secret": "wrong"}, {"X-RZ-Cron-Secret": ""}])
def test_the_tick_needs_the_cron_secret_and_does_nothing_without_it(client, cron_headers, headers):
    post = fact("A claim #true")
    response = tick(client, headers)
    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"
    after = Post.objects.get(pk=post.pk)
    assert (after.status, after.pipeline_attempts) == (PostStatus.PENDING, 0)


def test_a_non_ascii_secret_is_a_403_not_a_crash(client, cron_headers):
    assert client.post(URL, HTTP_X_RZ_CRON_SECRET="séc").status_code == 403


def test_get_is_not_allowed(client, cron_headers):
    assert client.get(URL, headers=cron_headers).status_code == 405


def test_with_nothing_waiting_it_answers_zero(client, cron_headers):
    response = tick(client, cron_headers)
    assert response.status_code == 200
    assert response.json() == {"processed": 0}
    assert "no-store" in response["Cache-Control"]


def test_a_stale_token_is_ignored_because_the_tick_authenticates_no_user(client, cron_headers):
    headers = {**cron_headers, "Authorization": "Bearer not-a-real-token"}
    assert tick(client, headers).status_code == 200


def test_a_backlog_of_twelve_takes_two_ticks_of_ten_and_two(client, cron_headers):
    posts = [fact(f"Claim {n} #true", age_seconds=100 - n) for n in range(12)]
    assert tick(client, cron_headers).json() == {"processed": 10}
    assert tick(client, cron_headers).json() == {"processed": 2}
    assert tick(client, cron_headers).json() == {"processed": 0}
    statuses = Post.objects.filter(pk__in=[p.pk for p in posts]).values_list("status", flat=True)
    assert set(statuses) == {PostStatus.VERIFIED_TRUE}


def test_ten_posts_with_the_stub_take_far_less_than_thirty_seconds(client, cron_headers):
    for n in range(10):
        fact(f"Claim {n} #false", age_seconds=100 - n)
    started = time.monotonic()
    response = tick(client, cron_headers)
    elapsed = time.monotonic() - started
    assert response.json() == {"processed": 10}
    assert elapsed < 30
    assert elapsed < 5  # what it really takes; a slower run is a regression worth a look


def test_a_pipeline_that_may_take_25_seconds_gets_one_post_per_tick(
    client, cron_headers, monkeypatch
):
    """The first post is always taken; another only if its worst case still fits the budget."""
    for n in range(3):
        fact(f"Claim {n}", age_seconds=10 - n)
    monkeypatch.setattr(processor, "get_client", lambda: FakeClient(max_seconds=25))
    assert tick(client, cron_headers).json() == {"processed": 1}
