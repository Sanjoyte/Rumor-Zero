from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsEmailVerified
from apps.posts import services
from apps.posts.exceptions import (
    EmergencyUnavailableError,
    FactPostsPausedError,
    FactQuotaExceededError,
)
from apps.posts.models import Post
from apps.posts.pagination import FeedPagination
from apps.posts.serializers import (
    PostCreateSerializer,
    PostSerializer,
    fact_quota_data,
    feed_item,
)


@method_decorator(never_cache, name="dispatch")
class PostListView(APIView):
    """`GET /api/v1/posts/` (public Recent feed) and `POST /api/v1/posts/` (create a post).

    One view with two jobs, so permissions and throttles depend on the method: DRF runs throttles
    on every request, and reading the feed must not use up the posting allowance. The check order
    is authentication, permissions (401/403), the throttle (429 `throttled`), validation (400),
    then the service (400/403/429). So a 401 or 403 never counts against `post_create`, but a 400
    or a quota refusal does.
    """

    throttle_scope = "post_create"

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsEmailVerified()]
        return [AllowAny()]

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def get(self, request):
        paginator = FeedPagination()
        page = paginator.paginate_queryset(Post.objects.visible().for_list(), request, view=self)
        posts = PostSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response([feed_item(data) for data in posts])

    def post(self, request):
        serializer = PostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        now = timezone.now()
        try:
            post = services.create_post(
                author=request.user,
                content=data["content"],
                post_type=data["post_type"],
                sources=data.get("sources", []),
                is_emergency=data["is_emergency"],
                now=now,
            )
        except services.EmergencyUnavailable:
            raise EmergencyUnavailableError from None
        except services.FactPostsPaused:
            raise FactPostsPausedError from None
        except services.FactQuotaExceeded as exc:
            raise FactQuotaExceededError(
                limit=exc.limit, next_slot_at=exc.next_slot_at, now=now
            ) from None
        context = {"request": request, "now": now}
        return Response(PostSerializer(post, context=context).data, status=201)


@method_decorator(never_cache, name="dispatch")
class FactQuotaView(APIView):
    """`GET /api/v1/me/fact-quota/`: how many fact posts you have left in the rolling 24 h."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(fact_quota_data(services.fact_quota(request.user)))
