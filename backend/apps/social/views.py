from django.db.models import Exists, OuterRef
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsEmailVerified
from apps.posts.exceptions import NotAuthorError
from apps.posts.models import Post, PostType
from apps.posts.pagination import FeedPagination
from apps.posts.serializers import PostSerializer, feed_item
from apps.posts.views import parse_post_id
from apps.social import feed, services
from apps.social.exceptions import CannotFollowSelfError
from apps.social.models import Comment, Follow
from apps.social.pagination import CommentPagination, UserListPagination
from apps.social.serializers import (
    CommentCreateSerializer,
    comment_data,
    profile_data,
    profile_queryset,
    user_row,
)


def _target_or_404(username):
    target = services.find_active_user(username)
    if target is None:
        raise NotFound
    return target


@method_decorator(never_cache, name="dispatch")
class ProfileView(APIView):
    """`GET /api/v1/users/{username}/`: public profile and counts, one query for the profile."""

    permission_classes = [AllowAny]

    def get(self, request, username):
        normalized = services.lookup_name(username)
        user = None
        if normalized is not None:
            user = profile_queryset(request.user).filter(username=normalized).first()
        if user is None:
            raise NotFound
        return Response(profile_data(user, request.user))


@method_decorator(never_cache, name="dispatch")
class UserPostsView(APIView):
    """`GET /api/v1/users/{username}/posts/`: the author's posts the public can see (§9 shape)."""

    permission_classes = [AllowAny]

    def get(self, request, username):
        target = _target_or_404(username)
        queryset = Post.objects.visible().filter(author=target).for_list(request.user)
        post_type = request.query_params.get("post_type")
        if post_type:
            if post_type not in PostType.values:
                raise serializers.ValidationError(
                    {"post_type": ["Choose fact or opinion, or leave it out."]}
                )
            queryset = queryset.filter(post_type=post_type)
        paginator = FeedPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        posts = PostSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response([feed_item(data) for data in posts])


class UserListView(APIView):
    """Followers or following of a user, newest follow first: `{results: [row], next_cursor}`.

    The rows are users; the cursor walks the follow rows. `is_following` is an `Exists`
    annotation, so the page is one query whoever asks.
    """

    permission_classes = [AllowAny]
    # The Follow column holding the person shown in each row, and the one holding the profile.
    person_field = "follower"
    owner_field = "following"

    def get(self, request, username):
        target = _target_or_404(username)
        viewer = request.user if request.user.is_authenticated else None
        person = self.person_field
        rows = Follow.objects.filter(**{self.owner_field: target, f"{person}__is_active": True})
        rows = rows.select_related(person)
        if viewer is not None:
            rows = rows.annotate(
                viewer_follows=Exists(
                    Follow.objects.filter(follower=viewer, following=OuterRef(f"{person}_id"))
                )
            )
        paginator = UserListPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        results = [
            user_row(
                getattr(row, person),
                is_following=bool(getattr(row, "viewer_follows", False)),
                viewer=viewer,
            )
            for row in page
        ]
        return paginator.get_paginated_response(results)


@method_decorator(never_cache, name="dispatch")
class FollowersView(UserListView):
    person_field = "follower"
    owner_field = "following"


@method_decorator(never_cache, name="dispatch")
class FollowingView(UserListView):
    person_field = "following"
    owner_field = "follower"


@method_decorator(never_cache, name="dispatch")
class FollowView(APIView):
    """`POST` / `DELETE /api/v1/users/{username}/follow/`: idempotent.

    Following needs a verified email (ARCHITECTURE §7); unfollowing only a login. Both use the
    `follow` throttle. The order is authentication, permissions (a 401 or 403 never counts), the
    throttle, then the lookup and the service.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "follow"

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsEmailVerified()]
        return [IsAuthenticated()]

    def post(self, request, username):
        target = _target_or_404(username)
        try:
            created = services.follow(follower=request.user, target=target)
        except services.SelfFollow:
            raise CannotFollowSelfError from None
        return Response({"is_following": True}, status=201 if created else 200)

    def delete(self, request, username):
        services.unfollow(follower=request.user, target=_target_or_404(username))
        return Response(status=204)


@method_decorator(never_cache, name="dispatch")
class FeedView(APIView):
    """`GET /api/v1/feed/`: posts by the people you follow and by you, newest first (§9).

    The first page is cached per user as a list of ids (`social.feed`); the posts themselves are
    read fresh every time.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        paginator = FeedPagination()
        posts, next_cursor = feed.following_page(request, self, request.user, paginator)
        data = PostSerializer(posts, many=True, context={"request": request}).data
        return paginator.envelope([feed_item(item) for item in data], next_cursor)


@method_decorator(never_cache, name="dispatch")
class LikeView(APIView):
    """`POST` / `DELETE /api/v1/posts/{id}/like/`: idempotent.

    Liking needs a verified email (ARCHITECTURE §7); taking a like back only a login. Both share
    the `like` throttle. Order: authentication, permissions (a 401 or 403 never counts), the
    throttle, then the lookup and the service. A malformed id is a JSON 404, never a URL
    converter's HTML one.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "like"

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsEmailVerified()]
        return [IsAuthenticated()]

    def post(self, request, post_id):
        pk = parse_post_id(post_id)
        if pk is None:
            raise NotFound
        try:
            created = services.like(user=request.user, post_id=pk)
        except services.PostNotFound:
            raise NotFound from None
        return Response({"liked": True}, status=201 if created else 200)

    def delete(self, request, post_id):
        pk = parse_post_id(post_id)
        if pk is None:
            raise NotFound
        try:
            services.unlike(user=request.user, post_id=pk)
        except services.PostNotFound:
            raise NotFound from None
        return Response(status=204)


@method_decorator(never_cache, name="dispatch")
class CommentListView(APIView):
    """`GET /api/v1/posts/{id}/comments/` (public, oldest first) and `POST` (a verified user).

    As on the post list, permissions and throttles depend on the method: reading must not use up
    the `comment` allowance. Hidden and deleted comments are in no list.
    """

    throttle_scope = "comment"

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsEmailVerified()]
        return [AllowAny()]

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def get(self, request, post_id):
        pk = parse_post_id(post_id)
        try:
            if pk is None:
                raise services.PostNotFound
            services.get_visible_post(pk)
        except services.PostNotFound:
            raise NotFound from None
        queryset = Comment.objects.filter(
            post_id=pk, is_hidden=False, deleted_at__isnull=True
        ).select_related("author")
        paginator = CommentPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(
            [comment_data(comment, request.user) for comment in page]
        )

    def post(self, request, post_id):
        pk = parse_post_id(post_id)
        if pk is None:
            raise NotFound
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            comment = services.add_comment(
                author=request.user, post_id=pk, content=serializer.validated_data["content"]
            )
        except services.PostNotFound:
            raise NotFound from None
        return Response(comment_data(comment, request.user), status=201)


@method_decorator(never_cache, name="dispatch")
class CommentDetailView(APIView):
    """`DELETE /api/v1/comments/{id}/`: the author's soft delete. No throttle of its own."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, comment_id):
        pk = parse_post_id(comment_id)
        if pk is None:
            raise NotFound
        try:
            services.delete_comment(comment_id=pk, user=request.user)
        except services.CommentNotFound:
            raise NotFound from None
        except services.NotCommentAuthor:
            raise NotAuthorError from None
        return Response(status=204)
