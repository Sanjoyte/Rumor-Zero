"""`POST /api/v1/posts/{id}/appeal/` (ARCHITECTURE §4, §9)."""

import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.moderation.models import Appeal, AppealKind, AppealStatus
from apps.moderation.tests.factories import AppealFactory, ModerationActionFactory, moderator_user
from apps.posts.models import FlaggedReason, Post, PostStatus, PostType, VerdictSource
from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory
from apps.posts.tests.test_api_create import POST_KEYS

pytestmark = pytest.mark.django_db


def url(post_id):
    return f"/api/v1/posts/{post_id}/appeal/"


def false_post(**fields):
    fields.setdefault("verdict_source", VerdictSource.PIPELINE)
    return PostFactory(post_type=PostType.FACT, status=PostStatus.VERIFIED_FALSE, **fields)


def removed_post(**fields):
    return PostFactory(
        post_type=PostType.FACT,
        status=PostStatus.REMOVED,
        pre_removal_status=PostStatus.VERIFIED_FALSE,
        **fields,
    )


def appeal(client, post_id, **body):
    return client.post(url(post_id), body, format="json")


# ---------- the happy path ----------


def test_appealing_a_false_label_is_201_and_the_post_comes_back_under_review(auth_client):
    post = false_post()
    response = appeal(auth_client(post.author), post.pk, reason="  The source was updated.  ")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == POST_KEYS  # 25 keys: the post as its author now sees it
    assert body["status"] == "under_review"
    assert body["can_appeal"] is False and body["appeal_status"] == "open"
    assert body["is_mine"] is True and body["id"] == str(post.pk)
    stored = Appeal.objects.get()
    assert (stored.post, stored.author, stored.kind) == (post, post.author, AppealKind.LABEL)
    assert (stored.status, stored.reason) == (AppealStatus.OPEN, "The source was updated.")
    after = Post.objects.get(pk=post.pk)
    assert (after.status, after.flagged_reason) == (PostStatus.UNDER_REVIEW, FlaggedReason.APPEAL)


def test_appealing_a_removal_is_201_and_the_post_stays_removed_with_its_text_and_reason(
    auth_client,
):
    post = removed_post()
    ModerationActionFactory(post=post, public_note="Personal attack")
    response = appeal(auth_client(post.author), post.pk, reason="It was a quote.")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == POST_KEYS
    assert body["status"] == "removed"
    assert body["content"] == post.content  # the author's own removed post is theirs to read
    assert body["removal_reason"] == "Personal attack"
    assert body["can_appeal"] is False and body["appeal_status"] == "open"
    assert Appeal.objects.get().kind == AppealKind.REMOVAL


def test_the_reason_is_optional_and_null_means_nothing_typed(auth_client):
    one, two, three = false_post(), false_post(), false_post()
    assert appeal(auth_client(one.author), one.pk).status_code == 201
    assert appeal(auth_client(two.author), two.pk, reason=None).status_code == 201
    assert appeal(auth_client(three.author), three.pk, reason="").status_code == 201
    assert set(Appeal.objects.values_list("reason", flat=True)) == {""}


def test_the_reason_counts_code_points_so_500_emoji_pass_and_501_do_not(auth_client):
    ok, too_long = false_post(), false_post()
    assert appeal(auth_client(ok.author), ok.pk, reason="😀" * 500).status_code == 201
    response = appeal(auth_client(too_long.author), too_long.pk, reason="x" * 501)
    assert response.status_code == 400
    assert response.json()["reason"] == ["Keep it to 500 characters."]
    assert Appeal.objects.count() == 1
    assert Post.objects.get(pk=too_long.pk).status == PostStatus.VERIFIED_FALSE


def test_undeclared_fields_are_ignored(auth_client):
    post = false_post()
    other = VerifiedUserFactory()
    body = {"reason": "x", "status": "overturned", "author": str(other.pk), "kind": "removal"}
    assert auth_client(post.author).post(url(post.pk), body, format="json").status_code == 201
    stored = Appeal.objects.get()
    assert (stored.status, stored.author, stored.kind) == (
        AppealStatus.OPEN,
        post.author,
        AppealKind.LABEL,
    )


def test_the_answer_is_never_cached(auth_client):
    post = false_post()
    assert "no-store" in appeal(auth_client(post.author), post.pk)["Cache-Control"]


# ---------- who may ----------


def test_anonymous_is_401(api_client):
    post = false_post()
    assert api_client.post(url(post.pk), {}, format="json").status_code == 401
    assert Appeal.objects.count() == 0


def test_an_unverified_email_is_403_email_unverified(auth_client):
    post = false_post(author=UserFactory())  # is_email_verified False
    response = appeal(auth_client(post.author), post.pk)
    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"
    assert Appeal.objects.count() == 0


def test_somebody_elses_post_is_403_not_author_even_for_a_moderator(auth_client):
    post = false_post()
    for stranger in (VerifiedUserFactory(), moderator_user()):
        response = appeal(auth_client(stranger), post.pk)
        assert response.status_code == 403
        assert response.json()["code"] == "not_author"
    assert Appeal.objects.count() == 0
    assert Post.objects.get(pk=post.pk).status == PostStatus.VERIFIED_FALSE


