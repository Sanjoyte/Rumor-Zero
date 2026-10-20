"""Follow, like, comment and repost tell the right person once (ARCHITECTURE §2; Part 13), and a
deleted post or comment takes its items with it."""

from datetime import timedelta

import pytest
from django.contrib.admin.sites import site
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.models import Role
from apps.moderation.tests.factories import moderator_user
from apps.notifications.models import Notification, NotificationType
from apps.posts import services as post_services
from apps.posts.models import PostStatus
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.social import services
from apps.social.admin import CommentAdmin
from apps.social.models import Comment

pytestmark = pytest.mark.django_db


def items(**filters):
    return list(Notification.objects.filter(**filters).order_by("created_at", "id"))


# ---------- follow ----------


def test_a_follow_tells_the_person_followed():
    me, fan = VerifiedUserFactory(), VerifiedUserFactory()
    services.follow(follower=fan, target=me)
    item = Notification.objects.get()
    assert (item.type, item.recipient_id, item.actor_id) == (NotificationType.FOLLOW, me.pk, fan.pk)
    assert item.post_id is None and item.comment_id is None
    assert item.is_read is False


def test_following_twice_makes_one_item():
    me, fan = VerifiedUserFactory(), VerifiedUserFactory()
    assert services.follow(follower=fan, target=me) is True
    assert services.follow(follower=fan, target=me) is False
    assert Notification.objects.count() == 1


def test_follow_unfollow_follow_makes_one_item_and_keeps_it():
    me, fan = VerifiedUserFactory(), VerifiedUserFactory()
    services.follow(follower=fan, target=me)
    services.unfollow(follower=fan, target=me)
    assert Notification.objects.count() == 1  # a record, not a live state
    services.follow(follower=fan, target=me)
    assert Notification.objects.count() == 1


def test_following_yourself_writes_nothing():
    me = VerifiedUserFactory()
    with pytest.raises(services.SelfFollow):
        services.follow(follower=me, target=me)
    assert Notification.objects.count() == 0


# ---------- like ----------


def test_a_like_tells_the_posts_author():
    post = PostFactory()
    fan = VerifiedUserFactory()
    services.like(user=fan, post_id=post.pk)
    item = Notification.objects.get()
    assert (item.type, item.recipient_id, item.actor_id, item.post_id) == (
        NotificationType.LIKE,
        post.author_id,
        fan.pk,
        post.pk,
    )


def test_like_unlike_like_makes_one_item():
    post = PostFactory()
    fan = VerifiedUserFactory()
    services.like(user=fan, post_id=post.pk)
    services.unlike(user=fan, post_id=post.pk)
    services.like(user=fan, post_id=post.pk)
    assert Notification.objects.count() == 1


def test_liking_twice_makes_one_item():
    post = PostFactory()
    fan = VerifiedUserFactory()
    assert services.like(user=fan, post_id=post.pk) is True
    assert services.like(user=fan, post_id=post.pk) is False
    assert Notification.objects.count() == 1


def test_liking_your_own_post_writes_nothing():
    post = PostFactory()
    services.like(user=post.author, post_id=post.pk)
    assert Notification.objects.count() == 0


def test_two_people_liking_one_post_make_two_items():
    post = PostFactory()
    services.like(user=VerifiedUserFactory(), post_id=post.pk)
    services.like(user=VerifiedUserFactory(), post_id=post.pk)
    assert Notification.objects.count() == 2


def test_a_like_of_a_post_you_cannot_see_writes_nothing():
    post = PostFactory(removed=True)
    with pytest.raises(services.PostNotFound):
        services.like(user=VerifiedUserFactory(), post_id=post.pk)
    assert Notification.objects.count() == 0


# ---------- comment ----------


def test_a_comment_tells_the_posts_author_and_carries_the_comment():
    post = PostFactory()
    fan = VerifiedUserFactory()
    comment = services.add_comment(author=fan, post_id=post.pk, content="Nice")
    item = Notification.objects.get()
    assert (item.type, item.recipient_id, item.actor_id) == (
        NotificationType.COMMENT,
        post.author_id,
        fan.pk,
    )
    assert (item.post_id, item.comment_id) == (post.pk, comment.pk)


def test_every_comment_is_its_own_item():
    post = PostFactory()
    fan = VerifiedUserFactory()
    services.add_comment(author=fan, post_id=post.pk, content="One")
    services.add_comment(author=fan, post_id=post.pk, content="Two")
    assert Notification.objects.count() == 2


def test_commenting_on_your_own_post_writes_nothing():
    post = PostFactory()
    services.add_comment(author=post.author, post_id=post.pk, content="Note to self")
    assert Notification.objects.count() == 0


