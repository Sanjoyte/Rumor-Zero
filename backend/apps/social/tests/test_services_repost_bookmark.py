"""Reposts and bookmarks in `social.services`: the rules, their order, the cache bust, and what
simultaneous requests do."""

import threading
import uuid
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.tests.conftest import run_together
from apps.accounts.tests.factories import UserFactory
from apps.posts.models import Post, PostStatus
from apps.social import feed, services
from apps.social.models import Bookmark, Repost
from apps.social.tests.factories import (
    BookmarkFactory,
    PostFactory,
    RepostFactory,
    VerifiedUserFactory,
)

pytestmark = pytest.mark.django_db


# ---------- reposts ----------


def test_repost_creates_once_and_then_reports_it_already_existed():
    user, post = VerifiedUserFactory(), PostFactory()
    assert services.repost(user=user, post_id=post.pk) is True
    assert services.repost(user=user, post_id=post.pk) is False
    assert Repost.objects.filter(user=user, post=post).count() == 1


@pytest.mark.parametrize(
    ("traits", "status"),
    [
        ({}, PostStatus.PUBLISHED),
        ({"fact": True}, PostStatus.PENDING),
        ({"under_review": True}, PostStatus.UNDER_REVIEW),
        ({"verified_pipeline": True}, PostStatus.VERIFIED_TRUE),
    ],
)
def test_the_status_at_repost_is_recorded(traits, status):
    post = PostFactory(**traits)
    services.repost(user=VerifiedUserFactory(), post_id=post.pk)
    assert Repost.objects.get().status_at_repost == status


def test_the_first_status_is_kept_when_the_post_changes_and_you_repost_again():
    user, post = VerifiedUserFactory(), PostFactory(fact=True)
    services.repost(user=user, post_id=post.pk)
    post.status = PostStatus.VERIFIED_TRUE
    post.save()
    assert services.repost(user=user, post_id=post.pk) is False
    assert Repost.objects.get().status_at_repost == PostStatus.PENDING


def test_your_own_post_is_refused():
    post = PostFactory()
    with pytest.raises(services.CannotRepostOwn):
        services.repost(user=post.author, post_id=post.pk)
    assert Repost.objects.count() == 0


def test_a_false_post_is_refused():
    post = PostFactory(moderator_verdict=True)  # verified_false
    with pytest.raises(services.CannotRepostFalse):
        services.repost(user=VerifiedUserFactory(), post_id=post.pk)
    assert Repost.objects.count() == 0


def test_a_post_that_reports_sent_to_review_after_it_was_false_is_still_closed_to_reposts():
    """Reports move a FALSE post to review (§4); it keeps its label until a moderator decides
    (user decision 2026-10-10), so the review must not reopen it."""
    post = PostFactory(
        moderator_verdict=True,
        status=PostStatus.UNDER_REVIEW,
        pre_review_status=PostStatus.VERIFIED_FALSE,
        flagged_reason="reports",
    )
    with pytest.raises(services.CannotRepostFalse):
        services.repost(user=VerifiedUserFactory(), post_id=post.pk)
    assert Repost.objects.count() == 0


@pytest.mark.parametrize(
    "before", [PostStatus.PENDING, PostStatus.PUBLISHED, PostStatus.VERIFIED_TRUE, None]
)
def test_a_post_under_review_that_was_not_false_can_be_reposted(before):
    post = PostFactory(fact=True, under_review=True, pre_review_status=before)
    assert services.repost(user=VerifiedUserFactory(), post_id=post.pk) is True
    assert Repost.objects.get().status_at_repost == PostStatus.UNDER_REVIEW


def test_a_repost_you_already_made_survives_the_post_going_to_review_after_false():
    me = VerifiedUserFactory()
    post = PostFactory(fact=True)
    services.repost(user=me, post_id=post.pk)
    post.status, post.pre_review_status = PostStatus.UNDER_REVIEW, PostStatus.VERIFIED_FALSE
    post.review_started_at = timezone.now()
    post.save()
    assert services.repost(user=me, post_id=post.pk) is False  # a quiet 200, as for a FALSE post


def test_your_own_post_under_review_after_false_is_own_not_false():
    mine = PostFactory(
        moderator_verdict=True,
        status=PostStatus.UNDER_REVIEW,
        pre_review_status=PostStatus.VERIFIED_FALSE,
    )
    with pytest.raises(services.CannotRepostOwn):
        services.repost(user=mine.author, post_id=mine.pk)


@pytest.mark.parametrize("state", ["removed", "deleted"])
def test_a_removed_or_deleted_post_is_not_found_even_for_its_author(state):
    post = PostFactory(**{state: True})
    for user in (VerifiedUserFactory(), post.author):
        with pytest.raises(services.PostNotFound):
            services.repost(user=user, post_id=post.pk)


