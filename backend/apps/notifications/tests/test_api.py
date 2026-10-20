"""`GET /api/v1/notifications/`, `…/unread-count/` and `POST …/mark-read/` (ARCHITECTURE §9)."""

import uuid
from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications import services
from apps.notifications.models import Notification, NotificationType
from apps.notifications.tests.factories import (
    NotificationFactory,
    comment_item,
    follow_item,
    spaced,
    system_item,
)
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.social.models import Follow

pytestmark = pytest.mark.django_db

LIST = "/api/v1/notifications/"
COUNT = "/api/v1/notifications/unread-count/"
MARK = "/api/v1/notifications/mark-read/"
ITEM_KEYS = {"id", "type", "outcome", "is_read", "created_at", "actor", "post", "comment"}


@pytest.fixture
def me():
    return VerifiedUserFactory()


@pytest.fixture
def client(auth_client, me):
    return auth_client(me)


# ---------- who may ask ----------


@pytest.mark.parametrize("url", [LIST, COUNT])
def test_reading_needs_a_login(url):
    assert APIClient().get(url).status_code == 401


def test_marking_read_needs_a_login():
    assert APIClient().post(MARK, {"all": True}, format="json").status_code == 401


def test_an_unverified_email_may_still_read_its_notifications(auth_client):
    from apps.posts.tests.factories import UserFactory

    unverified = UserFactory()
    NotificationFactory(recipient=unverified)
    assert auth_client(unverified).get(COUNT).json() == {"count": 1}


def test_the_answers_are_never_cached(client):
    assert "no-cache" in client.get(LIST)["Cache-Control"]
    assert "no-cache" in client.get(COUNT)["Cache-Control"]


# ---------- the list ----------


def test_an_empty_list(client):
    assert client.get(LIST).json() == {"results": [], "next_cursor": None}


def test_a_like_item(client, me):
    post = PostFactory(author=me, content="Water is wet")
    fan = VerifiedUserFactory(display_name="Fan One")
    item = NotificationFactory(recipient=me, actor=fan, post=post)
    [row] = client.get(LIST).json()["results"]
    assert set(row) == ITEM_KEYS
    assert row["id"] == str(item.pk)
    assert row["type"] == "like"
    assert row["outcome"] == ""
    assert row["is_read"] is False
    assert row["actor"] == {
        "id": str(fan.pk),
        "username": fan.username,
        "display_name": "Fan One",
        "avatar_url": None,
    }
    assert row["post"] == {
        "id": str(post.pk),
        "excerpt": "Water is wet",
        "post_type": "opinion",
        "status": "published",
    }
    assert row["comment"] is None
    assert row["created_at"].endswith("Z")


def test_a_comment_item_carries_the_comment_excerpt(client, me):
    comment_item(me, VerifiedUserFactory())
    [row] = client.get(LIST).json()["results"]
    assert row["type"] == "comment"
    assert row["comment"]["excerpt"] == "A comment"
    assert set(row["comment"]) == {"id", "excerpt"}


def test_a_system_item_has_no_actor(client, me):
    system_item(me, NotificationType.VERDICT, outcome="false")
    [row] = client.get(LIST).json()["results"]
    assert (row["type"], row["outcome"], row["actor"]) == ("verdict", "false", None)


def test_a_follow_item_has_no_post_and_says_whether_you_follow_back(client, me):
    fan, stranger = VerifiedUserFactory(), VerifiedUserFactory()
    follow_item(me, fan, created_at=timezone.now())
    follow_item(me, stranger, created_at=timezone.now() - timedelta(seconds=1))
    Follow.objects.create(follower=me, following=fan)
    first, second = client.get(LIST).json()["results"]
    assert first["post"] is None and first["comment"] is None
    assert first["actor"]["following"] is True
    assert second["actor"]["following"] is False


def test_only_a_follow_carries_following(client, me):
    NotificationFactory(recipient=me)
    [row] = client.get(LIST).json()["results"]
    assert "following" not in row["actor"]


def test_the_excerpt_is_cut_at_140_characters_and_collapses_whitespace(client, me):
    post = PostFactory(author=me, content="word  " * 60)
    NotificationFactory(recipient=me, post=post)
    excerpt = client.get(LIST).json()["results"][0]["post"]["excerpt"]
    assert excerpt.endswith("…")
    assert "  " not in excerpt
    assert len(excerpt) <= 141


