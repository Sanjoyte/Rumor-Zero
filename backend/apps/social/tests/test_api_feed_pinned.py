"""Pinned emergencies on the Following feed (ARCHITECTURE §4b, §9; Part 11C): the active
emergencies by the people you follow and by you, newest first, at most 3, left out of the pages;
reposts never pin."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.posts.models import Post
from apps.posts.tests.conftest import fact_limit  # noqa: F401  (fixture)
from apps.social import feed
from apps.social.tests.factories import (
    FollowFactory,
    PostFactory,
    RepostFactory,
    VerifiedUserFactory,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/feed/"


@pytest.fixture
def me():
    return VerifiedUserFactory(username="myself")


@pytest.fixture
def bo(me):
    star = VerifiedUserFactory(username="bob")
    FollowFactory(follower=me, following=star)
    return star


def ago(minutes):
    return timezone.now() - timedelta(minutes=minutes)


def emergency(author, content, minutes=10, **fields):
    made = ago(minutes)
    return PostFactory(
        author=author,
        content=content,
        post_type="fact",
        status="pending",
        is_emergency=True,
        created_at=made,
        emergency_expires_at=made + timedelta(hours=24),
        **fields,
    )


def post(author, content, minutes):
    return PostFactory(author=author, content=content, created_at=ago(minutes))


def body_of(client, **params):
    return client.get(URL, params).json()


def pinned(body):
    return [p["content"] for p in body["pinned"]]


def shape(body):
    out = []
    for item in body["results"]:
        text = "gone" if item["post"].get("unavailable") else item["post"]["content"]
        who = f":{item['reposted_by']['username']}" if item["reposted_by"] else ""
        out.append(f"{item['kind']}:{text}{who}")
    return out


def test_followed_and_own_emergencies_are_pinned_and_a_strangers_is_not(auth_client, me, bo):
    stranger = VerifiedUserFactory()
    emergency(me, "Mine", 5)
    emergency(bo, "Bob's", 10)
    emergency(stranger, "A stranger's", 1)
    post(bo, "An ordinary post", 3)
    body = body_of(auth_client(me))
    assert pinned(body) == ["Mine", "Bob's"]
    assert body["pinned_total"] == 2
    assert shape(body) == ["post:An ordinary post"]


def test_at_most_three_and_none_of_them_in_the_pages(auth_client, me, bo):
    for i in range(5):
        emergency(bo, f"Warning {i}", 10 + i)
    post(bo, "Ordinary", 1)
    body = body_of(auth_client(me))
    assert pinned(body) == ["Warning 0", "Warning 1", "Warning 2"]
    assert body["pinned_total"] == 5
    assert shape(body) == ["post:Ordinary"]


def test_a_repost_of_a_pinned_post_is_left_out_and_others_stay(auth_client, me, bo):
    """Reposts never pin. A repost of a post that is pinned here would repeat it; a repost of
    someone else's emergency stays in the list, with its chip."""
    stranger = VerifiedUserFactory()
    mine = emergency(bo, "Bob's warning", 20)
    theirs = emergency(stranger, "A stranger's warning", 30)
    friend = VerifiedUserFactory(username="cleo")
    FollowFactory(follower=me, following=friend)
    RepostFactory(user=friend, post=mine, created_at=ago(2))
    RepostFactory(user=friend, post=theirs, created_at=ago(1))
    body = body_of(auth_client(me))
    assert pinned(body) == ["Bob's warning"]
    assert shape(body) == ["repost:A stranger's warning:cleo"]
    [item] = body["results"]
    assert item["post"]["emergency_active"] is True


def test_an_expired_emergency_is_back_in_the_list_with_its_reposts(auth_client, me, bo):
    over = emergency(bo, "Over", 24 * 60 + 1)
    friend = VerifiedUserFactory(username="cleo")
    FollowFactory(follower=me, following=friend)
    RepostFactory(user=friend, post=over, created_at=ago(1))
    body = body_of(auth_client(me))
    assert pinned(body) == []
    assert shape(body) == ["repost:Over:cleo"]  # the post itself is hidden behind its repost


def test_the_pinned_list_is_on_the_first_page_only(auth_client, me, bo):
    for i in range(25):
        post(bo, f"Post {i}", i + 1)
    emergency(bo, "Warning", 100)
    client = auth_client(me)
    first = body_of(client)
    assert pinned(first) == ["Warning"]
    later = body_of(client, cursor=first["next_cursor"])
    assert (later["pinned"], later["pinned_total"]) == ([], 0)
    everything = shape(first) + shape(later)
    assert "post:Warning" not in everything and len(everything) == 25


def test_a_cache_hit_still_pins_fresh(auth_client, me, bo):
    """The cached keys were filtered when cached; the pinned list is read on every first page,
    so a new emergency shows at once and a demoted one leaves at once."""
    post(bo, "Ordinary", 5)
    client = auth_client(me)
    assert pinned(body_of(client)) == []
    assert cache.get(feed.cache_key(me.pk)) is not None
    warning = emergency(bo, "New warning", 1)
    assert pinned(body_of(client)) == ["New warning"]  # a hit: the keys came from the cache
    Post.objects.filter(pk=warning.pk).update(emergency_demoted_at=timezone.now())
    body = body_of(client)
    assert pinned(body) == []
    assert shape(body) == ["post:Ordinary"]  # until the cache's 30 s run out (accepted)


def test_your_own_new_emergency_is_pinned_at_once(auth_client, me, fact_limit):  # noqa: F811
    """Posting busts your cached page, and the pinned list is fresh anyway."""
    me.created_at = timezone.now() - timedelta(days=30)
    me.save(update_fields=["created_at"])
    client = auth_client(me)
    body_of(client)
    response = client.post(
        "/api/v1/posts/",
        {"content": "Gas leak on Main Street", "post_type": "fact", "is_emergency": True},
        format="json",
    )
    assert response.status_code == 201
    body = body_of(client)
    assert pinned(body) == ["Gas leak on Main Street"]
    assert shape(body) == []
