"""`GET /api/v1/me/reputation/events/`: your whole ledger (ARCHITECTURE §9), reversals included,
with the appeal state on your own negative rows. Only ever your own."""

import base64
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.moderation import services as moderation
from apps.posts import services as post_services
from apps.reputation.models import EventKind as K
from apps.reputation.tests.factories import (
    FALSE_95,
    TRUE_95,
    EventFactory,
    VerifiedUserFactory,
    label_by_pipeline,
    moderator_user,
    open_reports,
    pending_fact,
    reported_fact,
    reposted,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/reputation/events/"
ROW_KEYS = {
    "id",
    "kind",
    "label",
    "positive",
    "negative",
    "score_after",
    "created_at",
    "post_id",
    "reverses",
    "reversed",
    "appeal",
}


def page(client, **params):
    response = client.get(URL, params)
    assert response.status_code == 200
    return response.json()


def test_anonymous_is_a_401(api_client):
    assert api_client.get(URL).status_code == 401


def test_only_your_own_rows(auth_client):
    me, other = VerifiedUserFactory(), VerifiedUserFactory()
    EventFactory(user=me)
    EventFactory(user=other)
    EventFactory(user=other)
    rows = page(auth_client(me))["results"]
    assert len(rows) == 1


def test_a_relabel_shows_every_row_with_its_reversal(auth_client):
    author = VerifiedUserFactory()
    post = pending_fact(author)
    label_by_pipeline(post, FALSE_95)
    moderation.file_appeal(author=author, post_id=post.pk)
    moderation.mark_verified(post.pk, moderator=moderator_user())
    body = page(auth_client(author))
    assert body["next_cursor"] is None
    added, reversal, original = body["results"]  # newest first
    assert all(set(row) == ROW_KEYS for row in body["results"])
    assert (original["kind"], original["positive"], original["negative"]) == (
        "fact_false",
        "0.00",
        "1.00",
    )
    assert original["reversed"] is True
    assert original["appeal"] is None  # it no longer stands
    assert original["label"] == "Fact labelled FALSE"
    assert (reversal["kind"], reversal["negative"], reversal["reverses"]) == (
        "reversal",
        "-1.00",
        original["id"],
    )
    assert reversal["label"] == "Reversed: Fact labelled FALSE"
    assert reversal["reversed"] is False
    assert reversal["appeal"] is None
    assert (added["kind"], added["positive"], added["score_after"]) == ("fact_true", "1.00", 55)
    assert [row["score_after"] for row in (original, reversal, added)] == [45, 50, 55]
    assert {row["post_id"] for row in body["results"]} == {str(post.pk)}


def test_report_and_repost_rows_are_listed_with_their_weights(auth_client):
    me = VerifiedUserFactory()
    reposted_post = pending_fact()
    reposted(reposted_post, me)
    label_by_pipeline(reposted_post, TRUE_95)
    reported = reported_fact()
    open_reports(reported, reporter=me)
    moderation.mark_false(reported.pk, moderator=moderator_user())
    credit, repost = page(auth_client(me))["results"]
    assert (credit["kind"], credit["positive"], credit["label"]) == (
        "report_upheld",
        "0.25",
        "Report upheld by a moderator",
    )
    assert (repost["kind"], repost["positive"]) == ("repost_true", "0.25")
    assert credit["appeal"] is None and repost["appeal"] is None


def test_a_negative_repost_row_has_no_appeal_of_its_own(auth_client):
    """Only the author can ask another look at a post: a repost of a FALSE post, a removed one or
    an emergency FALSE has `appeal: null`."""
    me = VerifiedUserFactory()
    for result, emergency in ((FALSE_95, False), (FALSE_95, True)):
        # An expired emergency: an active one would go to review (Part 11C).
        post = pending_fact(
            is_emergency=emergency,
            emergency_expires_at=timezone.now() - timedelta(minutes=1) if emergency else None,
        )
        reposted(post, me)
        label_by_pipeline(post, result)
    removed = pending_fact()
    reposted(removed, me)
    moderation.remove_post(removed.pk, moderator=moderator_user())
    rows = page(auth_client(me))["results"]
    assert {row["kind"] for row in rows} == {
        "repost_false",
        "repost_emergency_false",
        "repost_removed",
    }
    assert all(row["appeal"] is None for row in rows)


def post_object(client, post_id):
    response = client.get(f"/api/v1/posts/{post_id}/")
    assert response.status_code == 200
    return response.json()


def test_the_appeal_block_follows_the_post_objects_rule(auth_client):
    author = VerifiedUserFactory()
    client = auth_client(author)
    falsy = pending_fact(author)
    label_by_pipeline(falsy, FALSE_95)
    removed = pending_fact(author)
    moderation.remove_post(removed.pk, moderator=moderator_user())
    truthy = pending_fact(author)
    label_by_pipeline(truthy, TRUE_95)

    rows = {row["post_id"]: row for row in page(client)["results"]}
    assert rows[str(truthy.pk)]["appeal"] is None  # not negative
    for post in (falsy, removed):
        block = rows[str(post.pk)]["appeal"]
        shown = post_object(client, post.pk)
        assert block == {"status": None, "can_appeal": True}
        assert block["can_appeal"] is shown["can_appeal"]

    moderation.file_appeal(author=author, post_id=falsy.pk)
    rows = {row["post_id"]: row for row in page(client)["results"]}
    assert rows[str(falsy.pk)]["appeal"] == {"status": "open", "can_appeal": False}
    assert post_object(client, falsy.pk)["can_appeal"] is False

    moderation.mark_false(falsy.pk, moderator=moderator_user())  # upheld
    rows = {row["post_id"]: row for row in page(client)["results"]}
    assert rows[str(falsy.pk)]["appeal"] == {"status": "upheld", "can_appeal": False}


def test_a_deleted_post_has_no_link_and_no_appeal(auth_client):
    author = VerifiedUserFactory()
    post = pending_fact(author)
    label_by_pipeline(post, FALSE_95)
    post_services.delete_post(post_id=post.pk, user=author)
    [row] = page(auth_client(author))["results"]
    assert row["post_id"] is None
    assert row["appeal"] == {"status": None, "can_appeal": False}


def test_the_cursor_walks_every_row_once(auth_client):
    me = VerifiedUserFactory()
    start = timezone.now() - timedelta(days=1)
    made = [EventFactory(user=me, created_at=start + timedelta(minutes=i)).pk for i in range(25)]
    client = auth_client(me)
    seen, cursor = [], None
    while True:
        params = {"page_size": 10}
        if cursor:
            params["cursor"] = cursor
        body = page(client, **params)
        seen += [row["id"] for row in body["results"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == [str(pk) for pk in reversed(made)]


def crafted(position):
    return base64.urlsafe_b64encode(urlencode({"p": position}).encode()).decode()


@pytest.mark.parametrize("position", ["not-a-date", "2026-10-14T12:00:00"])
def test_a_crafted_cursor_is_a_404(auth_client, position):
    client = auth_client(VerifiedUserFactory())
    assert client.get(URL, {"cursor": crafted(position)}).status_code == 404


def test_it_is_never_cached(auth_client):
    response = auth_client(VerifiedUserFactory()).get(URL)
    assert "no-store" in response["Cache-Control"]


def queries(client):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(URL).status_code == 200
    return len(captured)


def test_two_queries_however_many_rows(auth_client):
    me = VerifiedUserFactory()
    client = auth_client(me)
    post = pending_fact(me)
    label_by_pipeline(post, FALSE_95)
    one = queries(client)
    for _ in range(10):
        relabel = pending_fact(me)
        label_by_pipeline(relabel, FALSE_95)
        moderation.file_appeal(author=me, post_id=relabel.pk)
        moderation.mark_verified(relabel.pk, moderator=moderator_user())
    assert queries(client) == one == 2


def test_a_row_whose_post_is_gone_has_no_link_and_no_appeal(auth_client):
    """A post's hard delete only nulls the link (SET_NULL)."""
    me = VerifiedUserFactory()
    EventFactory(user=me, kind=K.POST_REMOVED, post=None)
    [row] = page(auth_client(me))["results"]
    assert row["post_id"] is None
    assert row["appeal"] == {"status": None, "can_appeal": False}
