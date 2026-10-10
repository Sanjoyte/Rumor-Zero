"""`POST /api/v1/posts/{id}/comments/`: verified-only, 1 to 500 code points, throttled on POST."""

import uuid

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.social.models import Comment
from apps.social.tests.factories import PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db


def url(post_id):
    return f"/api/v1/posts/{post_id}/comments/"


@pytest.fixture
def post():
    return PostFactory()


@pytest.fixture
def ada():
    return VerifiedUserFactory(username="ada")


def test_a_comment_is_201_with_the_comment_object(auth_client, ada, post):
    response = auth_client(ada).post(url(post.pk), {"content": "Good point."}, format="json")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "author", "content", "is_mine", "created_at"}
    assert (body["content"], body["is_mine"], body["author"]["username"]) == (
        "Good point.",
        True,
        "ada",
    )
    comment = Comment.objects.get()
    assert (str(comment.pk), comment.post_id, comment.author_id) == (body["id"], post.pk, ada.pk)


def test_the_new_comment_shows_in_the_list_and_the_count(auth_client, api_client, ada, post):
    auth_client(ada).post(url(post.pk), {"content": "Hi"}, format="json")
    assert [c["content"] for c in api_client.get(url(post.pk)).json()["results"]] == ["Hi"]
    assert api_client.get(f"/api/v1/posts/{post.pk}/").json()["comment_count"] == 1


def test_the_text_is_trimmed_and_may_have_several_lines(auth_client, ada, post):
    response = auth_client(ada).post(url(post.pk), {"content": "  one\ntwo  \n"}, format="json")
    assert response.json()["content"] == "one\ntwo"


@pytest.mark.parametrize("text", ["x", "x" * 500, "😀" * 500])
def test_one_to_500_code_points_is_accepted(auth_client, ada, post, text):
    assert auth_client(ada).post(url(post.pk), {"content": text}, format="json").status_code == 201


@pytest.mark.parametrize("body", [{}, {"content": ""}, {"content": "   \n "}, {"content": None}])
def test_an_empty_comment_is_refused(auth_client, ada, post, body):
    response = auth_client(ada).post(url(post.pk), body, format="json")
    assert response.status_code == 400
    assert response.json() == {"content": ["Write something first."]}
    assert Comment.objects.count() == 0


@pytest.mark.parametrize("text", ["x" * 501, "😀" * 501])
def test_a_comment_over_500_code_points_is_refused(auth_client, ada, post, text):
    response = auth_client(ada).post(url(post.pk), {"content": text}, format="json")
    assert response.status_code == 400
    assert response.json() == {"content": ["Keep it to 500 characters."]}


def test_undeclared_fields_are_ignored(auth_client, ada, post):
    other = VerifiedUserFactory()
    auth_client(ada).post(
        url(post.pk),
        {"content": "Hi", "author": str(other.pk), "is_hidden": True, "created_at": "2001-01-01"},
        format="json",
    )
    comment = Comment.objects.get()
    assert (comment.author_id, comment.is_hidden) == (ada.pk, False)
    assert comment.created_at.year >= 2026


def test_anonymous_is_401(api_client, post):
    assert api_client.post(url(post.pk), {"content": "Hi"}, format="json").status_code == 401


def test_an_unverified_user_cannot_comment(auth_client, post):
    response = auth_client(UserFactory()).post(url(post.pk), {"content": "Hi"}, format="json")
    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"
    assert Comment.objects.count() == 0


@pytest.mark.parametrize("trait", ["fact", "under_review", "verified_pipeline"])
def test_every_visible_status_can_be_commented_on(auth_client, ada, trait):
    post = PostFactory(**{trait: True})
    assert auth_client(ada).post(url(post.pk), {"content": "Hi"}, format="json").status_code == 201


@pytest.mark.parametrize("trait", ["removed", "deleted"])
def test_a_removed_or_deleted_post_cannot_be_commented_on(auth_client, ada, trait):
    post = PostFactory(**{trait: True})
    response = auth_client(ada).post(url(post.pk), {"content": "Hi"}, format="json")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert Comment.objects.count() == 0


@pytest.mark.parametrize("post_id", [str(uuid.uuid4()), "not-a-uuid"])
def test_an_unknown_or_malformed_post_id_is_a_json_404(auth_client, ada, post_id):
    response = auth_client(ada).post(url(post_id), {"content": "Hi"}, format="json")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# ---------- the throttle (the real number of requests: rates are bound at import) ----------


def test_the_61st_comment_in_an_hour_is_throttled(auth_client, ada, post):
    client = auth_client(ada)
    for _ in range(60):
        assert client.post(url(post.pk), {"content": "Hi"}, format="json").status_code == 201
    response = client.post(url(post.pk), {"content": "Hi"}, format="json")
    assert response.status_code == 429
    assert response.json()["code"] == "throttled"
    assert "Retry-After" in response
    assert Comment.objects.count() == 60


def test_reading_comments_never_uses_up_the_comment_allowance(auth_client, ada, post):
    client = auth_client(ada)
    for _ in range(70):
        assert client.get(url(post.pk)).status_code == 200
    assert client.post(url(post.pk), {"content": "Hi"}, format="json").status_code == 201


def test_a_401_403_or_400_before_the_throttle_never_counts_but_a_validation_error_does(
    api_client, auth_client, ada, post
):
    for _ in range(65):
        assert api_client.post(url(post.pk), {"content": "Hi"}, format="json").status_code == 401
    unverified = auth_client(UserFactory())
    for _ in range(65):
        assert unverified.post(url(post.pk), {"content": "Hi"}, format="json").status_code == 403
    client = auth_client(ada)
    for _ in range(60):
        assert client.post(url(post.pk), {"content": ""}, format="json").status_code == 400
    assert client.post(url(post.pk), {"content": "Hi"}, format="json").status_code == 429