def test_a_short_excerpt_is_whole(client, me):
    post = PostFactory(author=me, content="Line one\n\nLine   two")
    NotificationFactory(recipient=me, post=post)
    assert client.get(LIST).json()["results"][0]["post"]["excerpt"] == "Line one Line two"


def test_a_suspended_actor_shows_as_someone(client, me):
    fan = VerifiedUserFactory(is_active=False)
    NotificationFactory(recipient=me, actor=fan)
    [row] = client.get(LIST).json()["results"]
    assert row["actor"] is None


def test_a_deleted_account_shows_as_someone(client, me):
    fan = VerifiedUserFactory()
    NotificationFactory(recipient=me, actor=fan)
    fan.delete()
    assert client.get(LIST).json()["results"][0]["actor"] is None


def test_you_never_see_other_peoples_items(client, me):
    NotificationFactory()
    NotificationFactory(recipient=me)
    assert len(client.get(LIST).json()["results"]) == 1


def test_an_item_about_a_post_the_author_deleted_is_left_out(client, me):
    kept = NotificationFactory(recipient=me)
    gone = NotificationFactory(recipient=me)
    gone.post.deleted_at = timezone.now()
    gone.post.save()
    assert [row["id"] for row in client.get(LIST).json()["results"]] == [str(kept.pk)]


def test_a_removed_post_s_items_still_show_to_its_author(client, me):
    post = PostFactory(author=me, removed=True)
    NotificationFactory(recipient=me, post=post)
    assert client.get(LIST).json()["results"][0]["post"]["status"] == "removed"


def test_newest_first_with_a_cursor(client, me):
    times = spaced(25)
    for when in times:
        NotificationFactory(recipient=me, created_at=when)
    first = client.get(LIST).json()
    assert len(first["results"]) == 20
    assert first["next_cursor"]
    second = client.get(LIST, {"cursor": first["next_cursor"]}).json()
    assert len(second["results"]) == 5
    assert second["next_cursor"] is None
    ids = [row["id"] for row in first["results"] + second["results"]]
    assert len(set(ids)) == 25
    stamps = [row["created_at"] for row in first["results"] + second["results"]]
    assert stamps == sorted(stamps, reverse=True)


def test_page_size_up_to_50(client, me):
    for when in spaced(30):
        NotificationFactory(recipient=me, created_at=when)
    assert len(client.get(LIST, {"page_size": 30}).json()["results"]) == 30


@pytest.mark.parametrize("cursor", ["not-a-cursor", "cD1ub3QtYS1kYXRl", "cD0yMDI2LTEwLTIwVDEyOjAw"])
def test_a_crafted_cursor_is_a_404(client, cursor):
    assert client.get(LIST, {"cursor": cursor}).status_code == 404


def test_items_of_one_action_keep_their_order_across_a_page_boundary(client, me):
    post = PostFactory(author=me)
    base = timezone.now()
    with transaction.atomic():
        services.removed(post=post, now=base)
        services.emergency_demoted(post=post, now=base + services.TICK)
    page = client.get(LIST, {"page_size": 1}).json()
    assert page["results"][0]["type"] == "emergency_demoted"
    rest = client.get(LIST, {"page_size": 1, "cursor": page["next_cursor"]}).json()
    assert rest["results"][0]["type"] == "removed"


def test_the_list_is_two_queries_whatever_it_holds(auth_client, me):
    other = VerifiedUserFactory()
    post = PostFactory(author=me)
    now = timezone.now()
    NotificationFactory(recipient=me, post=post, created_at=now)
    follow_item(me, other, created_at=now - timedelta(seconds=1))
    comment_item(me, other, created_at=now - timedelta(seconds=2))
    system_item(me, NotificationType.REMOVED, created_at=now - timedelta(seconds=3))
    for n in range(4, 20):
        NotificationFactory(recipient=me, created_at=now - timedelta(seconds=n))
    client = auth_client(me)
    with CaptureQueriesContext(connection) as queries:
        response = client.get(LIST)
    assert len(response.json()["results"]) == 20
    assert len(queries) == 2


def test_the_list_never_reads_the_posts_pipeline_result_or_search_vector(auth_client, me):
    NotificationFactory(recipient=me)
    client = auth_client(me)
    with CaptureQueriesContext(connection) as queries:
        client.get(LIST)
    sql = queries[-1]["sql"]
    assert "pipeline_result" not in sql
    assert "search_vector" not in sql


