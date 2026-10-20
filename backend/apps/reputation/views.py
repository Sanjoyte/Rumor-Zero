from datetime import UTC

from django.db.models import OuterRef, Subquery
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.pagination import CursorPagination, TimestampCursorMixin
from apps.posts.models import Post, PostStatus
from apps.reputation import scoring, trend
from apps.reputation.models import ReputationEvent
from apps.reputation.serializers import event_data, is_reversed, recent_events, reputation_data
from apps.social.engagement import count_subquery
from apps.social.services import lookup_name


def _by_status(status):
    # Deleted posts included: deleting a post doesn't erase its record (as the profile's counts).
    return count_subquery(Post.objects.filter(author=OuterRef("pk"), status=status), "author")


def _last_by_day(user, start):
    """`{date: score_after}` of the last row of each UTC day since `start` (one `DISTINCT ON`
    query). A person's rows have strictly increasing times, so "last" has no ties."""
    rows = (
        ReputationEvent.objects.filter(user=user, created_at__gte=start)
        .annotate(day=TruncDate("created_at", tzinfo=UTC))
        .order_by("day", "-created_at")
        .distinct("day")
        .values_list("day", "score_after")
    )
    return dict(rows)


@method_decorator(never_cache, name="dispatch")
class ReputationView(APIView):
    """`GET /api/v1/users/{username}/reputation/`: an account's public credibility summary.

    Public, uncached, and it **never authenticates** (`authentication_classes = []`, like the
    status poller): the answer doesn't depend on who asks, so a stale token isn't a 401. Two
    queries: the account with its three counts and the score before the trend's window, then its
    recent own-post events; a third (the last row of each UTC day) only while the score is public.
    The score and `trend` are null until three events count (ARCHITECTURE §4a).
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, username):
        name = lookup_name(username)
        user = None
        today = timezone.now().astimezone(UTC).date()
        start = trend.window_start(today)
        if name is not None:
            before = ReputationEvent.objects.filter(
                user=OuterRef("pk"), created_at__lt=start
            ).order_by("-created_at")
            user = (
                User.objects.filter(username=name, is_active=True)
                .only("id", "reputation_score", "reputation_sample")
                .annotate(
                    verified_n=_by_status(PostStatus.VERIFIED_TRUE),
                    false_n=_by_status(PostStatus.VERIFIED_FALSE),
                    removed_n=_by_status(PostStatus.REMOVED),
                    trend_base=Subquery(before.values("score_after")[:1]),
                )
                .first()
            )
        if user is None:
            raise NotFound
        points = None
        if scoring.public_score(user.reputation_score, user.reputation_sample) is not None:
            points = trend.build_trend(user.trend_base, _last_by_day(user, start), today)
        return Response(reputation_data(user, recent_events(user), points))


class ReputationEventPagination(TimestampCursorMixin, CursorPagination):
    """Your ledger, newest first; a crafted cursor is a 404."""

    ordering = ("-created_at", "-id")


@method_decorator(never_cache, name="dispatch")
class MyReputationEventsView(APIView):
    """`GET /api/v1/me/reputation/events/`: your whole ledger, reversals included, newest first
    (`{results, next_cursor}`). Only ever your own. Two queries: you, then the page."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = (
            ReputationEvent.objects.filter(user=request.user)
            .select_related("post", "post__appeal", "reverses")
            .defer("post__pipeline_result", "post__content", "post__sources")
            .annotate(is_reversed=is_reversed())
        )
        paginator = ReputationEventPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response([event_data(row) for row in page])