def test_deleting_a_comment_removes_its_item_and_only_its_item():
    post = PostFactory()
    fan = VerifiedUserFactory()
    gone = services.add_comment(author=fan, post_id=post.pk, content="Oops")
    kept = services.add_comment(author=fan, post_id=post.pk, content="Fine")
    services.delete_comment(comment_id=gone.pk, user=fan)
    assert [item.comment_id for item in Notification.objects.all()] == [kept.pk]


def _hide(comments, *, hidden=True):
    admin_site = CommentAdmin(Comment, site)
    request = RequestFactory().post("/")
    request.user = moderator_user()
    request.session = {}
    request._messages = FallbackStorage(request)
    admin_site._set_hidden(request, Comment.objects.filter(pk__in=[c.pk for c in comments]), hidden)


def test_hiding_a_comment_in_the_admin_removes_its_item_and_unhiding_does_not_bring_it_back():
    post = PostFactory()
    fan = VerifiedUserFactory()
    hidden = services.add_comment(author=fan, post_id=post.pk, content="Rude")
    shown = services.add_comment(author=fan, post_id=post.pk, content="Kind")
    _hide([hidden])
    assert [item.comment_id for item in Notification.objects.all()] == [shown.pk]
    _hide([hidden], hidden=False)
    assert [item.comment_id for item in Notification.objects.all()] == [shown.pk]


# ---------- repost ----------


def test_a_repost_tells_the_originals_author():
    post = PostFactory()
    fan = VerifiedUserFactory()
    services.repost(user=fan, post_id=post.pk)
    item = Notification.objects.get()
    assert (item.type, item.recipient_id, item.actor_id, item.post_id) == (
        NotificationType.REPOST,
        post.author_id,
        fan.pk,
        post.pk,
    )


def test_repost_unrepost_repost_makes_one_item():
    post = PostFactory()
    fan = VerifiedUserFactory()
    services.repost(user=fan, post_id=post.pk)
    services.unrepost(user=fan, post_id=post.pk)
    services.repost(user=fan, post_id=post.pk)
    services.repost(user=fan, post_id=post.pk)
    assert Notification.objects.count() == 1


def test_a_refused_repost_writes_nothing():
    own = PostFactory()
    with pytest.raises(services.CannotRepostOwn):
        services.repost(user=own.author, post_id=own.pk)
    false = PostFactory(moderator_verdict=True)
    with pytest.raises(services.CannotRepostFalse):
        services.repost(user=VerifiedUserFactory(), post_id=false.pk)
    assert Notification.objects.count() == 0


def test_a_like_and_a_repost_of_one_post_by_one_person_are_two_items():
    post = PostFactory()
    fan = VerifiedUserFactory()
    services.like(user=fan, post_id=post.pk)
    services.repost(user=fan, post_id=post.pk)
    assert sorted(Notification.objects.values_list("type", flat=True)) == ["like", "repost"]


def test_a_bookmark_tells_nobody():
    post = PostFactory()
    services.bookmark(user=VerifiedUserFactory(), post_id=post.pk)
    assert Notification.objects.count() == 0


# ---------- the author deletes the post ----------


def test_deleting_a_post_removes_every_item_about_it_and_only_those():
    post, other = PostFactory(), PostFactory()
    fan = VerifiedUserFactory()
    services.like(user=fan, post_id=post.pk)
    services.repost(user=fan, post_id=post.pk)
    services.add_comment(author=fan, post_id=post.pk, content="Hi")
    services.like(user=fan, post_id=other.pk)
    services.follow(follower=fan, target=post.author)
    post_services.delete_post(post_id=post.pk, user=post.author)
    left = Notification.objects.all()
    assert {(item.type, item.post_id) for item in left} == {
        (NotificationType.LIKE, other.pk),
        (NotificationType.FOLLOW, None),
    }


def test_the_status_of_a_deleted_post_does_not_matter():
    post = PostFactory(fact=True, status=PostStatus.PENDING)
    services.like(user=VerifiedUserFactory(), post_id=post.pk)
    post_services.delete_post(post_id=post.pk, user=post.author)
    assert Notification.objects.count() == 0


def test_a_moderator_account_is_just_another_actor():
    post = PostFactory()
    mod = VerifiedUserFactory(role=Role.MODERATOR)
    services.like(user=mod, post_id=post.pk)
    assert Notification.objects.get().actor_id == mod.pk


def test_a_comments_item_takes_the_comments_time():
    post = PostFactory()
    comment = services.add_comment(
        author=VerifiedUserFactory(),
        post_id=post.pk,
        content="Back then",
        now=timezone.now() - timedelta(days=1),
    )
    assert Notification.objects.get().created_at == comment.created_at
