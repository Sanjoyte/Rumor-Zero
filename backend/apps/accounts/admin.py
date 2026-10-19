from allauth.socialaccount.models import SocialApp, SocialToken
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.contrib.admin.utils import NestedObjects
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.core.exceptions import PermissionDenied
from django.db import router
from django.utils.html import format_html
from django.utils.text import capfirst, get_text_list

from apps.accounts import services
from apps.accounts.models import Role, User
from apps.core.admin_mixins import HistoryNeedsLog
from apps.reputation.admin import events_url
from apps.reputation.scoring import public_score

# allauth registers all three social models. The Google app lives in settings (a database row would
# make two apps match: a 500), and tokens are never stored. SocialAccount stays: it shows who linked
# Google.
admin.site.unregister(SocialApp)
admin.site.unregister(SocialToken)


class UserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "username")


class UserChangeForm(BaseUserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


# What a senior moderator may edit on someone else's account (user decision 2026-10-11). Email,
# password, profile and `is_superuser` stay superuser-only.
SENIOR_EDITABLE = ("role", "is_active")


def yes_no(value):
    return "yes" if value else "no"


@admin.register(User)
class UserAdmin(HistoryNeedsLog, BaseUserAdmin):
    """Accounts in Django Admin. A **superuser** has the whole form. A **senior moderator** sees
    the page read-only except `role` and `is_active` (suspension), never sees the password hash, and
    can't edit, suspend or delete a superuser or themselves; they also get "Mark email verified"
    and a one-at-a-time delete. A moderator may only look (ARCHITECTURE §8)."""

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
    actions = ["verify_email"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("username", "display_name", "bio")}),
        ("Access", {"fields": ("role", "is_active", "is_superuser", "is_staff", "groups")}),
        (
            "Account state",
            {
                "fields": (
                    "is_email_verified",
                    "credibility",
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
    # logged actions in Parts 11C and 14B ("Mark email verified" is below; Part 2 added none, since
    # allauth's email_confirmed signal sets is_email_verified).
    readonly_fields = (
        "is_staff",
        "groups",
        "is_email_verified",
        "credibility",
        "avatar_version",
        "avatar_uploads_blocked",
        "emergency_blocked_until",
        "last_login",
        "created_at",
    )

    # --- the credibility score (Part 11B): read-only, written only by the reputation service ---

    @admin.display(description="Credibility")
    def credibility(self, user):
        """The score with its counted events ("72 · 23 counted events"), or "New (2 counted
        events, score 55)" while the public sees no score, and a link to the account's rows."""
        sample = user.reputation_sample
        events = f"{sample} counted event{'' if sample == 1 else 's'}"
        if public_score(user.reputation_score, sample) is None:
            text = f"New ({events}, score {user.reputation_score})"
        else:
            text = f"{user.reputation_score} · {events}"
        return format_html('{} · <a href="{}">View events</a>', text, events_url(user))

    # --- what each kind of staff member sees ---

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is None or request.user.is_superuser:
            return fieldsets
        # The read-only `password` field would print the hash (`ReadOnlyPasswordHashField`).
        return [
            (name, {**options, "fields": tuple(f for f in options["fields"] if f != "password")})
            for name, options in fieldsets
        ]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if request.user.is_superuser:
            return fields
        every = (
            "email",
            "username",
            "display_name",
            "bio",
            "is_superuser",
            *self.readonly_fields,
        )
        return tuple(f for f in every if f not in SENIOR_EDITABLE)

    def _may_touch(self, request, obj):
        """A non-superuser can't edit, suspend or delete a superuser, or themselves."""
        return (
            request.user.is_superuser
            or obj is None
            or not (obj.is_superuser or obj.pk == request.user.pk)
        )

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and self._may_touch(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and self._may_touch(request, obj)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            # The bulk delete checks no object, so it could remove a superuser; a senior deletes
            # one account at a time, from its page.
            actions.pop("delete_selected", None)
        return actions

    def user_change_password(self, request, id, form_url=""):
        # Django only asks for change permission on the account, which a senior has.
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().user_change_password(request, id, form_url)

    # --- deleting an account ---

    def get_deleted_objects(self, objs, request):
        """What the delete page shows and allows (user decision 2026-10-11).

        Django's version lists every cascaded row by `str()` (a bookmark prints "x bookmarked y",
        and bookmarks are private; a comment prints its text) and refuses when the person lacks
        permission on a cascaded model (a user with posts could never be deleted, since posts are
        read-only). This one shows a **summary** (a count per kind) and asks for no permission on
        the cascaded models; the account's own delete permission is the gate. It **protects** an
        account that wrote admin log entries: `LogEntry.user` cascades, and deleting a former
        senior would erase their record of role, suspension and settings changes. Suspend it.
        """
        using = router.db_for_write(self.model)
        collector = NestedObjects(using=using, origin=objs)
        collector.collect(list(objs))
        model_count = {
            model._meta.verbose_name_plural: len(rows)
            for model, rows in collector.model_objs.items()
        }
        deleted = [f"{capfirst(name)}: {count}" for name, count in sorted(model_count.items())]
        protected = []
        wrote = LogEntry.objects.filter(user__in=list(objs)).values_list(
            "user__username", flat=True
        )
        for username in sorted(set(wrote)):
            protected.append(
                f"{username} wrote admin log entries, which would be deleted with the account. "
                "Suspend the account instead (clear Active)."
            )
        return deleted, model_count, set(), protected

    # --- the change message: values, not just field names ---

    def construct_change_message(self, request, form, formsets, add=False):
        instance = getattr(form, "instance", None)
        changed = getattr(form, "changed_data", [])
        if add or instance is None or not ({"role", "is_active"} & set(changed)):
            return super().construct_change_message(request, form, formsets, add)
        parts = []
        if "role" in changed:
            parts.append(
                f"Role: {Role(form.initial['role']).label.lower()} → "
                f"{Role(form.cleaned_data['role']).label.lower()}"
            )
        if "is_active" in changed:
            parts.append(
                f"Active: {yes_no(form.initial['is_active'])} → "
                f"{yes_no(form.cleaned_data['is_active'])}"
            )
        message = ". ".join(parts) + "."
        others = [name for name in changed if name not in SENIOR_EDITABLE]
        if others:
            labels = [str(form.fields[name].label or name).lower() for name in others]
            message += f" Also changed: {get_text_list(labels, 'and')}."
        return message

    # --- Mark email verified ---

    @admin.action(description="Mark email verified", permissions=["change"])
    def verify_email(self, request, queryset):
        done = skipped = 0
        for account in queryset:
            if not self.has_change_permission(request, account):
                skipped += 1
                continue
            if services.verify_email_by_staff(account):
                self.log_change(request, account, "Marked email verified")
                done += 1
            else:
                skipped += 1
        if done:
            self.message_user(
                request,
                f"Marked the email verified on {done} account{'' if done == 1 else 's'}.",
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped}: already verified, or an account you can't change "
                "(a superuser or yourself).",
                messages.WARNING,
            )