def test_an_unknown_post_is_not_found():
    with pytest.raises(services.PostNotFound):
        services.repost(user=VerifiedUserFactory(), post_id=uuid.uuid4())


def test_the_order_of_the_checks_not_found_then_existing_then_own_then_false():
    """A removed own post is 404, not 409; a FALSE post you already reposted is a quiet 200; your
    own FALSE post is 'own', not 'false'."""
    me = VerifiedUserFactory()
    removed_mine = PostFactory(author=me, removed=True)
    with pytest.raises(services.PostNotFound):
        services.repost(user=me, post_id=removed_mine.pk)
    already = PostFactory(fact=True)
    services.repost(user=me, post_id=already.pk)
    already.status = PostStatus.VERIFIED_FALSE
    already.save()
    assert services.repost(user=me, post_id=already.pk) is False
    mine_false = PostFactory(author=me, moderator_verdict=True)
    with pytest.raises(services.CannotRepostOwn):
        services.repost(user=me, post_id=mine_false.pk)


def test_repost_uses_the_given_time():
    when = timezone.now() - timedelta(days=2)
    services.repost(user=VerifiedUserFactory(), post_id=PostFactory().pk, now=when)
    assert Repost.objects.get().created_at == when


def test_unrepost_removes_only_that_repost_and_is_quiet_when_there_is_none():
    user, other, post = VerifiedUserFactory(), VerifiedUserFactory(), PostFactory()
    RepostFactory(user=user, post=post)
    theirs = RepostFactory(user=other, post=post)
    services.unrepost(user=user, post_id=post.pk)
    services.unrepost(user=user, post_id=post.pk)
    assert list(Repost.objects.all()) == [theirs]


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", PostStatus.REMOVED), ("deleted_at", timezone.now())],
    ids=["removed", "deleted"],
)
def test_a_repost_of_a_removed_or_deleted_post_can_still_be_taken_back(field, value):
    """User decision 2026-10-10: your own 'no longer available' card must be removable."""
    repost = RepostFactory()
    setattr(repost.post, field, value)
    repost.post.save()
    services.unrepost(user=repost.user, post_id=repost.post_id)
    assert Repost.objects.count() == 0


def test_unrepost_of_an_unknown_post_is_not_found():
    with pytest.raises(services.PostNotFound):
        services.unrepost(user=VerifiedUserFactory(), post_id=uuid.uuid4())


def test_repost_and_unrepost_forget_the_reposters_cached_feed():
    user, post = VerifiedUserFactory(), PostFactory()
    key = feed.cache_key(user.pk)
    cache.set(key, {"items": [], "next": None}, 60)
    services.repost(user=user, post_id=post.pk)
    assert cache.get(key) is None
    cache.set(key, {"items": [], "next": None}, 60)
    services.unrepost(user=user, post_id=post.pk)
    assert cache.get(key) is None


def test_the_cache_is_forgotten_again_at_commit(django_capture_on_commit_callbacks):
    user, post = VerifiedUserFactory(), PostFactory()
    key = feed.cache_key(user.pk)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        services.repost(user=user, post_id=post.pk)
    cache.set(key, {"items": [], "next": None}, 60)  # a reader refills it mid-transaction
    for callback in callbacks:
        callback()
    assert cache.get(key) is None


def test_a_refused_repost_leaves_the_cache_alone():
    post = PostFactory()
    key = feed.cache_key(post.author_id)
    cache.set(key, {"items": [], "next": None}, 60)
    with pytest.raises(services.CannotRepostOwn):
        services.repost(user=post.author, post_id=post.pk)
    assert cache.get(key) is not None


def test_another_users_cache_is_untouched_by_a_repost():
    user, other, post = VerifiedUserFactory(), VerifiedUserFactory(), PostFactory()
    key = feed.cache_key(other.pk)
    cache.set(key, {"items": [], "next": None}, 60)
    services.repost(user=user, post_id=post.pk)
    assert cache.get(key) is not None


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_reposts_by_one_user_make_one_row():
    user, post = VerifiedUserFactory(), PostFactory()

    def go():
        try:
            return services.repost(user=user, post_id=post.pk)
        finally:
            connection.close()

    assert sorted(run_together(go, go)) == [False, True]
    assert Repost.objects.filter(user=user, post=post).count() == 1


@pytest.mark.django_db(transaction=True)
def test_six_users_reposting_at_once_are_all_counted():
    post = PostFactory()
    users = [VerifiedUserFactory() for _ in range(6)]

    def reposter(user):
        def go():
            try:
                return services.repost(user=user, post_id=post.pk)
            finally:
                connection.close()

        return go

    assert run_together(*[reposter(u) for u in users]) == [True] * 6
    assert Repost.objects.filter(post=post).count() == 6


