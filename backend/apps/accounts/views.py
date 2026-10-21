import re
import uuid

from django.contrib.admin.models import LogEntry
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.utils import timezone
from django.utils.cache import get_conditional_response
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import avatars, cookies, deletion, export, services
from apps.accounts.models import Avatar, User
from apps.accounts.permissions import IsEmailVerified, PhotoUploadsAllowed
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


def _declared_length(request):
    try:
        return int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return 0


@method_decorator(never_cache, name="dispatch")
class AvatarView(APIView):
    """`PUT /api/v1/me/avatar/` (multipart `file`) sets the profile photo and answers the new `/me`
    object; `DELETE` removes it (204, also when there was none). ARCHITECTURE §4e.

    PUT needs a verified email (403 `email_unverified`) and uploads that aren't blocked (403
    `photo_uploads_blocked`); both are permissions, so they never count against the `avatar_upload`
    throttle (5 a day, PUT only). A photo that can't be used is a 400 with a code that counts. The
    file is read by `avatars.PhotoUploadHandler` (memory only, 5 MB) and processed under the decode
    gate; the original is never kept. DELETE needs a login only: someone blocked or unverified can
    still take their photo down."""

    parser_classes = [MultiPartParser]

    def get_permissions(self):
        if self.request.method == "PUT":
            return [IsAuthenticated(), IsEmailVerified(), PhotoUploadsAllowed()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.request.method != "PUT":
            return []
        self.throttle_scope = "avatar_upload"
        return [ScopedRateThrottle()]

    def put(self, request):
        # Refused before the body is read. A body that lies about its length is cut off by the
        # handler at 5 MB of file data.
        if _declared_length(request) > avatars.MAX_BODY_BYTES:
            raise avatars.PhotoRefused("photo_too_large")
        # Before anything reads the body: Django refuses to swap handlers after parsing.
        handler = avatars.PhotoUploadHandler(request._request)
        request._request.upload_handlers = [handler]
        files = request.FILES
        if handler.too_large:
            raise avatars.PhotoRefused("photo_too_large")
        upload = files.get("file")
        if upload is None:
            raise avatars.PhotoRefused("photo_missing")
        request.user.avatar_version = avatars.save_photo(request.user.pk, upload.read())
        return _me(request)

    def delete(self, request):
        avatars.delete_photo(request.user.pk)
        return Response(status=204)


# 16 hex characters of the version, then the size.
AVATAR_NAME = re.compile(r"([0-9a-f]{16})-(96|256)\.webp")
AVATAR_IMAGE_COLUMNS = {96: "image_96", 256: "image_256"}


class AvatarImageView(APIView):
    """`GET|HEAD /api/v1/avatars/{user_id}/{version}-{96|256}.webp`: public, the one place photo
    bytes leave the database (ARCHITECTURE §4e).

    A name that isn't a current version of that account's photo, at one of the two sizes, is a 404,
    so a replaced or removed photo's old URL stops working. The ETag is the name, so a repeat
    request with `If-None-Match` is answered 304 after an `exists()` that never loads the bytes. No
    authentication (a stale token must not turn a public image into a 401), no throttle, and not
    `never_cache`: the URL changes with the pixels, so the response is `immutable` for a year.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request, user_id, name):
        match = AVATAR_NAME.fullmatch(name)
        try:
            account_id = uuid.UUID(user_id)
        except ValueError:
            raise NotFound from None
        # One address per image: only the canonical spelling of the id.
        if match is None or str(account_id) != user_id:
            raise NotFound
        version, size = match.group(1), int(match.group(2))
        etag = f'"{version}-{size}"'
        rows = Avatar.objects.filter(user_id=account_id, version=version)
        response = get_conditional_response(request, etag=etag)
        if response is not None and response.status_code == 304:
            if not rows.exists():
                raise NotFound
        else:
            data = rows.values_list(AVATAR_IMAGE_COLUMNS[size], flat=True).first()
            if data is None:
                raise NotFound
            response = HttpResponse(bytes(data), content_type="image/webp")
        response["Cache-Control"] = "public, max-age=31536000, immutable"
        response["ETag"] = etag
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        response["Content-Disposition"] = 'inline; filename="avatar.webp"'
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
