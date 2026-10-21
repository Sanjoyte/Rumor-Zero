import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from allauth.socialaccount.models import SocialApp, SocialToken
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.models import LogEntry
from django.contrib.admin.utils import NestedObjects
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.core.exceptions import PermissionDenied
from django.db import router
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.text import Truncator, capfirst, get_text_list

from apps.accounts import deletion, services
from apps.accounts.models import Avatar, Role, User
from apps.accounts.serializers import avatar_url
from apps.core.admin_mixins import HistoryNeedsLog
from apps.core.services import get_platform_settings
from apps.moderation import rules as moderation_rules
from apps.moderation import services as moderation_services
from apps.moderation.forms import ConfirmActionForm
from apps.moderation.models import ActionKind, ModerationAction
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


# ---------- Actions on an account: its emergency posting (Part 11C) and its photo (14B) ----------

BLOCK_PERMISSION = "moderation.block_emergency_posting"
PHOTO_PERMISSION = "moderation.moderate_profile_photos"
ACCOUNT_BATCH_CAP = 100  # accounts per action, as for posts
BLOCK_KINDS = (ActionKind.EMERGENCY_BLOCKED, ActionKind.EMERGENCY_UNBLOCKED)
PHOTO_KINDS = (
    ActionKind.AVATAR_REMOVED,
    ActionKind.AVATAR_BLOCKED,
    ActionKind.AVATAR_UNBLOCKED,
)
Act = moderation_rules.AccountAct


def when(moment):
    """A block's end for the confirmation page, or "—"."""
    return f"{moment:%Y-%m-%d %H:%M} UTC" if moment is not None else "—"


def plural(n, word="account"):
    return f"{n} {word}{'' if n == 1 else 's'}"


def photo_text(*, has_photo, blocked):
    photo = "Has a photo" if has_photo else "No photo"
    return f"{photo}, uploads {'blocked' if blocked else 'allowed'}"


def photo_now(account):
    return photo_text(
        has_photo=bool(account.avatar_version), blocked=account.avatar_uploads_blocked
    )


@dataclass(frozen=True)
class AccountActionSpec:
    """What the shared confirmation page needs to know about one action on accounts."""

    act: Act
    label: str
    service: Callable
    done_text: Callable[[int], str]
    permission: str
    now_heading: str
    after_heading: str
    # The sentence above the table (`days` is the emergency block length; 0 for the photo acts).
    explain: Callable[[int], str]
    current: Callable[[User], str]
    after: Callable[[User, datetime, int], str]


def _block_end(account, now, days):
    # The latest end of the blocks that stand: a longer block already there stays.
    end = now + timedelta(days=days)
    current = account.emergency_blocked_until
    return when(max(end, current) if current else end)


ACCOUNT_ACTIONS = {
    "block_emergency": AccountActionSpec(
        act=Act.BLOCK_EMERGENCY,
        label="Block emergency posting",
        service=moderation_services.block_emergency_posting,
        done_text=lambda n: f"Blocked emergency posting on {plural(n)}.",
        permission=BLOCK_PERMISSION,
        now_heading="Blocked until now",
        after_heading="Blocked until after this",
        explain=lambda days: (
            f"A block lasts {plural(days, 'day')}, as long as the block after a FALSE emergency, "
            "and is logged with your notes."
        ),
        current=lambda account: when(account.emergency_blocked_until),
        after=_block_end,
    ),
    "unblock_emergency": AccountActionSpec(
        act=Act.UNBLOCK_EMERGENCY,
        label="Unblock emergency posting",
        service=moderation_services.unblock_emergency_posting,
        done_text=lambda n: f"Unblocked emergency posting on {plural(n)}.",
        permission=BLOCK_PERMISSION,
        now_heading="Blocked until now",
        after_heading="Blocked until after this",
        explain=lambda days: (
            "Unblocking lifts every block on the account early, the automatic ones too, and is "
            "logged with your notes."
        ),
        current=lambda account: when(account.emergency_blocked_until),
        after=lambda account, now, days: "— (every block lifted)",
    ),
    "remove_photo": AccountActionSpec(
        act=Act.REMOVE_PHOTO,
        label="Remove photo",
        service=moderation_services.remove_photo,
        done_text=lambda n: f"Removed the photo of {plural(n)}.",
        permission=PHOTO_PERMISSION,
        now_heading="Photo now",
        after_heading="Photo after this",
        explain=lambda days: (
            "The account shows its initials everywhere at once. It can upload another photo "
            "unless uploads are blocked too. Logged with your notes."
        ),
        current=photo_now,
        after=lambda a, now, days: photo_text(has_photo=False, blocked=a.avatar_uploads_blocked),
    ),
    "block_photo_uploads": AccountActionSpec(
        act=Act.BLOCK_PHOTO_UPLOADS,
        label="Block photo uploads",
        service=moderation_services.block_photo_uploads,
        done_text=lambda n: f"Blocked photo uploads on {plural(n)}.",
        permission=PHOTO_PERMISSION,
        now_heading="Photo now",
        after_heading="Photo after this",
        explain=lambda days: (
            "This also removes the account's current photo (logged as two entries). Uploads fail "
            "with 403 until you allow them again."
        ),
        current=photo_now,
        after=lambda a, now, days: photo_text(has_photo=False, blocked=True),
    ),
    "allow_photo_uploads": AccountActionSpec(
        act=Act.ALLOW_PHOTO_UPLOADS,
        label="Allow photo uploads",
        service=moderation_services.allow_photo_uploads,
        done_text=lambda n: f"Allowed photo uploads on {plural(n)}.",
        permission=PHOTO_PERMISSION,
        now_heading="Photo now",
        after_heading="Photo after this",
        explain=lambda days: (
            "The account can upload a photo again. A photo that was removed stays removed. "
            "Logged with your notes."
        ),
        current=photo_now,
        after=lambda a, now, days: photo_text(has_photo=bool(a.avatar_version), blocked=False),
    ),
}


