import factory
from django.utils import timezone

from apps.accounts.models import Role
from apps.moderation.models import ActionKind, ModerationAction
from apps.posts.models import PostStatus
from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory


def moderator_user(**fields):
    return VerifiedUserFactory(role=Role.MODERATOR, **fields)


def senior_user(**fields):
    return VerifiedUserFactory(role=Role.SENIOR_MODERATOR, **fields)


class ModerationActionFactory(factory.django.DjangoModelFactory):
    """A finished `removed` action by a moderator. Rows are written once, so every field is set
    here; the services are what make them in production."""

    class Meta:
        model = ModerationAction

    post = factory.SubFactory(PostFactory)
    post_snapshot = factory.LazyAttribute(lambda row: row.post.content if row.post else "")
    moderator = factory.SubFactory(VerifiedUserFactory, role=Role.MODERATOR)
    action = ActionKind.REMOVED
    from_status = PostStatus.PUBLISHED
    to_status = PostStatus.REMOVED
    created_at = factory.LazyFunction(timezone.now)


__all__ = [
    "ModerationActionFactory",
    "PostFactory",
    "UserFactory",
    "VerifiedUserFactory",
    "moderator_user",
    "senior_user",
]
