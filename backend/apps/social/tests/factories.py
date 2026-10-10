import factory
from django.utils import timezone

from apps.posts.models import PostStatus
from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory
from apps.social.models import Bookmark, Comment, Follow, Like, Repost


class FollowFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Follow

    follower = factory.SubFactory(VerifiedUserFactory)
    following = factory.SubFactory(VerifiedUserFactory)
    created_at = factory.LazyFunction(timezone.now)


class LikeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Like

    user = factory.SubFactory(VerifiedUserFactory)
    post = factory.SubFactory(PostFactory)
    created_at = factory.LazyFunction(timezone.now)


class CommentFactory(factory.django.DjangoModelFactory):
    """A shown comment by a verified user. Give every comment on one post its own `created_at`
    (the cursor falls back to a plain offset when a whole page shares one timestamp)."""

    class Meta:
        model = Comment

    post = factory.SubFactory(PostFactory)
    author = factory.SubFactory(VerifiedUserFactory)
    content = factory.Sequence(lambda n: f"Comment number {n}")
    created_at = factory.LazyFunction(timezone.now)

    class Params:
        hidden = factory.Trait(is_hidden=True)
        deleted = factory.Trait(deleted_at=factory.LazyFunction(timezone.now))


class RepostFactory(factory.django.DjangoModelFactory):
    """A repost by a verified user of someone else's post. Give every item in a list its own
    `created_at` unless the test is about ties."""

    class Meta:
        model = Repost

    user = factory.SubFactory(VerifiedUserFactory)
    post = factory.SubFactory(PostFactory)
    status_at_repost = PostStatus.PUBLISHED
    created_at = factory.LazyFunction(timezone.now)


class BookmarkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Bookmark

    user = factory.SubFactory(VerifiedUserFactory)
    post = factory.SubFactory(PostFactory)
    created_at = factory.LazyFunction(timezone.now)


__all__ = [
    "BookmarkFactory",
    "CommentFactory",
    "FollowFactory",
    "LikeFactory",
    "PostFactory",
    "RepostFactory",
    "UserFactory",
    "VerifiedUserFactory",
]