class AccountActionsMixin:
    """The confirmation page and the apply step of the actions on accounts, shared by `UserAdmin`
    and `AvatarAdmin` (an avatar's primary key *is* its account's id, so both post account ids).

    First POST: show which accounts change (their state now and after) and which are skipped, with
    the internal notes. The confirmation POST (`apply`): do it, account by account, through the
    service. As on `PostAdmin`, the apply step acts on exactly the accounts shown (at most 100)
    and never trusts `select_across`.
    """

    def accounts_of(self, queryset):
        """The accounts behind this admin's rows (an avatar's own account)."""
        return queryset

    def has_moderate_photos_permission(self, request):
        """Moderators and up (user decision 2026-10-21): `moderation.moderate_profile_photos`."""
        return request.user.has_perm(PHOTO_PERMISSION)

    def response_action(self, request, queryset):
        """Django filters by the posted ids itself, and an id that isn't a UUID would raise
        `ValidationError` (a 500), as on `PostAdmin`. Drop such ids first."""
        posted = request.POST.copy()
        valid = []
        for value in posted.getlist(ACTION_CHECKBOX_NAME):
            try:
                valid.append(str(uuid.UUID(value)))
            except ValueError:
                continue
        posted.setlist(ACTION_CHECKBOX_NAME, valid)
        request.POST = posted
        return super().response_action(request, queryset)

    @admin.action(description="Remove photo", permissions=["moderate_photos"])
    def remove_photo(self, request, queryset):
        return self._account_action(request, queryset, "remove_photo")

    @admin.action(description="Block photo uploads", permissions=["moderate_photos"])
    def block_photo_uploads(self, request, queryset):
        return self._account_action(request, queryset, "block_photo_uploads")

    @admin.action(description="Allow photo uploads", permissions=["moderate_photos"])
    def allow_photo_uploads(self, request, queryset):
        return self._account_action(request, queryset, "allow_photo_uploads")

    def _account_action(self, request, queryset, name):
        spec = ACCOUNT_ACTIONS[name]
        applying = "apply" in request.POST
        if applying:
            ids = request.POST.getlist(ACTION_CHECKBOX_NAME)
            queryset = self.get_queryset(request).filter(pk__in=ids)
        accounts = list(self.accounts_of(queryset).order_by("pk")[: ACCOUNT_BATCH_CAP + 1])
        if len(accounts) > ACCOUNT_BATCH_CAP:
            self.message_user(
                request,
                f"Select at most {ACCOUNT_BATCH_CAP} accounts at a time.",
                messages.ERROR,
            )
            return None
        if not accounts:
            self.message_user(request, "No accounts to act on.", messages.WARNING)
            return None
        form = ConfirmActionForm(request.POST if applying else None, act=spec.act)
        if applying and form.is_valid():
            return self._apply_account_action(
                request, accounts, spec, form.cleaned_data["notes"].strip()
            )

        now = timezone.now()
        days = (
            get_platform_settings().emergency_false_cooldown_days
            if spec.act in moderation_rules.EMERGENCY_ACTS
            else 0
        )
        changing, skipped = [], []
        for account in accounts:
            row = {
                "account": account,
                "username": account.username,
                "current": spec.current(account),
            }
            refusal = moderation_rules.account_refusal(
                spec.act, account, request.user, block_days=days, now=now
            )
            if refusal is not None:
                skipped.append({"row": row, "why": refusal.text})
                continue
            row["after"] = spec.after(account, now, days)
            changing.append(row)
        context = {
            **self.admin_site.each_context(request),
            "title": f"{spec.label}: are you sure?",
            "opts": self.opts,
            "action": name,
            "label": spec.label,
            "explanation": spec.explain(days),
            "now_heading": spec.now_heading,
            "after_heading": spec.after_heading,
            "changelist_url": reverse(
                f"admin:{self.opts.app_label}_{self.opts.model_name}_changelist"
            ),
            "form": form,
            "changing": changing,
            "skipped": skipped,
            "selected": [str(account.pk) for account in accounts],
            "form_action": request.get_full_path(),
            "cancel_url": request.get_full_path(),
        }
        return TemplateResponse(request, "moderation/admin/confirm_account_action.html", context)

    def _apply_account_action(self, request, accounts, spec, notes):
        done = 0
        skipped = Counter()
        for account in accounts:
            try:
                spec.service(account.pk, moderator=request.user, notes=notes)
                done += 1
            except moderation_services.ActionRefused as refused:
                skipped[refused.refusal.text] += 1
        if done:
            self.message_user(request, spec.done_text(done), messages.SUCCESS)
        if skipped:
            detail = ", ".join(f"{count} {why}" for why, count in sorted(skipped.items()))
            self.message_user(
                request, f"Skipped {sum(skipped.values())}: {detail}.", messages.WARNING
            )
        return HttpResponseRedirect(request.get_full_path())


