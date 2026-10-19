"""`GET /api/v1/users/{username}/reputation/`: an account's public credibility summary
(ARCHITECTURE §9). Public, uncached, never authenticated, two queries, and nothing private."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import User
from apps.moderation import services as moderation
from apps.posts import services as post_services
from apps.posts.models import PostStatus, PostType
from apps.reputation.models import EventKind as K
from apps.reputation.tests.factories import (
    FALSE_95,
    TRUE_95,
    EventFactory,
    PostFactory,
    VerifiedUserFactory,
    label_by_pipeline,
    moderator_user,
    open_reports,
    pending_fact,
    reported_fact,
    reposted,
    reversal_of,
)

pytestmark = pytest.mark.django_db

KEYS = {"score", "sample", "verified", "false", "removed", "recent"}
RECENT_KEYS = {"kind", "label", "post_id", "created_at", "reversed"}


def url(name):
    return f"/api/v1/users/{name}/reputation/"


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada")


def test_the_shape_of_a_new_account(api_client, ada):
    response = api_client.get(url("ada"))
    assert response.status_code == 200
    assert response.json() == {
        "score": None,
        "sample": 0,
        "verified": 0,
        "false": 0,
        "removed": 0,
        "recent": [],
    }


def test_the_score_is_hidden_until_three_events_count(api_client, ada):
    for i in range(3):
        label_by_pipeline(pending_fact(ada), TRUE_95)
        body = api_client.get(url("ada")).json()
        assert body["sample"] == i + 1
        assert body["score"] == (None if i < 2 else 62)
    assert set(body) == KEYS


def test_the_counts_are_status_based_and_include_deleted_posts(api_client, ada):
    """The same rule as the profile header's counters, so the two never disagree."""
    for status, deleted in [
        (PostStatus.VERIFIED_TRUE, False),
        (PostStatus.VERIFIED_TRUE, True),
        (PostStatus.VERIFIED_FALSE, False),
        (PostStatus.VERIFIED_FALSE, True),
        (PostStatus.REMOVED, False),
        (PostStatus.REMOVED, True),
        (PostStatus.REMOVED, True),
        (PostStatus.PENDING, False),
    ]:
        PostFactory(author=ada, post_type=PostType.FACT, status=status, deleted=deleted)
    PostFactory(post_type=PostType.FACT, status=PostStatus.VERIFIED_TRUE)  # someone else's
    body = api_client.get(url("ada")).json()
    assert (body["verified"], body["false"], body["removed"]) == (2, 2, 3)
    profile = api_client.get("/api/v1/users/ada/").json()["counts"]
    assert (profile["verified"], profile["false"]) == (body["verified"], body["false"])


def test_recent_lists_own_post_events_newest_first_with_their_reversal(api_client, ada):
    true_post = pending_fact(ada)
    label_by_pipeline(true_post, TRUE_95)
    removed = pending_fact(ada)
    moderation.remove_post(removed.pk, moderator=moderator_user())
    moderation.file_appeal(author=ada, post_id=removed.pk)
    moderation.restore_post(removed.pk, moderator=moderator_user())
    recent = api_client.get(url("ada")).json()["recent"]
    assert [row["kind"] for row in recent] == [K.POST_REMOVED, K.FACT_TRUE]
    assert all(set(row) == RECENT_KEYS for row in recent)
    assert recent[0] == {
        "kind": "post_removed",
        "label": "Post removed by a moderator",
        "post_id": str(removed.pk),
        "created_at": recent[0]["created_at"],
        "reversed": True,
    }
    assert recent[1]["reversed"] is False
    assert recent[1]["label"] == "Fact verified true"
    assert recent[0]["created_at"] > recent[1]["created_at"]


