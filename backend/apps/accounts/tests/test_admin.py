import pytest
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django.contrib import admin
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def group_names(user):
    return set(user.groups.values_list("name", flat=True))


def test_createsuperuser_account_can_log_into_the_admin(client, monkeypatch):
    password = "S3cure-pass-phrase!"
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", password)
    call_command(
        "createsuperuser", interactive=False, email="Root@Example.com", username="root_user"
    )

    superuser = User.objects.get(username="root_user")
    assert superuser.email == "root@example.com"
    assert superuser.role == Role.USER
    assert superuser.is_superuser and superuser.is_staff

    # The admin logs in by email, whatever the case.
    assert client.login(username="ROOT@example.com", password=password)
    assert client.get(reverse("admin:index")).status_code == 200


def _change_form_data(user, **overrides):
    data = {
        "email": user.email,
        "username": user.username,
        "display_name": "",
        "bio": "",
        "role": user.role,
        "is_active": "on",
    }
    return {**data, **overrides}


def test_changing_the_role_in_the_admin_keeps_groups_and_is_staff_in_sync(client):
    client.force_login(UserFactory(is_superuser=True))
    target = UserFactory()
    url = reverse("admin:accounts_user_change", args=[target.pk])

    response = client.post(url, _change_form_data(target, role=Role.SENIOR_MODERATOR))
    assert response.status_code == 302  # a 200 would mean the form had errors
    target.refresh_from_db()
    assert target.role == Role.SENIOR_MODERATOR and target.is_staff is True
    assert group_names(target) == {"Moderators", "Senior moderators"}

    response = client.post(url, _change_form_data(target, role=Role.USER))
    assert response.status_code == 302
    target.refresh_from_db()
    assert target.is_staff is False
    assert group_names(target) == set()


def test_admin_form_cannot_override_derived_access_fields(client):
    client.force_login(UserFactory(is_superuser=True))
    target = UserFactory()
    other_group, _ = Group.objects.get_or_create(name="Moderators")
    url = reverse("admin:accounts_user_change", args=[target.pk])

    # A crafted POST that tries to grant staff access and a group without changing the role.
    response = client.post(url, _change_form_data(target, is_staff="on", groups=[other_group.pk]))
    assert response.status_code == 302
    target.refresh_from_db()
    assert target.is_staff is False
    assert group_names(target) == set()


def test_only_the_social_account_is_in_the_admin():
    # The Google app lives in settings (a database row would make two apps match: a 500) and
    # tokens are never stored. SocialAccount shows who linked Google.
    assert admin.site.is_registered(SocialAccount)
    assert not admin.site.is_registered(SocialApp)
    assert not admin.site.is_registered(SocialToken)