class EmergencyPostingFilter(admin.SimpleListFilter):
    """Accounts whose emergency posting is blocked right now (or not)."""

    title = "emergency posting"
    parameter_name = "emergency_posting"

    def lookups(self, request, model_admin):
        return [("blocked", "Blocked"), ("free", "Not blocked")]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "blocked":
            return queryset.filter(emergency_blocked_until__gt=now)
        if self.value() == "free":
            return queryset.filter(
                Q(emergency_blocked_until__isnull=True) | Q(emergency_blocked_until__lte=now)
            )
        return queryset


class PhotoUploadsFilter(admin.SimpleListFilter):
    """Accounts whose photo uploads are blocked (or allowed): Part 14B."""

    title = "photo uploads"
    parameter_name = "photo_uploads"

    def lookups(self, request, model_admin):
        return [("blocked", "Blocked"), ("allowed", "Allowed")]

    def queryset(self, request, queryset):
        if self.value() == "blocked":
            return queryset.filter(avatar_uploads_blocked=True)
        if self.value() == "allowed":
            return queryset.filter(avatar_uploads_blocked=False)
        return queryset


@admin.register(User)
class UserAdmin(HistoryNeedsLog, AccountActionsMixin, BaseUserAdmin):
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
    list_filter = (
        "role",
        "is_staff",
        "is_superuser",
        "is_email_verified",
        "is_active",
        EmergencyPostingFilter,
        PhotoUploadsFilter,
    )
    search_fields = ("username", "email")
    filter_horizontal = ()
    actions = [
        "verify_email",
        "block_emergency",
        "unblock_emergency",
        "remove_photo",
        "block_photo_uploads",
        "allow_photo_uploads",
    ]

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
                    "photo",
                    "emergency_blocked_until",
                    "emergency_blocks",
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
    # logged actions ("Mark email verified", Part 11C's Block / Unblock emergency posting and Part
    # 14B's photo actions are below; Part 2 added none, since allauth's email_confirmed signal sets
    # is_email_verified).
    readonly_fields = (
        "is_staff",
        "groups",
        "is_email_verified",
        "credibility",
        "photo",
        "emergency_blocked_until",
        "emergency_blocks",
        "last_login",
        "created_at",
    )

    # --- the emergency blocks (Part 11C): read-only, written only by the moderation service ---

    @admin.display(description="Emergency blocks")
    def emergency_blocks(self, user):
        """The account's emergency blocks and unblocks, newest first: the automatic ones (a post's
        FALSE, or its overturn) and a moderator's. A manual row has no post, so no post page shows
        it, and the full log is seniors-only. A read-only list, not an inline: an inline formset
        would make the account form's own POST carry its management form."""
        rows = (
            ModerationAction.objects.filter(subject_user=user, action__in=BLOCK_KINDS)
            .select_related("moderator")
            .order_by("-created_at")[:50]
        )

        def cells(row):
            if row.post_id is not None:
                url = reverse("admin:posts_post_change", args=[row.post_id])
                post = format_html(
                    '<a href="{}">{}</a>', url, Truncator(row.post_snapshot).chars(60)
                )
            else:
                post = "—"
            who = row.moderator.username if row.moderator else "automatic"
            return (
                when(row.created_at),
                row.get_action_display(),
                who,
                post,
                when(row.blocked_until),
                row.notes or "—",
            )

        body = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>",
            (cells(row) for row in rows),
        )
        if not body:
            return "None"
        return format_html(
            "<table><thead><tr><th>Time</th><th>Action</th><th>By</th><th>Post</th>"
            "<th>Until</th><th>Notes</th></tr></thead><tbody>{}</tbody></table>",
            body,
        )

    # --- the profile photo (Part 14B): read-only, written by the avatar and moderation services ---

    @admin.display(description="Photo")
    def photo(self, user):
        """The thumbnail (or "No photo"), whether uploads are blocked, and the account's photo
        actions, newest first. Read-only text built from the user row and the audit rows (the
        image bytes live in another table and are never loaded here); a field and not an inline,
        which would break the account form's POST."""
        thumbnail = (
            format_html(
                '<img src="{}" width="48" height="48" alt="" style="border-radius:50%">',
                avatar_url(user, 96),
            )
            if user.avatar_version
            else "No photo"
        )
        state = "Uploads blocked" if user.avatar_uploads_blocked else "Uploads allowed"
        rows = (
            ModerationAction.objects.filter(subject_user=user, action__in=PHOTO_KINDS)
            .select_related("moderator")
            .order_by("-created_at")[:50]
        )
        history = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>",
            (
                (
                    when(row.created_at),
                    row.get_action_display(),
                    row.moderator.username if row.moderator else "—",
                    row.notes or "—",
                )
                for row in rows
            ),
        )
        table = (
            format_html(
                "<table><thead><tr><th>Time</th><th>Action</th><th>By</th><th>Notes</th></tr>"
                "</thead><tbody>{}</tbody></table>",
                history,
            )
            if history
            else ""
        )
        return format_html(
            "{} · {}{}", thumbnail, state, format_html("<br>{}", table) if table else ""
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
        if obj is None:
            return fieldsets
        hidden = set()
        if not request.user.is_superuser:
            # The read-only `password` field would print the hash (`ReadOnlyPasswordHashField`).
            hidden.add("password")
        if not request.user.has_perm(BLOCK_PERMISSION):
            hidden.add("emergency_blocks")
        if not request.user.has_perm(PHOTO_PERMISSION):
            hidden.add("photo")
        if not hidden:
            return fieldsets
        return [
            (name, {**options, "fields": tuple(f for f in options["fields"] if f not in hidden)})
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

    def delete_model(self, request, obj):
        # The same routine as the owner's `DELETE /me`: it locks the posts before the account and
        # first deletes the notifications the account caused (Part 14). Django's own delete would
        # leave "Someone liked your post" items behind.
        deletion.delete_account(obj)

    def delete_queryset(self, request, queryset):
        for user in list(queryset):
            deletion.delete_account(user)

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

    # --- Block / Unblock emergency posting (Part 11C) ---

    def has_block_emergency_permission(self, request):
        """Moderators and up (user decision 2026-10-19): `moderation.block_emergency_posting`."""
        return request.user.has_perm(BLOCK_PERMISSION)

    @admin.action(description="Block emergency posting", permissions=["block_emergency"])
    def block_emergency(self, request, queryset):
        return self._account_action(request, queryset, "block_emergency")

    @admin.action(description="Unblock emergency posting", permissions=["block_emergency"])
    def unblock_emergency(self, request, queryset):
        return self._account_action(request, queryset, "unblock_emergency")


# ---------- Profile photos (Part 14B) ----------


@admin.register(Avatar)
class AvatarAdmin(HistoryNeedsLog, AccountActionsMixin, admin.ModelAdmin):
    """The accounts that have a profile photo, newest change first. Read-only: a photo is changed
    only by its owner, and taken down by **Remove photo** or **Block photo uploads** (which also
    removes it), both through the moderation service and logged with `subject_user`. The two image
    columns are never loaded here; a thumbnail is the public 96 px URL (this admin is on the same
    host as the API)."""

    list_display = ("thumbnail", "account", "bytes_total", "updated_at")
    list_select_related = ("user",)
    ordering = ("-updated_at",)
    search_fields = ("user__username",)
    actions = ["remove_photo", "block_photo_uploads"]
    fields = ("thumbnail", "account", "version", "bytes_total", "created_at", "updated_at")
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).defer("image_256", "image_96")

    def accounts_of(self, queryset):
        return User.objects.filter(pk__in=queryset.values("pk"))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Photo")
    def thumbnail(self, avatar):
        url = f"/api/v1/avatars/{avatar.user_id}/{avatar.version}-96.webp"
        return format_html(
            '<img src="{}" width="48" height="48" alt="" style="border-radius:50%">', url
        )

    @admin.display(description="Account", ordering="user__username")
    def account(self, avatar):
        url = reverse("admin:accounts_user_change", args=[avatar.user_id])
        return format_html('<a href="{}">{}</a>', url, avatar.user.username)