# ---------- the unread count ----------


def test_the_unread_count(client, me):
    NotificationFactory.create_batch(3, recipient=me)
    NotificationFactory(recipient=me, is_read=True)
    NotificationFactory()
    assert client.get(COUNT).json() == {"count": 3}


def test_the_unread_count_is_two_queries(auth_client, me):
    NotificationFactory.create_batch(3, recipient=me)
    client = auth_client(me)
    with CaptureQueriesContext(connection) as queries:
        client.get(COUNT)
    assert len(queries) == 2


def test_the_count_is_exact_above_99(client, me):
    NotificationFactory.create_batch(101, recipient=me)
    assert client.get(COUNT).json() == {"count": 101}


def test_the_count_query_can_use_the_partial_index(me):
    """Postgres uses `notifications_unread_idx` for the count's own predicate."""
    NotificationFactory.create_batch(3, recipient=me)
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL enable_seqscan = off")
    plan = Notification.objects.filter(recipient=me, is_read=False).explain(format="json")
    assert "notifications_unread_idx" in plan


# ---------- mark read ----------


def test_mark_some_read(client, me):
    a, b, c = NotificationFactory.create_batch(3, recipient=me)
    response = client.post(MARK, {"ids": [str(a.pk), str(b.pk)]}, format="json")
    assert response.status_code == 200
    assert response.json() == {"count": 1}
    assert set(Notification.objects.filter(is_read=True).values_list("pk", flat=True)) == {
        a.pk,
        b.pk,
    }


def test_mark_all_read(client, me):
    NotificationFactory.create_batch(3, recipient=me)
    other = NotificationFactory()
    assert client.post(MARK, {"all": True}, format="json").json() == {"count": 0}
    other.refresh_from_db()
    assert other.is_read is False
    assert client.get(COUNT).json() == {"count": 0}


def test_other_peoples_and_unknown_ids_are_ignored_not_an_error(client, me):
    mine = NotificationFactory(recipient=me)
    theirs = NotificationFactory()
    response = client.post(MARK, {"ids": [str(theirs.pk), str(uuid.uuid4())]}, format="json")
    assert response.status_code == 200
    assert response.json() == {"count": 1}
    theirs.refresh_from_db()
    mine.refresh_from_db()
    assert not theirs.is_read and not mine.is_read


def test_marking_twice_is_harmless(client, me):
    item = NotificationFactory(recipient=me)
    for _ in range(2):
        assert client.post(MARK, {"ids": [str(item.pk)]}, format="json").json() == {"count": 0}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"ids": []},
        {"all": False},
        {"all": True, "ids": ["00000000-0000-0000-0000-000000000000"]},
        {"ids": ["nope"]},
        {"ids": "00000000-0000-0000-0000-000000000000"},
        {"ids": [str(uuid.uuid4()) for _ in range(51)]},
        {"all": "maybe"},
        {"all": None},
        {"ids": None},
    ],
)
def test_a_bad_body_is_a_400_and_changes_nothing(client, me, body):
    item = NotificationFactory(recipient=me)
    assert client.post(MARK, body, format="json").status_code == 400
    item.refresh_from_db()
    assert not item.is_read


def test_fifty_ids_are_allowed(client, me):
    ids = [str(uuid.uuid4()) for _ in range(50)]
    assert client.post(MARK, {"ids": ids}, format="json").status_code == 200


def test_a_list_body_is_a_400(client):
    assert client.post(MARK, [1, 2], format="json").status_code == 400


def test_mark_read_does_not_accept_get(client):
    assert client.get(MARK).status_code == 405


# ---------- the allowance ----------


def test_120_requests_a_minute_per_user_then_429_shared_by_the_three_endpoints(auth_client, me):
    client = auth_client(me)
    for n in range(120):
        url = (LIST, COUNT)[n % 2]
        assert client.get(url).status_code == 200
    response = client.post(MARK, {"all": True}, format="json")
    assert response.status_code == 429
    assert response.json()["code"] == "throttled"
    assert "Retry-After" in response
    assert client.get(LIST).status_code == 429
    other = auth_client(VerifiedUserFactory())
    assert other.get(COUNT).status_code == 200


def test_a_401_does_not_use_up_the_allowance(auth_client, me):
    anonymous = APIClient()
    for _ in range(130):
        assert anonymous.get(COUNT).status_code == 401
    assert auth_client(me).get(COUNT).status_code == 200
