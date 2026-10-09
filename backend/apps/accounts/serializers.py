from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from rest_framework import serializers

from apps.accounts.models import User


def avatar_url(user, size=96):
    """`/api/v1/avatars/{user_id}/{avatar_version}-{size}.webp`, or None for initials (§9)."""
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

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "display_name",
            "email",
            "is_email_verified",
            "role",
            "has_usable_password",
            "google_connected",
            "avatar_url",
        ]
        read_only_fields = fields

    def get_has_usable_password(self, user):
        return user.has_usable_password()

    def get_google_connected(self, user):
        return SocialAccount.objects.filter(user=user, provider="google").exists()

    def get_avatar_url(self, user):
        return avatar_url(user)

    def to_representation(self, user):
        data = super().to_representation(user)
        if user.is_staff:
            # The backend host serves the admin, so the path never appears in the frontend build.
            data["admin_url"] = self.context["request"].build_absolute_uri(
                "/" + settings.ADMIN_URL_PATH
            )
        return data
