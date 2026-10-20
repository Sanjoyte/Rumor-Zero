import uuid

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsEmailVerified
from apps.core.services import get_platform_settings
from apps.moderation.queries import appeal_defaults
from apps.posts import services
from apps.posts.emergency import active_emergency_q
from apps.posts.exceptions import (
    FactPostsPausedError,
    FactQuotaExceededError,
    NotAuthorError,
)
from apps.posts.models import Post
from apps.posts.pagination import EmergencyPagination, FeedPagination
from apps.posts.pinned import is_first_page, pinned_page, recent_pinnable
from apps.posts.serializers import (
    PostCreateSerializer,
    PostSerializer,
    fact_quota_data,
    feed_item,
    iso,
    status_item,
)
from apps.social.engagement import engagement_defaults

# `GET /api/v1/posts/status/?ids=` takes at most this many posts (ARCHITECTURE §9).
MAX_STATUS_IDS = 50


def parse_post_id(value):
    """The post id from the URL, or None. A malformed id is a JSON 404 from the view: a `<uuid:>`
    URL converter would answer Django's HTML 404 instead."""
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


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
        """Recent: every visible post but the active emergencies, which are pinned above it on the
        first page instead (Part 11C). One `now` for the filters and the serializer."""
        now = timezone.now()
        paginator = FeedPagination()
        page = paginator.paginate_queryset(
            Post.objects.visible().exclude(active_emergency_q(now)).for_list(request.user),
            request,
            view=self,
        )
        context = {"request": request, "now": now}
        posts = PostSerializer(page, many=True, context=context).data
        pinned, pinned_total = [], 0
        if is_first_page(request):
            rows, pinned_total = pinned_page(recent_pinnable(now), request.user)
            pinned = PostSerializer(rows, many=True, context=context).data
        return paginator.envelope(
            [feed_item(data) for data in posts],
            paginator.get_next_link(),
            pinned=pinned,
            pinned_total=pinned_total,
        )

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
        except services.EmergencyNotAllowed as exc:
            # Built by hand, not an `APIException`: a dict detail would turn a null
            # `next_allowed_at` into the string "None".
            return Response(
                {
                    "detail": exc.text,
                    "code": "emergency_not_allowed",
                    "reason": str(exc.reason),
                    "next_allowed_at": iso(exc.next_allowed_at),
                },
                status=403,
            )
        except services.FactPostsPaused:
            raise FactPostsPausedError from None
        except services.FactQuotaExceeded as exc:
            raise FactQuotaExceededError(
                limit=exc.limit, next_slot_at=exc.next_slot_at, now=now
            ) from None
        context = {"request": request, "now": now}
        post = appeal_defaults(engagement_defaults(post))
        return Response(PostSerializer(post, context=context).data, status=201)


@method_decorator(never_cache, name="dispatch")
class EmergencyListView(APIView):
    """`GET /api/v1/posts/emergencies/?feed=recent|following`: every active emergency the feed
    pins, newest first, for "Show all" (Part 11C). `recent` (the default) is public; `following`
    needs a login. `{results: [Post], next_cursor}`, 20 a page up to 50."""

    permission_classes = [AllowAny]

    def get(self, request):
        scope = request.query_params.get("feed", "recent")
        if scope not in ("recent", "following"):
            raise serializers.ValidationError({"feed": ["Choose recent or following."]})
        now = timezone.now()
        if scope == "following":
            if not request.user.is_authenticated:
                raise NotAuthenticated
            # Local: `social` depends on `posts`, not the other way round.
            from apps.social.feed import following_emergencies

            pinnable = following_emergencies(request.user, now)
        else:
            pinnable = recent_pinnable(now)
        paginator = EmergencyPagination()
        page = paginator.paginate_queryset(pinnable.for_list(request.user), request, view=self)
        context = {"request": request, "now": now}
        return paginator.get_paginated_response(
            PostSerializer(page, many=True, context=context).data
        )


@method_decorator(never_cache, name="dispatch")
class FactQuotaView(APIView):
    """`GET /api/v1/me/fact-quota/`: how many fact posts you have left in the rolling 24 h, and
    whether you may post an emergency now (Part 11C). A login is enough (not a verified email),
    so an unverified account learns its reason here. The same queries as before: you, and your
    fact posts of the window."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        quota = services.fact_quota(request.user, now=now)
        refused = services.emergency_refusal(request.user, quota=quota, now=now)
        block_days = get_platform_settings().emergency_false_cooldown_days
        return Response(fact_quota_data(quota, refused=refused, block_days=block_days))


@method_decorator(never_cache, name="dispatch")
class PostDetailView(APIView):
    """`GET /api/v1/posts/{id}/` (public) and `DELETE …/{id}/` (the author's soft delete).

    A deleted post is 404 for everyone, its author included. A removed post is the full object for
    its author and a tombstone for everyone else (`PostSerializer` blanks it). Like `PostListView`,
    permissions depend on the method. DELETE has no throttle of its own.
    """

    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method == "DELETE" else [AllowAny()]

    def get(self, request, post_id):
        pk = parse_post_id(post_id)
        post = (
            None
            if pk is None
            else Post.objects.not_deleted().for_list(request.user).filter(pk=pk).first()
        )
        if post is None:
            raise NotFound
        return Response(PostSerializer(post, context={"request": request}).data)

    def delete(self, request, post_id):
        pk = parse_post_id(post_id)
        if pk is None:
            raise NotFound
        try:
            services.delete_post(post_id=pk, user=request.user)
        except services.PostNotFound:
            raise NotFound from None
        except services.NotPostAuthor:
            raise NotAuthorError from None
        return Response(status=204)


@method_decorator(never_cache, name="dispatch")
class PostStatusView(APIView):
    """`GET /api/v1/posts/status/?ids=a,b`: the live status of up to 50 posts, for the badge poller.

    Public and uncached. It never authenticates (`authentication_classes = []`): a stale Bearer
    token would otherwise turn a public read into a 401, and the answer doesn't depend on who asks.
    Throttled per client IP by `status_poll`. Deleted and unknown ids are left out; a removed post
    answers `status: "removed"` and nothing else.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "status_poll"

    def get(self, request):
        ids = self._ids(request.query_params.get("ids", ""))
        posts = {
            post.pk: post
            for post in Post.objects.not_deleted()
            .filter(pk__in=ids)
            .only("id", "status", "confidence_score", "verdict_source")
        }
        return Response({"results": [status_item(posts[pk]) for pk in ids if pk in posts]})

    @staticmethod
    def _ids(raw):
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if not parts:
            raise serializers.ValidationError({"ids": ["Send the ids of the posts to check."]})
        ids = []
        for part in parts:
            pk = parse_post_id(part)
            if pk is None:
                raise serializers.ValidationError({"ids": [f"{part[:40]!r} isn't a post id."]})
            if pk not in ids:
                ids.append(pk)
        if len(ids) > MAX_STATUS_IDS:
            raise serializers.ValidationError(
                {"ids": [f"Check at most {MAX_STATUS_IDS} posts at a time."]}
            )
        return ids
