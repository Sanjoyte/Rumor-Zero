from django.contrib.admin.models import LogEntry
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import cookies, deletion, export, services
from apps.accounts.models import User
from apps.accounts.permissions import IsEmailVerified
from apps.accounts.serializers import (
    MAX_USERNAME_INPUT,
    MeSerializer,
    PasswordChangeSerializer,
    ProfileUpdateSerializer,
)
from apps.accounts.tokens import session_key_of_payload
from apps.accounts.validators import normalize_username, validate_username


class PasswordNotSet(APIException):
    status_code = 409
    default_code = "password_not_set"
    default_detail = "This account has no password. Use Forgot password to set one."


class StaffAccount(APIException):
    status_code = 403
    default_code = "staff_account"
    default_detail = (
        "Staff accounts can't delete themselves. Ask an admin to remove the role first."
    )


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


def _me(request):
    return Response(MeSerializer(request.user, context={"request": request}).data)


@method_decorator(never_cache, name="dispatch")
class MeView(APIView):
    """`GET /api/v1/me/` (anyone signed in), `PATCH` (the profile; verified email) and `DELETE`
    (the account). One URL, so the permission and the throttle scope depend on the method; a 401 or
    403 never counts against a scope."""

    THROTTLE_SCOPES = {"PATCH": "profile_update", "DELETE": "account_delete"}

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsAuthenticated(), IsEmailVerified()]
        return [IsAuthenticated()]

    def get_throttles(self):
        scope = self.THROTTLE_SCOPES.get(self.request.method)
        if scope is None:
            return []
        self.throttle_scope = scope
        return [ScopedRateThrottle()]

    def get(self, request):
        return _me(request)

    def patch(self, request):
        """Edit `display_name`, `username` and `bio`. Answers the new `/me` object."""
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.update_profile(request.user, serializer.validated_data)
        except services.UsernameTaken:
            raise ValidationError({"username": ["That username is taken."]}) from None
        return _me(request)

    def delete(self, request):
        """Delete the account. Body: `{password}`, or `{username}` for an account without a
        password. 204 and the cookies are expired; staff and anyone who wrote admin log entries
        get 403 `staff_account`."""
        user = request.user
        # Same rule as the admin's delete page: LogEntry.user cascades, and the admin history of a
        # former moderator would vanish with the account.
        if user.is_staff or LogEntry.objects.filter(user=user).exists():
            raise StaffAccount
        data = request.data if isinstance(request.data, dict) else {}
        if user.has_usable_password():
            password = data.get("password")
            if not isinstance(password, str) or not user.check_password(password[:1024]):
                raise ValidationError({"password": ["That password is not right."]})
        else:
            typed = data.get("username")
            if not isinstance(typed, str) or normalize_username(typed[:MAX_USERNAME_INPUT]) != (
                user.username
            ):
                raise ValidationError({"username": ["Type your username exactly to confirm."]})
        deletion.delete_account(user, session_key=session_key_of_payload(request.auth))
        response = Response(status=204)
        cookies.delete_auth_cookies(response)
        return response


@method_decorator(never_cache, name="dispatch")
class PasswordChangeView(APIView):
    """`POST /api/v1/me/password/` `{current_password, new_password}`: 204. A Google-only account
    (no usable password) gets 409 `password_not_set`; a wrong current password is a 400 on
    `current_password`. This device stays signed in, every other one ends at its next refresh."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_change"

    def post(self, request):
        user = request.user
        if not user.has_usable_password():
            raise PasswordNotSet
        serializer = PasswordChangeSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not user.check_password(data["current_password"]):
            raise ValidationError({"current_password": ["That password is not right."]})
        services.change_password(
            request._request,
            user,
            data["new_password"],
            session_key=session_key_of_payload(request.auth),
        )
        return Response(status=204)


@method_decorator(never_cache, name="dispatch")
class ExportView(APIView):
    """`GET /api/v1/me/export/`: everything stored about you, as a JSON download."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "data_export"

    def get(self, request):
        now = timezone.now()
        response = Response(export.build_export(request.user, now))
        name = export.filename(request.user, now)
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        return response


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
