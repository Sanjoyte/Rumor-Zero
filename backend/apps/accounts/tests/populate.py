"""An account with one of everything (export and deletion tests), plus other people's data that
must stay out of its export and survive its deletion."""

from datetime import timedelta
from decimal import Decimal

from allauth.socialaccount.models import SocialAccount
from django.utils import timezone

from apps.moderation.models import AppealKind, AppealStatus
from apps.moderation.tests.factories import AppealFactory, ModerationActionFactory, moderator_user
from apps.notifications.models import NotificationType
from apps.notifications.tests.factories import comment_item, follow_item, system_item
from apps.posts.models import PipelineVerdict, PostStatus, PostType, VerdictSource
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.reports.tests.factories import ReportFactory
from apps.reputation.models import EventKind
from apps.reputation.tests.factories import EventFactory, reversal_of
from apps.social.tests.factories import (
    BookmarkFactory,
    CommentFactory,
    FollowFactory,
    LikeFactory,
    RepostFactory,
)


def fill(user, tag=""):
    """One of everything the account owns, plus things of other people that must stay out."""
    other = VerifiedUserFactory(email=f"private{tag}@example.test", username=f"other_person{tag}")
    now = timezone.now()
    ago = lambda **kw: now - timedelta(**kw)  # noqa: E731

    fact = PostFactory(
        author=user,
        content="My fact",
        post_type=PostType.FACT,
        status=PostStatus.VERIFIED_FALSE,
        verdict_source=VerdictSource.PIPELINE,
        pipeline_verdict=PipelineVerdict.FALSE,
        confidence_score=Decimal("91.50"),
        verdict_note="Checked",
        sources=["https://example.test/a", "10.1000/xyz"],
        pipeline_result={"secret": "internals"},
        report_count=7,
        created_at=ago(days=5),
    )
    emergency = PostFactory(
        author=user,
        content="Alert",
        post_type=PostType.FACT,
        status=PostStatus.PENDING,
        is_emergency=True,
        emergency_expires_at=ago(days=-1),
        created_at=ago(days=4),
    )
    removed = PostFactory(author=user, content="Bad", removed=True, created_at=ago(days=3))
    ModerationActionFactory(
        post=removed,
        moderator=moderator_user(),
        public_note="Against the rules",
        notes="private moderator note",
        created_at=ago(days=2),
    )
    deleted = PostFactory(author=user, content="Gone", deleted=True, created_at=ago(days=2))
    PostFactory(author=other, content="Someone else's post", created_at=ago(days=1))

    CommentFactory(author=user, post=fact, content="Mine", created_at=ago(days=3))
    CommentFactory(author=user, post=emergency, content="Hidden", hidden=True)
    CommentFactory(author=user, post=emergency, content="Deleted", deleted=True)
    CommentFactory(author=other, post=fact, content="Not mine")

    LikeFactory(user=user, post=PostFactory(author=other))
    BookmarkFactory(user=user, post=PostFactory(author=other))
    RepostFactory(user=user, post=PostFactory(author=other), status_at_repost=PostStatus.PUBLISHED)
    FollowFactory(follower=user, following=other)
    FollowFactory(follower=other, following=user)
    ReportFactory(reporter=user, post=PostFactory(author=other), details="Looks fake")
    ReportFactory(reporter=other, post=fact)

    appeal = AppealFactory(
        post=fact,
        status=AppealStatus.UPHELD,
        reason="I disagree",
        resolved_by=moderator_user(),
        resolved_at=ago(days=1),
    )
    assert appeal.kind == AppealKind.LABEL

    row = EventFactory(user=user, kind=EventKind.FACT_FALSE, post=fact, created_at=ago(days=4))
    reversal_of(row)
    EventFactory(user=user, kind=EventKind.FACT_TRUE, post=deleted, created_at=ago(days=1))

    follow_item(user, other)
    comment_item(user, other, post=fact)
    system_item(user, NotificationType.UNDER_REVIEW, post=fact)
    system_item(user, NotificationType.REMOVED, post=removed, is_read=True)
    SocialAccount.objects.get_or_create(
        user=user, provider="google", defaults={"uid": f"g-{user.pk}"}
    )
    return {"fact": fact, "emergency": emergency, "removed": removed, "deleted": deleted}
