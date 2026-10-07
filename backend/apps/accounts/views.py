from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import cookies, services
from apps.accounts.models import User
from apps.accounts.serializers import MeSerializer
from apps.accounts.validators import normalize_username, validate_username

# Longer input is rejected before normalising it.
MAX_USERNAME_INPUT = 64


# AuthApiMiddleware checks Origin and X-Requested-With instead of Django's CSRF check, which can't
# work here: through the relay, Host is the backend and Origin is the frontend.
@csrf_exempt
@require_POST
@never_cache
def logout_view(request):
    """`POST /api/auth/logout/`: end the session behind the refresh cookie. Always 204."""
    cookies.revoke_refresh_token_session(request.COOKIES.get(cookies.REFRESH_COOKIE, ""))
    response = HttpResponse(status=204)
    cookies.delete_auth_cookies(response)
    return response


@method_decorator(never_cache, name="dispatch")
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user, context={"request": request}).data)


@method_decorator(never_cache, name="dispatch")
class VerificationEmailView(APIView):
    """`POST /api/v1/me/verification-email/`: send the signed-in user a new verification link.

    204 sent, 409 `already_verified`, 429 `verification_email_throttled`. The 429 has no
    Retry-After: the full bucket may be the 60 s one or the daily one.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        outcome = services.resend_verification_email(request._request, request.user)
        if outcome == services.SENT:
            return Response(status=204)
        if outcome == services.ALREADY_VERIFIED:
            return Response(
                {"detail": "Your email is already verified.", "code": "already_verified"},
                status=409,
            )
        return Response(
            {
                "detail": "We sent one recently. Wait a little before asking again.",
                "code": "verification_email_throttled",
            },
            status=429,
        )


@method_decorator(never_cache, name="dispatch")
class UsernameAvailableView(APIView):
    """`GET /api/v1/auth/username-available/?u=` for the live check on the sign-up form."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "username_check"

    def get(self, request):
        raw = request.query_params.get("u")
        if raw is None:
            raise ValidationError({"u": ["This query parameter is required."]})
        username = normalize_username(raw[:MAX_USERNAME_INPUT])
        if len(raw) > MAX_USERNAME_INPUT:
            return self._answer(username, "invalid", "Usernames are 3–30 characters.")
        try:
            validate_username(username)
        except DjangoValidationError as exc:
            reason = "reserved" if exc.code == "reserved_username" else "invalid"
            return self._answer(username, reason, exc.messages[0])
        if User.objects.filter(username=username).exists():
            return self._answer(username, "taken", "That username is taken.")
        return self._answer(username, None, "Available")

    @staticmethod
    def _answer(username, reason, message):
        return Response(
            {
                "username": username,
                "available": reason is None,
                "reason": reason,
                "message": message,
            }
        )
