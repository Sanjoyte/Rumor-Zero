"""What the post object says about appeals (ARCHITECTURE §9): `can_appeal`, `appeal_status` and
`removal_reason`, per viewer, on every list that carries a post, and what they cost."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.moderation.models import ActionKind, AppealStatus
from apps.moderation.tests.factories import AppealFactory, ModerationActionFactory, moderator_user
from apps.posts.models import FlaggedReason, Post, PostStatus, PostType, VerdictSource
from apps.posts.serializers import PostSerializer
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.social.feed import bust_following_feed
from apps.social.tests.factories import BookmarkFactory, FollowFactory

pytestmark = pytest.mark.django_db


def false_post(**fields):
    fields.setdefault("verdict_source", VerdictSource.PIPELINE)
    return PostFactory(post_type=PostType.FACT, status=PostStatus.VERIFIED_FALSE, **fields)


def removed_post(reason=None, **fields):
    post = PostFactory(
        post_type=PostType.FACT,
        status=PostStatus.REMOVED,
        pre_removal_status=PostStatus.VERIFIED_FALSE,
        **fields,
    )
    if reason is not None:
        ModerationActionFactory(post=post, action=ActionKind.REMOVED, public_note=reason)
    return post


def detail(client, post):
    response = client.get(f"/api/v1/posts/{post.pk}/")
    assert response.status_code == 200
    return response.json()


def fields(body):
    return {key: body[key] for key in ("can_appeal", "appeal_status", "removal_reason")}


# ---------- can_appeal and appeal_status ----------


def test_the_author_of_a_false_post_can_appeal_and_nobody_else(api_client, auth_client):
    post = false_post()
    assert fields(detail(auth_client(post.author), post)) == {
        "can_appeal": True,
        "appeal_status": None,
        "removal_reason": "",
    }
    for client in (api_client, auth_client(VerifiedUserFactory()), auth_client(moderator_user())):
        assert fields(detail(client, post)) == {
            "can_appeal": False,
            "appeal_status": None,
            "removal_reason": "",
        }


@pytest.mark.parametrize(
    "fields_",
    [
        {"status": PostStatus.PENDING},
        {"status": PostStatus.PUBLISHED, "post_type": PostType.OPINION},
        {"status": PostStatus.VERIFIED_TRUE},
        {
            "status": PostStatus.UNDER_REVIEW,
            "flagged_reason": FlaggedReason.REPORTS,
            "pre_review_status": PostStatus.VERIFIED_FALSE,
        },
    ],
)
def test_no_other_status_can_be_appealed(auth_client, fields_):
    post = PostFactory(**{"post_type": PostType.FACT, **fields_})
    assert detail(auth_client(post.author), post)["can_appeal"] is False


def test_the_author_of_a_removed_post_can_appeal_it(auth_client):
    post = removed_post()
    assert detail(auth_client(post.author), post)["can_appeal"] is True


@pytest.mark.parametrize("status", AppealStatus.values)
def test_after_an_appeal_the_author_sees_its_status_and_can_no_longer_appeal(auth_client, status):
    resolved = status != AppealStatus.OPEN
    existing = AppealFactory(
        status=status,
        resolved_at=timezone.now() if resolved else None,
        resolved_by=moderator_user() if resolved else None,
    )
    body = detail(auth_client(existing.author), existing.post)
    assert body["appeal_status"] == status and body["can_appeal"] is False


def test_nobody_but_the_author_learns_that_an_appeal_exists(api_client, auth_client):
    existing = AppealFactory()
    for client in (api_client, auth_client(VerifiedUserFactory()), auth_client(moderator_user())):
        body = detail(client, existing.post)
        assert body["appeal_status"] is None and body["can_appeal"] is False


def test_the_appeal_belongs_to_the_post_not_to_whoever_looks(auth_client):
    one, two = AppealFactory(), AppealFactory()
    assert detail(auth_client(one.author), two.post)["appeal_status"] is None
    assert detail(auth_client(one.author), one.post)["appeal_status"] == "open"


# ---------- removal_reason ----------


def test_the_author_sees_the_reason_of_the_latest_removal_and_nobody_else_does(
    api_client, auth_client
):
    post = removed_post(reason="First reason")
    ModerationActionFactory(
        post=post,
        action=ActionKind.REMOVED,
        public_note="Latest reason",
        created_at=timezone.now() + timedelta(minutes=5),
    )
    ModerationActionFactory(  # another kind of row, even newer, is not the removal reason
        post=post,
        action=ActionKind.ESCALATED,
        public_note="not this",
        created_at=timezone.now() + timedelta(minutes=9),
    )
    assert detail(auth_client(post.author), post)["removal_reason"] == "Latest reason"
    for client in (api_client, auth_client(VerifiedUserFactory()), auth_client(moderator_user())):
        body = detail(client, post)
        assert body["removal_reason"] == "" and post.content not in str(body)


def test_a_removal_without_a_reason_has_a_blank_one(auth_client):
    assert (
        detail(auth_client(removed_post(reason="").author), removed_post(reason=""))[
            "removal_reason"
        ]
        == ""
    )
    post = removed_post(reason="")
    assert detail(auth_client(post.author), post)["removal_reason"] == ""


def test_the_reason_is_only_for_a_post_that_is_still_removed(auth_client):
    """After a Restore the audit row stays, and the post is live again: no stale reason."""
    post = removed_post(reason="Because")
    PostFactory._meta.model.objects.filter(pk=post.pk).update(status=PostStatus.VERIFIED_FALSE)
    assert detail(auth_client(post.author), post)["removal_reason"] == ""


def test_one_post_reads_the_reason_of_its_own_row_only(auth_client):
    one, two = removed_post(reason="One's reason"), removed_post(reason="Two's reason")
    assert detail(auth_client(one.author), one)["removal_reason"] == "One's reason"
    assert detail(auth_client(two.author), two)["removal_reason"] == "Two's reason"


# ---------- every list carries them ----------


def items(response):
    return {i["post"]["id"]: i["post"] for i in response.json()["results"] if i["kind"] == "post"}


def test_the_recent_feed_carries_them_for_the_author(auth_client):
    post = false_post()
    mine = items(auth_client(post.author).get("/api/v1/posts/"))[str(post.pk)]
    assert fields(mine) == {"can_appeal": True, "appeal_status": None, "removal_reason": ""}
    other = items(auth_client(VerifiedUserFactory()).get("/api/v1/posts/"))[str(post.pk)]
    assert other["can_appeal"] is False


def test_the_profile_the_following_feed_and_the_bookmarks_carry_them(auth_client):
    author = VerifiedUserFactory(username="grace")
    existing = AppealFactory(post=false_post(author=author), author=author)
    reader = VerifiedUserFactory()
    FollowFactory(follower=reader, following=author)
    BookmarkFactory(user=author, post=existing.post)
    BookmarkFactory(user=reader, post=existing.post)
    mine, theirs = auth_client(author), auth_client(reader)
    for path in ("/api/v1/users/grace/posts/", "/api/v1/me/bookmarks/"):
        assert items(mine.get(path))[str(existing.post_id)]["appeal_status"] == "open", path
        assert items(theirs.get(path))[str(existing.post_id)]["appeal_status"] is None, path
    assert items(mine.get("/api/v1/feed/"))[str(existing.post_id)]["appeal_status"] == "open"
    assert items(theirs.get("/api/v1/feed/"))[str(existing.post_id)]["appeal_status"] is None


# ---------- the cost ----------


def count(client, path):
    with CaptureQueriesContext(connection) as captured:
        assert client.get(path).status_code == 200
    return len(captured)


def seeded(author, *, with_appeals):
    """Twenty posts of one author, each with the audit and appeal rows when asked."""
    for index in range(20):
        base = timezone.now() - timedelta(minutes=index + 1)
        if index % 2:
            post = removed_post(author=author, created_at=base, reason=f"reason {index}")
        else:
            post = false_post(author=author, created_at=base)
        if with_appeals and index % 3 == 0:
            AppealFactory(post=post, author=author, removal=index % 2 == 1)


@pytest.mark.parametrize(
    "path",
    ["/api/v1/posts/", "/api/v1/users/grace/posts/", "/api/v1/feed/"],
)
def test_the_lists_cost_the_same_with_or_without_appeals_and_removal_rows(auth_client, path):
    """The two fields are subqueries of the same query, never a query per post."""
    author = VerifiedUserFactory(username="grace")
    client = auth_client(author)
    PostFactory(author=author, content="one so the list is never empty")
    FollowFactory(follower=author, following=VerifiedUserFactory())
    count(client, path)  # the Following feed's first page is cached: warm it, then compare hits
    before = count(client, path)
    seeded(author, with_appeals=True)
    bust_following_feed(author.pk)
    count(client, path)
    assert count(client, path) == before


def test_the_detail_page_costs_the_same_with_and_without_them(auth_client):
    author = VerifiedUserFactory()
    client = auth_client(author)
    plain = false_post(author=author)
    costly = removed_post(author=author, reason="x")
    AppealFactory(post=costly, author=author, removal=True)
    assert count(client, f"/api/v1/posts/{plain.pk}/") == count(
        client, f"/api/v1/posts/{costly.pk}/"
    )


# ---------- two independent guards: the query and the serializer ----------


def test_the_query_itself_gives_the_reason_to_nobody_but_the_author():
    """`for_list` annotates; the serializer gates again. Each is checked on its own."""
    post = removed_post(reason="Personal attack")
    stranger = VerifiedUserFactory()
    assert Post.objects.for_list(post.author).get(pk=post.pk).removal_reason == "Personal attack"
    assert Post.objects.for_list(stranger).get(pk=post.pk).removal_reason == ""
    assert Post.objects.for_list(None).get(pk=post.pk).removal_reason == ""
    assert Post.objects.for_list(stranger).get(pk=post.pk).appeal_status is None


def test_the_serializer_itself_hides_what_a_wrong_annotation_would_leak():
    """A list that annotated for the wrong person must still show a stranger nothing."""
    post = removed_post(reason="x")
    existing = AppealFactory(post=post, author=post.author, removal=True)
    annotated = Post.objects.for_list(post.author).get(pk=post.pk)
    assert annotated.removal_reason == "x" and annotated.appeal_status == existing.status
    request = type("R", (), {"user": VerifiedUserFactory()})()
    data = PostSerializer(annotated, context={"request": request}).data
    assert (data["removal_reason"], data["appeal_status"], data["can_appeal"]) == ("", None, False)
    assert data["content"] == ""  # and the tombstone rule, as ever
