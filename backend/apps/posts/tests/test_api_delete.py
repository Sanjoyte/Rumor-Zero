"""`DELETE /api/v1/posts/{id}/`: the author's soft delete (D6, ARCHITECTURE §4, §9)."""

import uuid
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tests.conftest import run_together
from apps.posts import services
from apps.posts.models import Post, PostStatus
from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

FEED = "/api/v1/posts/"


def url(post):
    return f"/api/v1/posts/{post.pk}/"


def test_the_author_deletes_their_post_and_gets_204(auth_client):
    post = PostFactory(fact=True)
    old_updated = Post.objects.get(pk=post.pk).updated_at
    response = auth_client(post.author).delete(url(post))
    assert response.status_code == 204
    assert response.content == b""
    row = Post.objects.get(pk=post.pk)  # the row stays: soft delete
    assert row.deleted_at is not None
    assert row.updated_at > old_updated
    assert row.status == PostStatus.PENDING  # the status is untouched
    assert row.content == post.content


def test_a_deleted_post_is_gone_from_the_feed_and_the_detail(api_client, auth_client):
    keep = PostFactory(created_at=timezone.now() - timedelta(minutes=2))
    post = PostFactory(created_at=timezone.now() - timedelta(minutes=1))
    auth_client(post.author).delete(url(post))
    ids = [item["post"]["id"] for item in api_client.get(FEED).json()["results"]]
    assert ids == [str(keep.pk)]
    assert api_client.get(url(post)).status_code == 404
    assert auth_client(post.author).get(url(post)).status_code == 404


def test_the_row_is_still_listed_in_the_admin(client):
    post = PostFactory(content="Deleted but audited")
    root = User.objects.create_superuser(
        email="root@example.test", username="root_user", password="S3cure-pass-phrase!"
    )
    services.delete_post(post_id=post.pk, user=post.author)
    client.force_login(root)
    page = client.get(reverse("admin:posts_post_changelist"))
    assert b"Deleted but audited" in page.content
    only_deleted = client.get(reverse("admin:posts_post_changelist"), {"deleted_at__isempty": "0"})
    assert b"Deleted but audited" in only_deleted.content
    not_deleted = client.get(reverse("admin:posts_post_changelist"), {"deleted_at__isempty": "1"})
    assert b"Deleted but audited" not in not_deleted.content


def test_a_second_delete_is_404(auth_client):
    post = PostFactory()
    client = auth_client(post.author)
    assert client.delete(url(post)).status_code == 204
    response = client.delete(url(post))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_nobody_but_the_author_can_delete_403_not_author(auth_client):
    post = PostFactory()
    other = auth_client(VerifiedUserFactory())
    response = other.delete(url(post))
    assert response.status_code == 403
    assert response.json()["code"] == "not_author"
    staff = auth_client(VerifiedUserFactory(role="senior_moderator"))
    assert staff.delete(url(post)).status_code == 403
    assert Post.objects.get(pk=post.pk).deleted_at is None


def test_an_anonymous_delete_is_401(api_client):
    post = PostFactory()
    assert api_client.delete(url(post)).status_code == 401
    assert Post.objects.get(pk=post.pk).deleted_at is None


def test_an_unverified_author_may_delete_their_own_post(auth_client):
    post = PostFactory(author=UserFactory())  # is_email_verified False
    assert auth_client(post.author).delete(url(post)).status_code == 204


@pytest.mark.parametrize("status", list(PostStatus.values))
def test_a_post_in_any_status_can_be_deleted_and_keeps_its_status(status, auth_client):
    post = PostFactory(fact=status != PostStatus.PUBLISHED, status=status)
    assert auth_client(post.author).delete(url(post)).status_code == 204
    assert Post.objects.get(pk=post.pk).status == status


def test_an_authors_removed_post_can_be_deleted(auth_client):
    post = PostFactory(removed=True)
    assert auth_client(post.author).delete(url(post)).status_code == 204


@pytest.mark.parametrize("bad", ["nope", "12345"])
def test_a_malformed_or_unknown_id_is_404(bad, auth_client):
    client = auth_client(VerifiedUserFactory())
    assert client.delete(f"/api/v1/posts/{bad}/").status_code == 404
    assert client.delete(f"/api/v1/posts/{uuid.uuid4()}/").status_code == 404


def test_a_deleted_fact_post_still_counts_toward_the_allowance(auth_client, fact_limit):
    fact_limit(2)
    author = VerifiedUserFactory()
    client = auth_client(author)
    body = {"content": "Claim", "post_type": "fact"}
    first = client.post(FEED, body, format="json").json()
    client.post(FEED, body, format="json")
    assert client.delete(f"/api/v1/posts/{first['id']}/").status_code == 204
    refused = client.post(FEED, body, format="json")
    assert refused.status_code == 429
    assert refused.json()["code"] == "fact_quota_exceeded"


def test_deleting_does_not_use_up_the_posting_throttle(auth_client):
    author = VerifiedUserFactory()
    client = auth_client(author)
    for _ in range(35):  # post_create is 30 an hour; deletes must not count
        post = PostFactory(author=author)
        assert client.delete(url(post)).status_code == 204


def test_delete_post_service_sets_deleted_at_to_now_and_saves_nothing_else():
    post = PostFactory(fact=True)
    moment = timezone.now() + timedelta(hours=1)
    services.delete_post(post_id=post.pk, user=post.author, now=moment)
    row = Post.objects.get(pk=post.pk)
    assert row.deleted_at == moment
    assert row.status == PostStatus.PENDING


def test_delete_post_service_errors():
    post = PostFactory()
    with pytest.raises(services.NotPostAuthor):
        services.delete_post(post_id=post.pk, user=VerifiedUserFactory())
    with pytest.raises(services.PostNotFound):
        services.delete_post(post_id=uuid.uuid4(), user=post.author)


def test_the_delete_locks_the_post_row():
    post = PostFactory()
    with CaptureQueriesContext(connection) as queries:
        services.delete_post(post_id=post.pk, user=post.author)
    selects = [q["sql"] for q in queries if "FOR UPDATE" in q["sql"]]
    assert len(selects) == 1
    assert "posts_post" in selects[0]


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_deletes_give_one_success_and_one_not_found():
    post = PostFactory()

    def attempt():
        try:
            services.delete_post(post_id=post.pk, user=post.author)
        except services.PostNotFound:
            return "not_found"
        return "deleted"

    assert sorted(run_together(attempt, attempt)) == ["deleted", "not_found"]
    assert Post.objects.get(pk=post.pk).deleted_at is not None
