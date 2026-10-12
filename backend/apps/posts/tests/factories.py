from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.posts.models import PipelineVerdict, Post, PostStatus, PostType, VerdictSource


class VerifiedUserFactory(UserFactory):
    is_email_verified = True


class PostFactory(factory.django.DjangoModelFactory):
    """An opinion by a verified author by default; the traits make the other shapes.

    Give every post in a list its own `created_at`: the feed's cursor falls back to a plain
    offset when a whole page shares one timestamp (a test-only situation).
    """

    class Meta:
        model = Post

    author = factory.SubFactory(VerifiedUserFactory)
    content = factory.Sequence(lambda n: f"Post number {n}")
    post_type = PostType.OPINION
    status = PostStatus.PUBLISHED
    created_at = factory.LazyFunction(timezone.now)
    # The database holds this to "set exactly while under review", so a post made under review
    # gets the moment the queue's clock started (the post's own `created_at` unless given).
    review_started_at = factory.LazyAttribute(
        lambda post: post.created_at if post.status == PostStatus.UNDER_REVIEW else None
    )

    class Params:
        fact = factory.Trait(post_type=PostType.FACT, status=PostStatus.PENDING)
        verified_pipeline = factory.Trait(
            post_type=PostType.FACT,
            status=PostStatus.VERIFIED_TRUE,
            verdict_source=VerdictSource.PIPELINE,
            pipeline_verdict=PipelineVerdict.TRUE,
            confidence_score=Decimal("94.00"),
        )
        moderator_verdict = factory.Trait(
            post_type=PostType.FACT,
            status=PostStatus.VERIFIED_FALSE,
            verdict_source=VerdictSource.MODERATOR,
        )
        under_review = factory.Trait(status=PostStatus.UNDER_REVIEW)
        removed = factory.Trait(status=PostStatus.REMOVED)
        deleted = factory.Trait(deleted_at=factory.LazyFunction(timezone.now))


__all__ = ["PostFactory", "UserFactory", "VerifiedUserFactory"]
