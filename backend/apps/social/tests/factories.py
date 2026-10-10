import factory
from django.utils import timezone

from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory
from apps.social.models import Comment, Follow, Like


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


__all__ = [
    "CommentFactory",
    "FollowFactory",
    "LikeFactory",
    "PostFactory",
    "UserFactory",
    "VerifiedUserFactory",
]
