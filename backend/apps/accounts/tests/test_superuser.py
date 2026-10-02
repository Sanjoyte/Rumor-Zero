"""Superusers count as verified (user decision 2026-10-01)."""

import importlib

import pytest
from allauth.account.models import EmailAddress
from django.apps import apps
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.conftest import login
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

backfill = importlib.import_module("apps.accounts.migrations.0002_verify_superuser_emails")
PASSWORD = "S3cure-pass-phrase!"


def test_createsuperuser_is_verified_with_a_primary_email_address(monkeypatch, client):
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", PASSWORD)
    call_command("createsuperuser", interactive=False, email="Root@Example.com", username="rooty")

    user = User.objects.get(username="rooty")
    assert user.is_email_verified is True
    address = EmailAddress.objects.get(user=user)
    assert (address.email, address.verified, address.primary) == ("root@example.com", True, True)

    # Django Admin still logs in by email, through allauth's backend alone.
    assert client.login(username="ROOT@example.com", password=PASSWORD)
    assert client.get(reverse("admin:index")).status_code == 200


def test_a_superuser_can_also_log_in_through_the_api(site_client):
    User.objects.create_superuser("boss@example.test", "boss_user", PASSWORD)
    assert login(site_client, "boss@example.test", PASSWORD).status_code == 200


def test_the_backfill_verifies_existing_superusers():
    # Made the Part 0A way: no EmailAddress, not verified.
    old = UserFactory(is_superuser=True)
    with_address = UserFactory(is_superuser=True)
    EmailAddress.objects.create(user=with_address, email=with_address.email, primary=True)
    ordinary = UserFactory()

    backfill.verify_superuser_emails(apps, None)
    backfill.verify_superuser_emails(apps, None)  # running it twice changes nothing more

    for user in (old, with_address):
        user.refresh_from_db()
        assert user.is_email_verified is True
        address = EmailAddress.objects.get(user=user)
        assert (address.verified, address.primary) == (True, True)
    ordinary.refresh_from_db()
    assert ordinary.is_email_verified is False
    assert not EmailAddress.objects.filter(user=ordinary).exists()


def test_the_backfill_keeps_another_primary_address():
    user = UserFactory(is_superuser=True)
    EmailAddress.objects.create(user=user, email="other@example.test", primary=True)
    backfill.verify_superuser_emails(apps, None)
    address = EmailAddress.objects.get(user=user, email=user.email)
    assert (address.verified, address.primary) == (True, False)
