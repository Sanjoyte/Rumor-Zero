from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm

from apps.accounts.models import User


class UserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "username")


class UserChangeForm(BaseUserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    ordering = ("-created_at",)
    list_display = (
        "username",
        "email",
        "role",
        "is_staff",
        "is_superuser",
        "is_email_verified",
        "is_active",
        "created_at",
    )
    list_filter = ("role", "is_staff", "is_superuser", "is_email_verified", "is_active")
    search_fields = ("username", "email")
    filter_horizontal = ()

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("username", "display_name", "bio")}),
        ("Access", {"fields": ("role", "is_active", "is_superuser", "is_staff", "groups")}),
        (
            "Account state",
            {
                "fields": (
                    "is_email_verified",
                    "reputation_score",
                    "reputation_sample",
                    "avatar_version",
                    "avatar_uploads_blocked",
                    "emergency_blocked_until",
                    "last_login",
                    "created_at",
                )
            },
        ),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "username", "password1", "password2")}),
    )
    # is_staff and groups are derived from role/is_superuser on save. If the form edited them,
    # the admin's save_related would overwrite that sync. The remaining state fields get their own
    # logged actions in Parts 2, 10, 11C and 14B.
    readonly_fields = (
        "is_staff",
        "groups",
        "is_email_verified",
        "reputation_score",
        "reputation_sample",
        "avatar_version",
        "avatar_uploads_blocked",
        "emergency_blocked_until",
        "last_login",
        "created_at",
    )
