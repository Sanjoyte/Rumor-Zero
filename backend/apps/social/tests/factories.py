import factory
from django.utils import timezone

from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory
from apps.social.models import Follow


class FollowFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Follow

    follower = factory.SubFactory(VerifiedUserFactory)
    following = factory.SubFactory(VerifiedUserFactory)
    created_at = factory.LazyFunction(timezone.now)


__all__ = ["FollowFactory", "PostFactory", "UserFactory", "VerifiedUserFactory"]
