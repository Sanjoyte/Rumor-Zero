"""`GET /api/v1/users/{username}/posts/`: one author's public posts, the §9 feed shape."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.posts.tests.test_api_create import POST_KEYS
from apps.social.tests.factories import FollowFactory, PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def url(name="ada"):
    return f"/api/v1/users/{name}/posts/"


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada")


def posts_of(author, count, *, base=None, **kwargs):
    base = base or timezone.now() - timedelta(minutes=5)
    return [
        PostFactory(
            author=author,
            content=f"{author.username} {i}",
            created_at=base - timedelta(seconds=i),
            **kwargs,
        )
        for i in range(count)
    ]


def contents(response):
    return [item["post"]["content"] for item in response.json()["results"]]


def test_the_envelope_and_the_items_are_the_feed_shape(api_client, ada):
    posts_of(ada, 2)
    response = api_client.get(url())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"pinned", "pinned_total", "results", "next_cursor"}
    assert body["pinned"] == [] and body["pinned_total"] == 0
    item = body["results"][0]
    assert set(item) == {"kind", "post", "reposted_by", "activity_at"}
    assert item["kind"] == "post" and item["reposted_by"] is None
    assert set(item["post"]) == POST_KEYS
    assert "no-store" in response["Cache-Control"]


def test_only_that_authors_posts_newest_first(api_client, ada):
    posts_of(ada, 3)
    posts_of(VerifiedUserFactory(), 2)
    assert contents(api_client.get(url())) == ["ada 0", "ada 1", "ada 2"]


def test_removed_and_deleted_posts_are_left_out_even_for_their_author(api_client, auth_client, ada):
    kept = posts_of(ada, 2)
    PostFactory(author=ada, removed=True, content="removed one")
    PostFactory(author=ada, deleted=True, content="deleted one")
    for client in (api_client, auth_client(ada), auth_client(VerifiedUserFactory())):
        assert contents(client.get(url())) == [p.content for p in kept]


def test_every_other_status_is_listed(api_client, ada):
    PostFactory(author=ada, fact=True, content="pending")
    PostFactory(author=ada, verified_pipeline=True, content="true")
    PostFactory(author=ada, moderator_verdict=True, content="false")
    PostFactory(author=ada, under_review=True, content="review")
    PostFactory(author=ada, content="opinion")
    assert sorted(contents(api_client.get(url()))) == [
        "false",
        "opinion",
        "pending",
        "review",
        "true",
    ]


def test_post_type_filter(api_client, ada):
    PostFactory(author=ada, fact=True, content="a fact")
    PostFactory(author=ada, content="an opinion")
    assert contents(api_client.get(url(), {"post_type": "fact"})) == ["a fact"]
    assert contents(api_client.get(url(), {"post_type": "opinion"})) == ["an opinion"]
    assert len(contents(api_client.get(url(), {"post_type": ""}))) == 2


@pytest.mark.parametrize("value", ["both", "FACT", "fact,opinion", "1"])
def test_a_bad_post_type_is_a_400_on_that_field(api_client, ada, value):
    response = api_client.get(url(), {"post_type": value})
    assert response.status_code == 400
    assert "post_type" in response.json()


@pytest.mark.parametrize("name", ["nobody", "x" * 200, "a\x00b"])
def test_an_unknown_user_is_a_404(api_client, name):
    assert api_client.get(url(name)).status_code == 404


def test_an_inactive_author_is_a_404(api_client):
    gone = VerifiedUserFactory(username="gone", is_active=False)
    PostFactory(author=gone)
    assert api_client.get(url("gone")).status_code == 404


def test_the_lookup_is_case_insensitive(api_client, ada):
    posts_of(ada, 1)
    assert contents(api_client.get(url("Ada"))) == ["ada 0"]


def test_is_mine_is_filled_for_the_signed_in(auth_client, ada):
    posts_of(ada, 1)
    assert auth_client(ada).get(url()).json()["results"][0]["post"]["is_mine"] is True
    other = auth_client(VerifiedUserFactory()).get(url()).json()["results"][0]["post"]
    assert other["is_mine"] is False


def test_cursor_walk_has_no_repeat_or_gap_when_posts_arrive(api_client, ada):
    posts_of(ada, 7)
    first = api_client.get(url(), {"page_size": 3}).json()
    PostFactory(author=ada, content="late")
    seen = [i["post"]["content"] for i in first["results"]]
    cursor = first["next_cursor"]
    while cursor:
        page = api_client.get(url(), {"page_size": 3, "cursor": cursor}).json()
        seen += [i["post"]["content"] for i in page["results"]]
        cursor = page["next_cursor"]
    assert seen == [f"ada {i}" for i in range(7)]


def test_a_crafted_cursor_is_a_404(api_client, ada):
    assert api_client.get(url(), {"cursor": "cD1ub3QtYS1kYXRl"}).status_code == 404


def test_the_filter_survives_paging(api_client, ada):
    base = timezone.now() - timedelta(minutes=5)
    for i in range(4):
        PostFactory(
            author=ada, fact=True, content=f"fact {i}", created_at=base - timedelta(seconds=2 * i)
        )
        PostFactory(author=ada, content=f"op {i}", created_at=base - timedelta(seconds=2 * i + 1))
    first = api_client.get(url(), {"post_type": "fact", "page_size": 3}).json()
    second = api_client.get(
        url(), {"post_type": "fact", "page_size": 3, "cursor": first["next_cursor"]}
    ).json()
    seen = [i["post"]["content"] for i in first["results"] + second["results"]]
    assert seen == [f"fact {i}" for i in range(4)]


def queries(client):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(url()).status_code == 200
    return len(captured)


def test_the_query_count_is_constant(api_client, auth_client, ada):
    viewer = auth_client(VerifiedUserFactory())
    posts_of(ada, 3, verified_pipeline=True)
    small = (queries(api_client), queries(viewer))
    posts_of(ada, 17, base=timezone.now() - timedelta(hours=1), verified_pipeline=True)
    FollowFactory(following=ada)
    large = (queries(api_client), queries(viewer))
    # the lookup, the page's keys (a union), the posts; and the viewer's own row when signed in
    assert small == large == (3, 4)
