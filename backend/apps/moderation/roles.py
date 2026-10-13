"""What the two moderator groups may do in Django Admin (ARCHITECTURE §8; guide §8).

`User.role` is the source of truth: `User.save` puts a person into the cumulative groups
"Moderators" (moderators and seniors) and "Senior moderators" (seniors only). This module says which
model permissions each group holds. A senior moderator is in both groups, so the senior list only
holds the **extras**.

`sync_role_groups()` applies the lists to the live registry (the tests' `role_groups` fixture and
`manage.py` shells use it). The database itself is filled by migrations `0002_role_groups` and
`0004_appeal_permission`, which carry their own frozen copies of these lists: a migration must not
import a list that later parts edit (a fresh `migrate` would then grant permissions on models that
don't exist yet). A part that
changes a list here adds a new migration with the new frozen lists; `test_roles.py` fails until it
does.
"""

from django.contrib.auth.models import Group, Permission

from apps.accounts.models import MODERATORS_GROUP, SENIORS_GROUP

# "app_label.codename". Moderators: read the queue and act on posts through the services (the
# actions are gated on `posts.change_post`; the page itself stays read-only), hide comments, see
# who people are and what the settings are, and read the appeals (Part 11).
MODERATOR_PERMISSIONS = (
    "posts.view_post",
    "posts.change_post",
    "reports.view_report",
    "social.view_comment",
    "social.change_comment",
    "accounts.view_user",
    "core.view_platformsettings",
    "moderation.view_appeal",
)

# Seniors, on top of the above: change roles and suspend (accounts), delete accounts, edit the
# platform settings, and read the full moderation log and Django's admin log.
SENIOR_PERMISSIONS = (
    "accounts.change_user",
    "accounts.delete_user",
    "core.change_platformsettings",
    "moderation.view_moderationaction",
    "admin.view_logentry",
)

GROUP_PERMISSIONS = {
    MODERATORS_GROUP: MODERATOR_PERMISSIONS,
    SENIORS_GROUP: SENIOR_PERMISSIONS,
}


def permissions_for(names):
    """The `Permission` rows for "app_label.codename" `names`. A missing row raises: it means the
    list names a model that doesn't exist (or whose permissions weren't created yet)."""
    rows = []
    for name in names:
        app_label, codename = name.split(".")
        rows.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return rows


def sync_role_groups():
    """Create both groups if needed and make their permissions exactly `GROUP_PERMISSIONS`."""
    for group_name, names in GROUP_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        group.permissions.set(permissions_for(names))
