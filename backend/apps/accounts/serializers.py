import unicodedata

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.validators import normalize_username, validate_username
from apps.reputation.scoring import public_score


def avatar_url(user, size=96):
    """`/api/v1/avatars/{user_id}/{avatar_version}-{size}.webp`, or None for initials (§9). Lists
    use the default 96 px; `/me` and a profile ask for 256 (the settings preview and the header are
    56 and 80 px, crisp at 2x)."""
    if not user.avatar_version:
        return None
    return f"/api/v1/avatars/{user.pk}/{user.avatar_version}-{size}.webp"


def user_summary(user):
    """The public bits of a user inside other objects (post authors, reposters): §9."""
    return {
        "id": str(user.pk),
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": avatar_url(user),
    }


class UserSummarySerializer(serializers.BaseSerializer):
    """`{id, username, display_name, avatar_url}`; never the email, role or credibility."""

    def to_representation(self, user):
        return user_summary(user)


class MeSerializer(serializers.ModelSerializer):
    """`GET /api/v1/me/` (ARCHITECTURE §9). Staff also get `admin_url`."""

    has_usable_password = serializers.SerializerMethodField()
    google_connected = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    # Both come from columns of the user row (no query): the settings form prefills `bio`, and
    # `public_score` is what the credibility panel on that page shows (null until the sample is big
    # enough, §4a).
    public_score = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "display_name",
            "bio",
            "email",
            "is_email_verified",
            "role",
            "has_usable_password",
            "google_connected",
            "avatar_url",
            "avatar_uploads_blocked",
            "public_score",
        ]
        read_only_fields = fields

    def get_has_usable_password(self, user):
        return user.has_usable_password()

    def get_google_connected(self, user):
        return SocialAccount.objects.filter(user=user, provider="google").exists()

    def get_avatar_url(self, user):
        return avatar_url(user, 256)

    def get_public_score(self, user):
        return public_score(user.reputation_score, user.reputation_sample)

    def to_representation(self, user):
        data = super().to_representation(user)
        if user.is_staff:
            # The backend host serves the admin, so the path never appears in the frontend build.
            data["admin_url"] = self.context["request"].build_absolute_uri(
                "/" + settings.ADMIN_URL_PATH
            )
        return data


# ---------- Settings (Part 14) ----------

MAX_DISPLAY_NAME = 50
MAX_BIO = 280
# A username that long is refused before it is normalised (as the availability check does).
MAX_USERNAME_INPUT = 64
# Format characters that reorder or hide text (bidi embeddings, overrides and isolates).
_BIDI_CONTROLS = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")


def _has_forbidden_character(value, *, allow_newline):
    for char in value:
        if char == "\n" and allow_newline:
            continue
        # Cc: controls (tab and newline too), Cs: lone surrogates, Zl/Zp: line and paragraph
        # separators.
        if unicodedata.category(char) in ("Cc", "Cs", "Zl", "Zp") or char in _BIDI_CONTROLS:
            return True
    return False


class ProfileUpdateSerializer(serializers.Serializer):
    """`PATCH /api/v1/me/`: any of `display_name`, `username` and `bio`. Every other key is
    ignored (DRF drops unknown ones), so `email`, `role` and the like can't be changed here.

    Plain text only: display names and bios are shown as text everywhere. Lengths count code
    points, after trimming (and, for the bio, after `\r\n` became `\n`).
    """

    display_name = serializers.CharField(allow_blank=True, required=False, max_length=200)
    username = serializers.CharField(required=False, max_length=MAX_USERNAME_INPUT)
    # Not trimmed here: the newlines are normalised first, then it is trimmed.
    bio = serializers.CharField(
        allow_blank=True, required=False, trim_whitespace=False, max_length=2000
    )

    def validate_display_name(self, value):
        if _has_forbidden_character(value, allow_newline=False):
            raise serializers.ValidationError("Display names are one line of plain text.")
        if len(value) > MAX_DISPLAY_NAME:
            raise serializers.ValidationError(
                f"Display names are at most {MAX_DISPLAY_NAME} characters."
            )
        return value

    def validate_username(self, value):
        username = normalize_username(value)
        try:
            validate_username(username)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from None
        return username

    def validate_bio(self, value):
        value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if _has_forbidden_character(value, allow_newline=True):
            raise serializers.ValidationError("Bios are plain text.")
        if len(value) > MAX_BIO:
            raise serializers.ValidationError(f"Bios are at most {MAX_BIO} characters.")
        return value


class PasswordChangeSerializer(serializers.Serializer):
    """`POST /api/v1/me/password/`. Passwords are never trimmed. The cap only keeps a huge body
    from reaching the hasher; the strength rules are Django's validators."""

    current_password = serializers.CharField(trim_whitespace=False, max_length=1024)
    new_password = serializers.CharField(trim_whitespace=False, max_length=1024)

    def validate_new_password(self, value):
        try:
            validate_password(value, self.context["user"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from None
        return value
