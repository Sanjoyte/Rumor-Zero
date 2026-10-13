"""Let moderators see appeals in Django Admin (Part 11): `moderation.view_appeal`.

Like `0002_role_groups`, the lists below are a **frozen copy** of `apps/moderation/roles.py` (as of
Part 11) and are never imported from there. Going back sets the groups to `0002`'s lists, not to
nothing: `0002`'s own reverse clears both groups, which would leave moderators with no permission
after `migrate moderation 0003`.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

MODERATORS_GROUP = "Moderators"
SENIORS_GROUP = "Senior moderators"

# What 0002 granted (restored when this migration is reversed).
PREVIOUS_MODERATOR_PERMISSIONS = (
    "posts.view_post",
    "posts.change_post",
    "reports.view_report",
    "social.view_comment",
    "social.change_comment",
    "accounts.view_user",
    "core.view_platformsettings",
)
MODERATOR_PERMISSIONS = (*PREVIOUS_MODERATOR_PERMISSIONS, "moderation.view_appeal")
SENIOR_PERMISSIONS = (
    "accounts.change_user",
    "accounts.delete_user",
    "core.change_platformsettings",
    "moderation.view_moderationaction",
    "admin.view_logentry",
)
APP_LABELS = ("admin", "accounts", "core", "posts", "reports", "social", "moderation")


def create_the_permission_rows(apps):
    """On a fresh database `post_migrate` (which normally creates them) hasn't run yet."""
    for label in APP_LABELS:
        app_config = apps.get_app_config(label)
        # `create_permissions` returns at once for an app with no `models_module`.
        previous = getattr(app_config, "models_module", None)
        app_config.models_module = True
        try:
            create_permissions(app_config, verbosity=0, interactive=False, apps=apps)
        finally:
            app_config.models_module = previous


def set_groups(apps, moderators, seniors):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for group_name, names in ((MODERATORS_GROUP, moderators), (SENIORS_GROUP, seniors)):
        group, _ = Group.objects.get_or_create(name=group_name)
        rows = []
        for name in names:
            app_label, codename = name.split(".")
            rows.append(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )
        group.permissions.set(rows)


def grant(apps, schema_editor):
    create_the_permission_rows(apps)
    set_groups(apps, MODERATOR_PERMISSIONS, SENIOR_PERMISSIONS)


def revoke(apps, schema_editor):
    set_groups(apps, PREVIOUS_MODERATOR_PERMISSIONS, SENIOR_PERMISSIONS)


class Migration(migrations.Migration):
    dependencies = [
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("accounts", "0002_verify_superuser_emails"),
        ("core", "0002_seed_platform_settings"),
        ("posts", "0002_review_started_at"),
        ("reports", "0001_initial"),
        ("social", "0003_repost_bookmark"),
        ("moderation", "0003_appeal"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
