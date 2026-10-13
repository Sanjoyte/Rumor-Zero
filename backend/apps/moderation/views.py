from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsEmailVerified
from apps.moderation import services
from apps.moderation.exceptions import AlreadyAppealedError, NotAppealableError
from apps.moderation.serializers import AppealCreateSerializer
from apps.posts.exceptions import NotAuthorError
from apps.posts.models import Post
from apps.posts.serializers import PostSerializer
from apps.posts.views import parse_post_id


@method_decorator(never_cache, name="dispatch")
class AppealView(APIView):
    """`POST /api/v1/posts/{id}/appeal/`: ask for another look at your FALSE-labelled or removed
    post, once per post (ARCHITECTURE §4, §9).

    Order: authentication, permissions (a 401 or 403 `email_unverified` never counts), the `appeal`
    throttle (5 a day; from here on every answer counts, a 400, 404 or 409 included, as for
    reports), a malformed id (JSON 404), the body (400), then the service: a post that exists and
    isn't deleted (404), your own post (403 `not_author`), an earlier appeal (409
    `already_appealed`), a status that can't be appealed (409 `not_appealable`). The throttle is
    for POST only: DRF throttles before it finds the handler, so a GET would otherwise use up the
    allowance and then answer 405. The 201 is the post as its author now sees it.
    """

    permission_classes = [IsAuthenticated, IsEmailVerified]
    throttle_scope = "appeal"

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def post(self, request, post_id):
        pk = parse_post_id(post_id)
        if pk is None:
            raise NotFound
        serializer = AppealCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.file_appeal(
                author=request.user, post_id=pk, reason=serializer.validated_data["reason"]
            )
        except services.PostNotFound:
            raise NotFound from None
        except services.NotPostAuthor:
            raise NotAuthorError from None
        except services.AlreadyAppealed:
            raise AlreadyAppealedError from None
        except services.NotAppealable:
            raise NotAppealableError from None
        # `not_deleted`, not `visible`: a removed post is exactly what a removal appeal is about.
        post = Post.objects.not_deleted().for_list(request.user).get(pk=pk)
        return Response(PostSerializer(post, context={"request": request}).data, status=201)
