"""Likes and comments in `social.services`: the rules, and what two simultaneous requests do."""

from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.accounts.tests.conftest import run_together
from apps.social import services
from apps.social.models import Comment, Like
from apps.social.tests.factories import (
    CommentFactory,
    LikeFactory,
    PostFactory,
    VerifiedUserFactory,
)

pytestmark = pytest.mark.django_db


# ---------- likes ----------


def test_like_creates_once_and_then_reports_it_already_existed():
    user, post = VerifiedUserFactory(), PostFactory()
    assert services.like(user=user, post_id=post.pk) is True
    assert services.like(user=user, post_id=post.pk) is False
    assert Like.objects.filter(user=user, post=post).count() == 1


@pytest.mark.parametrize(
    "state", ["fact", "under_review", "verified_pipeline", "moderator_verdict"]
)
def test_every_visible_status_can_be_liked(state):
    post = PostFactory(**{state: True})
    assert services.like(user=VerifiedUserFactory(), post_id=post.pk) is True


@pytest.mark.parametrize("state", ["removed", "deleted"])
def test_a_removed_or_deleted_post_cannot_be_liked(state):
    post = PostFactory(**{state: True})
    with pytest.raises(services.PostNotFound):
        services.like(user=VerifiedUserFactory(), post_id=post.pk)
    assert Like.objects.count() == 0


def test_liking_an_unknown_post_raises():
    import uuid

    with pytest.raises(services.PostNotFound):
        services.like(user=VerifiedUserFactory(), post_id=uuid.uuid4())


def test_you_can_like_your_own_post():
    post = PostFactory()
    assert services.like(user=post.author, post_id=post.pk) is True


def test_unlike_removes_only_that_like_and_is_quiet_when_there_is_none():
    like = LikeFactory()
    other = LikeFactory(post=like.post)
    services.unlike(user=like.user, post_id=like.post_id)
    services.unlike(user=like.user, post_id=like.post_id)  # no error
    assert list(Like.objects.all()) == [other]


def test_a_like_can_be_taken_back_from_a_removed_post_but_not_a_deleted_one():
    removed = LikeFactory(post=PostFactory(removed=True))
    services.unlike(user=removed.user, post_id=removed.post_id)
    assert Like.objects.count() == 0
    deleted = LikeFactory(post=PostFactory(deleted=True))
    with pytest.raises(services.PostNotFound):
        services.unlike(user=deleted.user, post_id=deleted.post_id)
    assert Like.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_likes_by_one_user_make_one_row_and_no_error():
    user, post = VerifiedUserFactory(), PostFactory()

    def go():
        try:
            return services.like(user=user, post_id=post.pk)
        finally:
            connection.close()

    assert sorted(run_together(go, go)) == [False, True]
    assert Like.objects.filter(user=user, post=post).count() == 1


@pytest.mark.django_db(transaction=True)
def test_simultaneous_likes_by_different_users_are_all_counted():
    post = PostFactory()
    users = [VerifiedUserFactory() for _ in range(6)]

    def liker(user):
        def go():
            try:
                return services.like(user=user, post_id=post.pk)
            finally:
                connection.close()

        return go

    assert run_together(*(liker(u) for u in users)) == [True] * 6
    assert Like.objects.filter(post=post).count() == 6


# ---------- comments ----------


def test_add_comment_stores_it_with_the_given_time():
    post, user = PostFactory(), VerifiedUserFactory()
    moment = timezone.now() - timedelta(days=1)
    comment = services.add_comment(author=user, post_id=post.pk, content="Hello", now=moment)
    assert (comment.post_id, comment.author_id, comment.content) == (post.pk, user.pk, "Hello")
    assert comment.created_at == moment
    assert (comment.is_hidden, comment.deleted_at) == (False, None)


@pytest.mark.parametrize("state", ["removed", "deleted"])
def test_a_removed_or_deleted_post_cannot_be_commented_on(state):
    post = PostFactory(**{state: True})
    with pytest.raises(services.PostNotFound):
        services.add_comment(author=VerifiedUserFactory(), post_id=post.pk, content="Hi")
    assert Comment.objects.count() == 0


@pytest.mark.parametrize("state", ["fact", "under_review"])
def test_a_pending_or_under_review_post_can_be_commented_on(state):
    post = PostFactory(**{state: True})
    services.add_comment(author=VerifiedUserFactory(), post_id=post.pk, content="Hi")
    assert Comment.objects.count() == 1


def test_delete_comment_sets_deleted_at_and_keeps_the_row():
    comment = CommentFactory()
    moment = timezone.now() - timedelta(minutes=3)
    services.delete_comment(comment_id=comment.pk, user=comment.author, now=moment)
    comment.refresh_from_db()
    assert comment.deleted_at == moment
    assert comment.is_hidden is False
    assert Comment.objects.count() == 1


def test_only_the_author_can_delete_a_comment():
    comment = CommentFactory()
    with pytest.raises(services.NotCommentAuthor):
        services.delete_comment(comment_id=comment.pk, user=VerifiedUserFactory())
    comment.refresh_from_db()
    assert comment.deleted_at is None


@pytest.mark.parametrize(
    "make",
    [
        lambda: CommentFactory(hidden=True),
        lambda: CommentFactory(deleted=True),
        lambda: CommentFactory(post=PostFactory(removed=True)),
        lambda: CommentFactory(post=PostFactory(deleted=True)),
    ],
    ids=["hidden", "deleted", "post removed", "post deleted"],
)
def test_a_comment_nobody_can_see_is_not_found(make):
    comment = make()
    with pytest.raises(services.CommentNotFound):
        services.delete_comment(comment_id=comment.pk, user=comment.author)


def test_a_missing_comment_is_not_found():
    import uuid

    with pytest.raises(services.CommentNotFound):
        services.delete_comment(comment_id=uuid.uuid4(), user=VerifiedUserFactory())


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_deletes_give_one_success_and_one_not_found():
    comment = CommentFactory()

    def go():
        try:
            services.delete_comment(comment_id=comment.pk, user=comment.author)
            return "deleted"
        except services.CommentNotFound:
            return "not found"
        finally:
            connection.close()

    assert sorted(run_together(go, go)) == ["deleted", "not found"]
