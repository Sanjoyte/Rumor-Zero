"""`social.Like` and `social.Comment` (ARCHITECTURE §2): the like pair is unique, a comment is 1 to
500 code points, and the indexes exist (the comment one only over the comments that are shown)."""

import pytest
from django.db import IntegrityError, connection, transaction

from apps.social.models import Comment, Like
from apps.social.tests.factories import (
    CommentFactory,
    LikeFactory,
    PostFactory,
    VerifiedUserFactory,
)

pytestmark = pytest.mark.django_db


def test_a_like_links_a_user_and_a_post():
    like = LikeFactory()
    assert str(like) == f"{like.user_id} likes {like.post_id}"


def test_the_like_pair_is_unique_at_the_database_level():
    like = LikeFactory()
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        Like.objects.create(user=like.user, post=like.post)
    assert "likes_pair_unique" in str(caught.value)


def test_one_user_can_like_two_posts_and_two_users_one_post():
    like = LikeFactory()
    Like.objects.create(user=like.user, post=PostFactory())
    Like.objects.create(user=VerifiedUserFactory(), post=like.post)
    assert Like.objects.count() == 3


@pytest.mark.parametrize("content", ["", "x" * 501])
def test_the_database_refuses_empty_and_over_long_comments(content):
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        CommentFactory(content=content)
    assert "comments_content_length" in str(caught.value)


@pytest.mark.parametrize("content", ["x", "x" * 500, "😀" * 500])
def test_the_database_accepts_one_to_500_code_points(content):
    assert CommentFactory(content=content).pk  # an emoji is one character, not two


def test_a_comment_is_shown_until_it_is_hidden_or_deleted():
    comment = CommentFactory()
    assert (comment.is_hidden, comment.deleted_at) == (False, None)
    assert CommentFactory(hidden=True).is_hidden
    assert CommentFactory(deleted=True).deleted_at is not None


def test_comment_ids_are_uuids():
    assert len(str(CommentFactory().pk)) == 36


def test_the_like_and_comment_indexes_exist():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename IN ('social_like', 'social_comment')"
        )
        indexes = dict(cursor.fetchall())
    assert "(post_id, created_at)" in indexes["likes_post_created_idx"]
    visible = indexes["comments_post_visible_idx"]
    assert "(post_id, created_at, id)" in visible
    assert "deleted_at IS NULL" in visible
    assert "NOT is_hidden" in visible


def test_deleting_a_post_deletes_its_likes_and_comments():
    like, comment = LikeFactory(), CommentFactory()
    like.post.delete()
    comment.post.delete()
    assert (Like.objects.count(), Comment.objects.count()) == (0, 0)


def test_deleting_a_user_deletes_their_likes_and_comments():
    like, comment = LikeFactory(), CommentFactory()
    like.user.delete()
    comment.author.delete()
    assert (Like.objects.count(), Comment.objects.count()) == (0, 0)