@pytest.mark.django_db(transaction=True)
def test_a_repost_waits_for_a_concurrent_status_change_and_records_the_status_at_commit():
    """The row lock: `status_at_repost` is what the post was when the repost committed."""
    post = PostFactory(fact=True)
    user = VerifiedUserFactory()
    with transaction.atomic():
        locked = Post.objects.select_for_update().get(pk=post.pk)
        done = threading.Event()
        outcome = {}

        def reposter():
            try:
                outcome["created"] = services.repost(user=user, post_id=post.pk)
            finally:
                connection.close()
                done.set()

        thread = threading.Thread(target=reposter)
        thread.start()
        assert not done.wait(0.5)  # blocked on our row lock
        locked.status = PostStatus.VERIFIED_TRUE
        locked.save()
    thread.join(timeout=30)
    assert outcome["created"] is True
    assert Repost.objects.get().status_at_repost == PostStatus.VERIFIED_TRUE


@pytest.mark.django_db(transaction=True)
def test_a_repost_that_waited_for_a_status_change_to_false_is_refused():
    post = PostFactory(fact=True)
    user = VerifiedUserFactory()
    errors = []
    done = threading.Event()

    def reposter():
        try:
            services.repost(user=user, post_id=post.pk)
        except services.CannotRepostFalse as exc:
            errors.append(exc)
        finally:
            connection.close()
            done.set()

    with transaction.atomic():
        locked = Post.objects.select_for_update().get(pk=post.pk)
        thread = threading.Thread(target=reposter)
        thread.start()
        assert not done.wait(0.5)
        locked.status = PostStatus.VERIFIED_FALSE
        locked.save()
    thread.join(timeout=30)
    assert len(errors) == 1
    assert Repost.objects.count() == 0


# ---------- bookmarks ----------


def test_bookmark_creates_once_and_then_reports_it_already_existed():
    user, post = VerifiedUserFactory(), PostFactory()
    assert services.bookmark(user=user, post_id=post.pk) is True
    assert services.bookmark(user=user, post_id=post.pk) is False
    assert Bookmark.objects.filter(user=user, post=post).count() == 1


@pytest.mark.parametrize(
    "traits",
    [
        {},
        {"fact": True},
        {"under_review": True},
        {"verified_pipeline": True},
        {"moderator_verdict": True},
    ],
)
def test_every_visible_status_can_be_bookmarked_your_own_and_false_ones_too(traits):
    post = PostFactory(**traits)
    assert services.bookmark(user=VerifiedUserFactory(), post_id=post.pk) is True
    assert services.bookmark(user=post.author, post_id=post.pk) is True


@pytest.mark.parametrize("state", ["removed", "deleted"])
def test_a_removed_or_deleted_post_cannot_be_bookmarked(state):
    post = PostFactory(**{state: True})
    with pytest.raises(services.PostNotFound):
        services.bookmark(user=VerifiedUserFactory(), post_id=post.pk)
    assert Bookmark.objects.count() == 0


def test_an_unverified_user_can_bookmark_at_the_service_level_too():
    assert services.bookmark(user=UserFactory(), post_id=PostFactory().pk) is True


def test_unbookmark_removes_only_that_bookmark_and_is_quiet_when_there_is_none():
    user, other, post = VerifiedUserFactory(), VerifiedUserFactory(), PostFactory()
    BookmarkFactory(user=user, post=post)
    theirs = BookmarkFactory(user=other, post=post)
    services.unbookmark(user=user, post_id=post.pk)
    services.unbookmark(user=user, post_id=post.pk)
    assert list(Bookmark.objects.all()) == [theirs]


def test_unbookmark_works_on_a_removed_post_but_not_a_deleted_or_unknown_one():
    removed = PostFactory(removed=True)
    BookmarkFactory(post=removed, user=(user := VerifiedUserFactory()))
    services.unbookmark(user=user, post_id=removed.pk)
    assert Bookmark.objects.count() == 0
    for post_id in (PostFactory(deleted=True).pk, uuid.uuid4()):
        with pytest.raises(services.PostNotFound):
            services.unbookmark(user=user, post_id=post_id)


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_bookmarks_by_one_user_make_one_row():
    user, post = VerifiedUserFactory(), PostFactory()

    def go():
        try:
            return services.bookmark(user=user, post_id=post.pk)
        finally:
            connection.close()

    assert sorted(run_together(go, go)) == [False, True]
    assert Bookmark.objects.filter(user=user, post=post).count() == 1
