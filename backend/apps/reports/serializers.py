from rest_framework import serializers

from apps.reports.models import MAX_DETAILS_LENGTH, ReportReason

CHOOSE_A_REASON = "Choose a reason."


class ReportCreateSerializer(serializers.Serializer):
    """`POST /api/v1/posts/{id}/report/`. Undeclared fields (`status`, `reporter`,
    `counts_toward_threshold`, …) are ignored."""

    reason = serializers.ChoiceField(
        choices=ReportReason.choices,
        error_messages={
            "required": CHOOSE_A_REASON,
            "invalid_choice": CHOOSE_A_REASON,
            "null": CHOOSE_A_REASON,
        },
    )
    # Trimmed by DRF; counted in code points like the posts; `null` is read as "nothing typed".
    details = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=MAX_DETAILS_LENGTH,
        error_messages={"max_length": f"Keep it to {MAX_DETAILS_LENGTH} characters."},
    )

    def validate(self, attrs):
        details = attrs.get("details") or ""
        if attrs["reason"] == ReportReason.OTHER and not details:
            raise serializers.ValidationError({"details": ["Tell us what's wrong."]})
        attrs["details"] = details
        return attrs
