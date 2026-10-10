from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsEmailVerified
from apps.posts.views import parse_post_id
from apps.reports import services
from apps.reports.exceptions import AlreadyReportedError, CannotReportOwnError
from apps.reports.serializers import ReportCreateSerializer


@method_decorator(never_cache, name="dispatch")
class ReportView(APIView):
    """`POST /api/v1/posts/{id}/report/`: one report per person and post, for a verified email.

    Order: authentication, permissions (a 401 or 403 `email_unverified` never counts), the
    `report` throttle (10 an hour; from here on every answer counts, a 400, 404 or 409 included,
    as for reposts), a malformed id (JSON 404), the body (400), then the service: a post the public
    can see (404), your own post (403 `cannot_report_own`), an earlier report (409
    `already_reported`). The answer is always the same 201: it never says whether this report
    sent the post to review.
    """

    permission_classes = [IsAuthenticated, IsEmailVerified]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "report"

    def post(self, request, post_id):
        pk = parse_post_id(post_id)
        if pk is None:
            raise NotFound
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.file_report(
                reporter=request.user,
                post_id=pk,
                reason=serializer.validated_data["reason"],
                details=serializer.validated_data["details"],
            )
        except services.PostNotFound:
            raise NotFound from None
        except services.CannotReportOwn:
            raise CannotReportOwnError from None
        except services.AlreadyReported:
            raise AlreadyReportedError from None
        return Response({"reported": True}, status=201)
