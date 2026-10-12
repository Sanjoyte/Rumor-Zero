"""The two groups and their permissions (ARCHITECTURE §8): what the migration grants, what
`roles.py` says, and what a person of each role can therefore do."""

import importlib

import pytest
from django.apps import apps as live_apps
from django.contrib.auth.models import Group, Permission

from apps.accounts.models import MODERATORS_GROUP, SENIORS_GROUP, Role
from apps.accounts.tests.factories import UserFactory
from apps.moderation import roles

pytestmark = pytest.mark.django_db

migration = importlib.import_module("apps.moderation.migrations.0002_role_groups")


def held(group_name):
    return {
        f"{p.content_type.app_label}.{p.codename}"
        for p in Group.objects.get(name=group_name).permissions.select_related("content_type")
    }


def test_the_lists_in_roles_py_equal_the_frozen_lists_of_the_migration():
    """A later part that changes a list adds a migration with the new frozen lists; until it
    does, this fails, so a fresh `migrate` and a live database can't drift apart."""
    assert roles.MODERATOR_PERMISSIONS == migration.MODERATOR_PERMISSIONS
    assert roles.SENIOR_PERMISSIONS == migration.SENIOR_PERMISSIONS
    assert (roles.MODERATORS_GROUP, roles.SENIORS_GROUP) == (
        migration.MODERATORS_GROUP,
        migration.SENIORS_GROUP,
    )


def test_the_migration_gives_both_groups_exactly_the_declared_permissions():
    Group.objects.all().delete()
    migration.grant(live_apps, None)
    assert held(MODERATORS_GROUP) == set(roles.MODERATOR_PERMISSIONS)
    assert held(SENIORS_GROUP) == set(roles.SENIOR_PERMISSIONS)


def test_the_migration_is_safe_to_run_again():
    migration.grant(live_apps, None)
    migration.grant(live_apps, None)
    assert Group.objects.filter(name=MODERATORS_GROUP).count() == 1
    assert held(MODERATORS_GROUP) == set(roles.MODERATOR_PERMISSIONS)


def test_going_back_clears_the_permissions_but_keeps_the_groups():
    migration.grant(live_apps, None)
    migration.revoke(live_apps, None)
    assert Group.objects.filter(name__in=[MODERATORS_GROUP, SENIORS_GROUP]).count() == 2
    assert held(MODERATORS_GROUP) == set() and held(SENIORS_GROUP) == set()


def test_the_test_database_got_its_groups_from_the_migration_itself():
    """pytest-django builds the database by migrating from nothing and runs ordinary `db` tests
    before the `transaction=True` ones (which flush it), so the groups are the migration's."""
    assert held(MODERATORS_GROUP) == set(roles.MODERATOR_PERMISSIONS)
    assert held(SENIORS_GROUP) == set(roles.SENIOR_PERMISSIONS)


def test_the_sync_creates_a_missing_group_and_removes_a_permission_it_should_not_hold():
    Group.objects.filter(name=SENIORS_GROUP).delete()
    moderators = Group.objects.get(name=MODERATORS_GROUP)
    moderators.permissions.add(Permission.objects.get(codename="delete_post"))
    roles.sync_role_groups()
    roles.sync_role_groups()  # idempotent
    assert held(MODERATORS_GROUP) == set(roles.MODERATOR_PERMISSIONS)
    assert held(SENIORS_GROUP) == set(roles.SENIOR_PERMISSIONS)


def test_a_permission_that_does_not_exist_is_an_error_not_a_silent_skip():
    with pytest.raises(Permission.DoesNotExist):
        roles.permissions_for(["posts.fly_post"])


def test_every_listed_permission_exists_and_none_is_listed_twice():
    everything = [*roles.MODERATOR_PERMISSIONS, *roles.SENIOR_PERMISSIONS]
    assert len(everything) == len(set(everything))
    assert len(roles.permissions_for(everything)) == len(everything)


def perms_of(user):
    return set(user.get_all_permissions())


def test_a_moderator_has_the_moderator_set_and_no_more(role_groups):
    moderator = UserFactory(role=Role.MODERATOR)
    assert perms_of(moderator) == set(roles.MODERATOR_PERMISSIONS)


def test_a_senior_moderator_has_both_sets(role_groups):
    senior = UserFactory(role=Role.SENIOR_MODERATOR)
    assert perms_of(senior) == set(roles.MODERATOR_PERMISSIONS) | set(roles.SENIOR_PERMISSIONS)


def test_an_ordinary_user_has_nothing(role_groups):
    assert perms_of(UserFactory()) == set()


@pytest.mark.parametrize(
    "name",
    [
        "accounts.change_user",
        "accounts.delete_user",
        "core.change_platformsettings",
        "moderation.view_moderationaction",
        "admin.view_logentry",
        "posts.delete_post",
        "posts.add_post",
        "social.view_bookmark",
        "social.view_like",
        "social.view_follow",
        "social.view_repost",
        "reports.change_report",
    ],
)
def test_a_moderator_lacks_what_the_task_reserves_for_seniors_and_superusers(role_groups, name):
    assert name not in perms_of(UserFactory(role=Role.MODERATOR))


@pytest.mark.parametrize(
    "name",
    [
        "posts.delete_post",
        "posts.add_post",
        "social.view_bookmark",
        "social.view_like",
        "accounts.add_user",
        "core.add_platformsettings",
        "core.delete_platformsettings",
        "moderation.add_moderationaction",
        "moderation.change_moderationaction",
        "moderation.delete_moderationaction",
        "admin.change_logentry",
        "admin.delete_logentry",
    ],
)
def test_a_senior_moderator_still_lacks_these(role_groups, name):
    assert name not in perms_of(UserFactory(role=Role.SENIOR_MODERATOR))


def test_changing_the_role_moves_the_permissions_with_the_groups(role_groups):
    person = UserFactory(role=Role.USER)
    person.role = Role.SENIOR_MODERATOR
    person.save()
    person = type(person).objects.get(pk=person.pk)  # fresh permission cache
    assert "admin.view_logentry" in perms_of(person)
    person.role = Role.MODERATOR
    person.save()
    person = type(person).objects.get(pk=person.pk)
    assert "admin.view_logentry" not in perms_of(person)
    assert "posts.change_post" in perms_of(person)
