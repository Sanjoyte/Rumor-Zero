"""`Repost` and `Bookmark`: the unique pair, the allowed statuses, cascades and indexes."""

import pytest
from django.db import IntegrityError, transaction

from apps.posts.models import PostStatus
from apps.social.models import REPOSTABLE_STATUSES, Bookmark, Repost
from apps.social.tests.factories import (
    BookmarkFactory,
    PostFactory,
    RepostFactory,
    VerifiedUserFactory,
)

pytestmark = pytest.mark.django_db


def test_a_user_reposts_a_post_once():
    repost = RepostFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        Repost.objects.create(
            user=repost.user, post=repost.post, status_at_repost=PostStatus.PUBLISHED
        )


def test_a_user_bookmarks_a_post_once():
    bookmark = BookmarkFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        Bookmark.objects.create(user=bookmark.user, post=bookmark.post)


def test_two_users_can_repost_and_bookmark_the_same_post_and_one_user_many_posts():
    post = PostFactory()
    RepostFactory.create_batch(2, post=post)
    BookmarkFactory.create_batch(2, post=post)
    user = VerifiedUserFactory()
    RepostFactory.create_batch(2, user=user)
    BookmarkFactory.create_batch(2, user=user)
    assert Repost.objects.count() == 4 and Bookmark.objects.count() == 4


@pytest.mark.parametrize("status", REPOSTABLE_STATUSES)
def test_every_repostable_status_is_accepted(status):
    assert RepostFactory(status_at_repost=status).pk


@pytest.mark.parametrize("status", [PostStatus.VERIFIED_FALSE, PostStatus.REMOVED, "nonsense", ""])
def test_a_status_a_post_can_never_be_reposted_in_is_refused_by_the_database(status):
    with pytest.raises(IntegrityError), transaction.atomic():
        RepostFactory(status_at_repost=status)


def test_the_repostable_statuses_are_exactly_the_four_the_architecture_allows():
    assert set(REPOSTABLE_STATUSES) == {
        PostStatus.PENDING,
        PostStatus.PUBLISHED,
        PostStatus.VERIFIED_TRUE,
        PostStatus.UNDER_REVIEW,
    }


def test_deleting_a_post_or_a_user_removes_their_reposts_and_bookmarks():
    repost, bookmark = RepostFactory(), BookmarkFactory()
    repost.post.delete()
    bookmark.user.delete()
    assert Repost.objects.count() == 0 and Bookmark.objects.count() == 0
    mine = RepostFactory()
    mine.user.delete()
    assert Repost.objects.count() == 0


def test_the_ids_are_bigint():
    assert Repost._meta.pk.get_internal_type() == "BigAutoField"
    assert Bookmark._meta.pk.get_internal_type() == "BigAutoField"


def test_the_indexes_and_constraints_are_the_documented_ones():
    reposts = {i.name: i.fields for i in Repost._meta.indexes}
    assert reposts == {
        "reposts_post_created_idx": ["post", "created_at"],
        "reposts_user_created_idx": ["user", "-created_at", "-post"],
    }
    assert {c.name for c in Repost._meta.constraints} == {
        "reposts_pair_unique",
        "reposts_status_allowed",
    }
    bookmarks = {i.name: i.fields for i in Bookmark._meta.indexes}
    assert bookmarks == {"bookmarks_user_created_idx": ["user", "-created_at", "-id"]}
    assert {c.name for c in Bookmark._meta.constraints} == {"bookmarks_pair_unique"}


def test_the_string_forms_name_both_sides():
    repost, bookmark = RepostFactory(), BookmarkFactory()
    assert str(repost.post_id) in str(repost) and str(repost.user_id) in str(repost)
    assert str(bookmark.post_id) in str(bookmark)
