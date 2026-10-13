import factory
from django.utils import timezone

from apps.accounts.models import Role
from apps.moderation.models import ActionKind, Appeal, AppealKind, ModerationAction
from apps.posts.models import FlaggedReason, PostStatus, PostType, VerdictSource
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


class AppealFactory(factory.django.DjangoModelFactory):
    """An open appeal by the post's author. The default is a label appeal on a FALSE fact that the
    appeal put back under review; `removal=True` makes a removal appeal on a removed fact. (The
    services build both in production; this makes the same rows.)"""

    class Meta:
        model = Appeal

    class Params:
        removal = factory.Trait(
            kind=AppealKind.REMOVAL,
            post=factory.SubFactory(
                PostFactory,
                post_type=PostType.FACT,
                status=PostStatus.REMOVED,
                flagged_reason=FlaggedReason.APPEAL,
                pre_removal_status=PostStatus.VERIFIED_FALSE,
            ),
        )

    kind = AppealKind.LABEL
    post = factory.SubFactory(
        PostFactory,
        post_type=PostType.FACT,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.APPEAL,
        pre_review_status=PostStatus.VERIFIED_FALSE,
        verdict_source=VerdictSource.PIPELINE,
    )
    author = factory.SelfAttribute("post.author")
    reason = ""
    created_at = factory.LazyFunction(timezone.now)


__all__ = [
    "AppealFactory",
    "ModerationActionFactory",
    "PostFactory",
    "UserFactory",
    "VerifiedUserFactory",
    "moderator_user",
    "senior_user",
]
