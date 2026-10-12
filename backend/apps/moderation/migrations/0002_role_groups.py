"""Create the two moderator groups and give them their permissions (Part 10).

The lists below are a **frozen copy** of `apps/moderation/roles.py` as it was in Part 10. Do not
import them from there: a later part that adds a permission would then change what this migration
grants on a fresh database, naming models that don't exist yet at this point in history. A later
part adds its own migration with its own lists, and `test_roles.py` fails until it does.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

MODERATORS_GROUP = "Moderators"
SENIORS_GROUP = "Senior moderators"

MODERATOR_PERMISSIONS = (
    "posts.view_post",
    "posts.change_post",
    "reports.view_report",
    "social.view_comment",
    "social.change_comment",
    "accounts.view_user",
    "core.view_platformsettings",
)
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


def grant(apps, schema_editor):
    create_the_permission_rows(apps)
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for group_name, names in (
        (MODERATORS_GROUP, MODERATOR_PERMISSIONS),
        (SENIORS_GROUP, SENIOR_PERMISSIONS),
    ):
        group, _ = Group.objects.get_or_create(name=group_name)
        rows = []
        for name in names:
            app_label, codename = name.split(".")
            rows.append(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )
        group.permissions.set(rows)


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for group in Group.objects.filter(name__in=(MODERATORS_GROUP, SENIORS_GROUP)):
        group.permissions.clear()


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
        ("moderation", "0001_initial"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
