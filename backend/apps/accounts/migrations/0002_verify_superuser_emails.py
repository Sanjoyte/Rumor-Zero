"""Superusers count as verified (user decision 2026-10-01; ARCHITECTURE §2).

`createsuperuser` now does this itself. This backfills superusers created before Part 1: it sets
`is_email_verified` and gives each a verified allauth EmailAddress for its email (primary when it
has none). The reverse does nothing.
"""

from django.db import migrations


def verify_superuser_emails(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")
    for user in User.objects.filter(is_superuser=True):
        User.objects.filter(pk=user.pk).update(is_email_verified=True)
        address = EmailAddress.objects.filter(user=user, email=user.email).first()
        if address is None:
            has_primary = EmailAddress.objects.filter(user=user, primary=True).exists()
            EmailAddress.objects.create(
                user=user, email=user.email, verified=True, primary=not has_primary
            )
        elif not address.verified:
            EmailAddress.objects.filter(pk=address.pk).update(verified=True)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("account", "0009_emailaddress_unique_primary_email"),
    ]

    operations = [
        migrations.RunPython(verify_superuser_emails, migrations.RunPython.noop),
    ]
