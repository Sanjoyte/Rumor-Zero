from django.conf import settings
from django.db import migrations


def seed_platform_settings(apps, schema_editor):
    PlatformSettings = apps.get_model("core", "PlatformSettings")
    # Only fields that exist at this point in history, so a field added by a later migration
    # can't break a fresh `migrate`.
    field_names = {field.name for field in PlatformSettings._meta.get_fields()}
    defaults = {
        name: value
        for name, value in settings.PLATFORM_SETTINGS_SEED.items()
        if name in field_names
    }
    PlatformSettings.objects.using(schema_editor.connection.alias).get_or_create(
        pk=1, defaults=defaults
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_platform_settings, migrations.RunPython.noop),
    ]
