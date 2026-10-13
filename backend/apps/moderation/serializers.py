from rest_framework import serializers

from apps.moderation.models import MAX_APPEAL_REASON_LENGTH


class AppealCreateSerializer(serializers.Serializer):
    """`POST /api/v1/posts/{id}/appeal/`. Undeclared fields (`status`, `author`, …) are ignored."""

    # Trimmed by DRF; counted in code points like the posts; `null` is read as "nothing typed".
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=MAX_APPEAL_REASON_LENGTH,
        error_messages={"max_length": f"Keep it to {MAX_APPEAL_REASON_LENGTH} characters."},
    )

    def validate(self, attrs):
        attrs["reason"] = attrs.get("reason") or ""
        return attrs
