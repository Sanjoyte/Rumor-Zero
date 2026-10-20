from django.db.models import Exists, OuterRef, Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.pagination import CursorPagination, TimestampCursorMixin
from apps.notifications import services
from apps.notifications.models import Notification
from apps.notifications.serializers import MarkReadSerializer, notification_data
from apps.social.models import Follow


class NotificationPagination(TimestampCursorMixin, CursorPagination):
    """Newest first (`{results, next_cursor}`, §9 envelope). The id breaks ties; an action's items
    are 1 µs apart, so the order inside one action is stable."""

    ordering = ("-created_at", "-id")


class NotificationView(APIView):
    """Behind a login, `never_cache`d, and counted by the one `notifications` allowance (a tab
    polls twice a minute, so 120 a minute leaves room for several). A 401 never counts."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "notifications"


@method_decorator(never_cache, name="dispatch")
class NotificationListView(NotificationView):
    """`GET /api/v1/notifications/`: 2 queries (the user, the page).

    The actor, post and comment come in the same query; `following` is an `Exists`. Items whose
    post the author deleted are left out (the cleanup normally removed them already; a like that
    commits just after the delete is the one case it can't see).
    """

    def get(self, request):
        rows = (
            Notification.objects.filter(recipient=request.user)
            .filter(Q(post__isnull=True) | Q(post__deleted_at__isnull=True))
            .select_related("actor", "post", "comment")
            .only(
                "type",
                "outcome",
                "is_read",
                "created_at",
                "actor__username",
                "actor__display_name",
                "actor__avatar_version",
                "actor__is_active",
                "post__content",
                "post__post_type",
                "post__status",
                "comment__content",
            )
            .annotate(
                actor_following=Exists(
                    Follow.objects.filter(follower=request.user, following=OuterRef("actor_id"))
                )
            )
        )
        paginator = NotificationPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response([notification_data(row) for row in page])


@method_decorator(never_cache, name="dispatch")
class UnreadCountView(NotificationView):
    """`GET /api/v1/notifications/unread-count/`: `{"count": n}`, exact and uncached; 2 queries
    (the user, the count on the partial index)."""

    def get(self, request):
        return Response({"count": services.unread_count(request.user)})


@method_decorator(never_cache, name="dispatch")
class MarkReadView(NotificationView):
    """`POST /api/v1/notifications/mark-read/`: `{"ids": [...]}` or `{"all": true}` → `{"count":
    <unread left>}`. Only your own unread items change; other people's ids are ignored."""

    def post(self, request):
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data.get("ids")
        return Response({"count": services.mark_read(request.user, ids=ids)})