def test_a_malformed_unknown_or_deleted_post_is_404(auth_client, verified_user):
    client = auth_client(verified_user)
    for bad in ("nope", "123", f"{uuid.uuid4()}x"):
        assert appeal(client, bad).status_code == 404
    assert appeal(client, uuid.uuid4()).status_code == 404
    gone = false_post(author=verified_user, deleted_at="2026-10-01T00:00:00Z")
    response = appeal(client, gone.pk)  # its author included
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found.", "code": "not_found"}
    assert Appeal.objects.count() == 0


# ---------- the refusals ----------


def test_a_second_appeal_is_409_already_appealed_whatever_became_of_the_first(auth_client):
    for status in AppealStatus.values:
        resolved = status != AppealStatus.OPEN
        existing = AppealFactory(
            status=status,
            resolved_at="2026-10-02T00:00:00Z" if resolved else None,
            resolved_by=moderator_user() if resolved else None,
        )
        response = appeal(auth_client(existing.author), existing.post_id)
        assert response.status_code == 409
        assert response.json()["code"] == "already_appealed"
        assert response.json()["detail"] == "You already asked for another look at this post."
    assert Appeal.objects.count() == 3


@pytest.mark.parametrize(
    "fields",
    [
        {"status": PostStatus.PENDING},
        {"status": PostStatus.PUBLISHED, "post_type": PostType.OPINION},
        {"status": PostStatus.VERIFIED_TRUE},
        {
            "status": PostStatus.UNDER_REVIEW,
            "flagged_reason": FlaggedReason.PIPELINE,
            "pre_review_status": PostStatus.PENDING,
        },
        {
            "status": PostStatus.UNDER_REVIEW,
            "flagged_reason": FlaggedReason.REPORTS,
            "pre_review_status": PostStatus.VERIFIED_FALSE,
        },
    ],
    ids=["pending", "published", "verified_true", "under_review", "false_under_review"],
)
def test_any_other_status_is_409_not_appealable(auth_client, fields):
    post = PostFactory(**{"post_type": PostType.FACT, **fields})
    response = appeal(auth_client(post.author), post.pk)
    assert response.status_code == 409
    assert response.json()["code"] == "not_appealable"
    assert response.json()["detail"] == "Only posts labelled FALSE or removed can be appealed."
    assert Appeal.objects.count() == 0


def test_already_appealed_is_checked_before_not_appealable(auth_client):
    """A restored post is no longer removed and an overturned label is TRUE now: still "already"."""
    existing = AppealFactory(removal=True)
    Post.objects.filter(pk=existing.post_id).update(status=PostStatus.VERIFIED_TRUE)
    assert appeal(auth_client(existing.author), existing.post_id).json()["code"] == (
        "already_appealed"
    )


# ---------- the method, the allowance, the cost ----------


def test_only_post_is_allowed_and_a_get_does_not_use_up_the_allowance(auth_client, verified_user):
    client = auth_client(verified_user)
    for _ in range(8):  # more than the 5 a day
        assert client.get(url(uuid.uuid4())).status_code == 405
    for method in ("put", "patch", "delete"):
        assert getattr(client, method)(url(uuid.uuid4())).status_code == 405
    post = false_post(author=verified_user)
    assert appeal(client, post.pk).status_code == 201


def test_the_sixth_appeal_in_a_day_is_429_and_every_answer_from_the_throttle_on_counts(
    auth_client, verified_user
):
    client = auth_client(verified_user)
    for _ in range(5):  # 404s, 400s and 409s all count; so does a 201
        assert appeal(client, uuid.uuid4()).status_code == 404
    response = appeal(client, uuid.uuid4())
    assert response.status_code == 429
    assert response["Retry-After"].isdigit()
    assert response.json()["code"] == "throttled"


def test_a_401_or_403_never_counts_against_the_allowance(api_client, auth_client):
    post = false_post()
    unverified = auth_client(UserFactory())
    for _ in range(7):
        assert api_client.post(url(post.pk), {}, format="json").status_code == 401
        assert appeal(unverified, post.pk).status_code == 403
    assert appeal(auth_client(post.author), post.pk).status_code == 201


def test_the_appeal_allowance_is_its_own(auth_client, verified_user):
    client = auth_client(verified_user)
    for _ in range(5):
        appeal(client, uuid.uuid4())
    assert appeal(client, uuid.uuid4()).status_code == 429
    other = PostFactory()
    assert client.post(f"/api/v1/posts/{other.pk}/like/").status_code == 201
    assert client.post(f"/api/v1/posts/{other.pk}/bookmark/").status_code in (200, 201)


def test_a_201_costs_a_constant_number_of_queries(auth_client):
    counts = []
    for kind_post in (false_post, removed_post):
        post = kind_post()
        client = auth_client(post.author)
        with CaptureQueriesContext(connection) as captured:
            assert appeal(client, post.pk).status_code == 201
        counts.append(len(captured))
    assert max(counts) - min(counts) <= 4  # a label appeal also moves the post (the same shape)
    assert max(counts) < 30