def test_recent_never_shows_reversal_repost_or_report_rows(api_client, ada):
    """User decision 2: own-post events only."""
    other = pending_fact()
    reposted(other, ada)
    label_by_pipeline(other, FALSE_95)
    reported = reported_fact()
    open_reports(reported, reporter=ada)
    moderation.mark_false(reported.pk, moderator=moderator_user())
    mine = EventFactory(user=ada, kind=K.FACT_TRUE)
    reversal_of(mine)
    kinds = {row["kind"] for row in api_client.get(url("ada")).json()["recent"]}
    assert kinds == {K.FACT_TRUE}


def test_recent_holds_at_most_ten(api_client, ada):
    start = timezone.now() - timedelta(days=1)
    for i in range(13):
        EventFactory(user=ada, kind=K.FACT_FALSE, created_at=start + timedelta(minutes=i))
    recent = api_client.get(url("ada")).json()["recent"]
    assert len(recent) == 10
    times = [row["created_at"] for row in recent]
    assert times == sorted(times, reverse=True)


def test_a_deleted_post_keeps_its_event_but_loses_its_link(api_client, ada):
    post = pending_fact(ada)
    label_by_pipeline(post, FALSE_95)
    post_services.delete_post(post_id=post.pk, user=ada)
    [row] = api_client.get(url("ada")).json()["recent"]
    assert (row["kind"], row["post_id"]) == ("fact_false", None)


def test_nothing_private_is_in_the_answer(api_client, ada):
    reporter = VerifiedUserFactory()
    post = reported_fact(ada)
    open_reports(post, reporter=reporter)
    entry = moderation.mark_false(post.pk, moderator=moderator_user(), notes="internal note")
    text = api_client.get(url("ada")).content.decode()
    for secret in (
        reporter.username,
        str(reporter.pk),
        str(entry.pk),
        entry.moderator.username,
        "internal note",
        "score_after",
        "positive",
        "negative",
        ada.email,
    ):
        assert secret not in text


@pytest.mark.parametrize("name", ["nobody", "x", "bad name!", "%00", "a" * 65])
def test_an_unknown_or_malformed_name_is_a_json_404(api_client, name):
    response = api_client.get(url(name))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_an_inactive_account_is_a_404(api_client):
    VerifiedUserFactory(username="gone", is_active=False)
    assert api_client.get(url("gone")).status_code == 404


def test_the_lookup_is_case_insensitive(api_client, ada):
    assert api_client.get(url("ADA")).status_code == 200


def test_it_is_never_cached(api_client, ada):
    assert "no-store" in api_client.get(url("ada"))["Cache-Control"]


def test_a_stale_token_is_not_a_401(api_client, ada):
    """It never authenticates: the answer doesn't depend on who asks."""
    response = api_client.get(url("ada"), HTTP_AUTHORIZATION="Bearer not-a-token")
    assert response.status_code == 200


def queries(client, name="ada"):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(url(name)).status_code == 200
    return len(captured)


def test_two_queries_however_many_events(api_client, ada, auth_client):
    viewer = auth_client(VerifiedUserFactory())
    EventFactory(user=ada)
    one = (queries(api_client), queries(viewer))
    for i in range(30):
        post = PostFactory(author=ada, post_type=PostType.FACT, status=PostStatus.VERIFIED_TRUE)
        EventFactory(user=ada, post=post, created_at=timezone.now() + timedelta(seconds=i))
    User.objects.filter(pk=ada.pk).update(reputation_sample=31)
    many = (queries(api_client), queries(viewer))
    assert one == many == (2, 2)


def test_the_profile_and_the_user_rows_carry_the_live_score(api_client, ada):
    """The `reputation` block of the profile and of follower rows is the stored score (Part 6's
    shape, now fed by the ledger)."""
    from apps.social.tests.factories import FollowFactory

    for _ in range(3):
        label_by_pipeline(pending_fact(ada), TRUE_95)
    expected = {"score": 62, "sample": 3}
    assert api_client.get("/api/v1/users/ada/").json()["reputation"] == expected
    FollowFactory(follower=ada, following=VerifiedUserFactory(username="bob"))
    [row] = api_client.get("/api/v1/users/bob/followers/").json()["results"]
    assert row["reputation"] == expected
    assert row["counts"] == {"verified": 3}
