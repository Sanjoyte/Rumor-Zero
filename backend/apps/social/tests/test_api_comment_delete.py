"""`DELETE /api/v1/comments/{id}/`: the author's soft delete."""

import uuid

import pytest

from apps.social.models import Comment
from apps.social.tests.factories import CommentFactory, PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def url(comment_id):
    return f"/api/v1/comments/{comment_id}/"


@pytest.fixture
def comment():
    return CommentFactory()


def test_the_author_deletes_with_204_and_the_row_stays(auth_client, comment):
    response = auth_client(comment.author).delete(url(comment.pk))
    assert response.status_code == 204
    assert not response.content
    comment.refresh_from_db()
    assert comment.deleted_at is not None
    assert Comment.objects.count() == 1


def test_a_deleted_comment_leaves_the_list_and_the_count(auth_client, api_client, comment):
    keep = CommentFactory(post=comment.post)
    post_url = f"/api/v1/posts/{comment.post_id}/"
    assert api_client.get(post_url).json()["comment_count"] == 2
    auth_client(comment.author).delete(url(comment.pk))
    assert api_client.get(post_url).json()["comment_count"] == 1
    listed = api_client.get(f"{post_url}comments/").json()["results"]
    assert [c["id"] for c in listed] == [str(keep.pk)]


def test_a_second_delete_is_404(auth_client, comment):
    client = auth_client(comment.author)
    assert client.delete(url(comment.pk)).status_code == 204
    assert client.delete(url(comment.pk)).status_code == 404


def test_someone_else_gets_403_not_author_and_nothing_changes(auth_client, comment):
    response = auth_client(VerifiedUserFactory()).delete(url(comment.pk))
    assert response.status_code == 403
    assert response.json()["code"] == "not_author"
    comment.refresh_from_db()
    assert comment.deleted_at is None


def test_the_post_author_cannot_delete_other_peoples_comments(auth_client, comment):
    assert auth_client(comment.post.author).delete(url(comment.pk)).status_code == 403


def test_anonymous_is_401(api_client, comment):
    assert api_client.delete(url(comment.pk)).status_code == 401


def test_deleting_needs_no_verified_email(auth_client):
    from apps.accounts.tests.factories import UserFactory

    comment = CommentFactory(author=UserFactory())
    assert auth_client(comment.author).delete(url(comment.pk)).status_code == 204


@pytest.mark.parametrize(
    "make",
    [
        lambda: CommentFactory(hidden=True),
        lambda: CommentFactory(post=PostFactory(removed=True)),
        lambda: CommentFactory(post=PostFactory(deleted=True)),
    ],
    ids=["hidden", "post removed", "post deleted"],
)
def test_a_comment_nobody_can_see_is_404_even_for_its_author(auth_client, make):
    comment = make()
    response = auth_client(comment.author).delete(url(comment.pk))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


@pytest.mark.parametrize("comment_id", [str(uuid.uuid4()), "not-a-uuid", "7"])
def test_an_unknown_or_malformed_id_is_a_json_404(auth_client, comment, comment_id):
    response = auth_client(comment.author).delete(url(comment_id))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
