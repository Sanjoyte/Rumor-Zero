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

migration = importlib.import_module("apps.moderation.migrations.0005_reputation_permission")
appeal_migration = importlib.import_module("apps.moderation.migrations.0004_appeal_permission")
first_migration = importlib.import_module("apps.moderation.migrations.0002_role_groups")


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


def test_part_10s_migration_keeps_its_own_lists_and_gives_the_groups_exactly_those():
    """`0002` is frozen: it gives moderators no appeal permission, whatever `roles.py` says now."""
    assert first_migration.MODERATOR_PERMISSIONS == appeal_migration.PREVIOUS_MODERATOR_PERMISSIONS
    assert first_migration.SENIOR_PERMISSIONS == appeal_migration.SENIOR_PERMISSIONS
    assert "moderation.view_appeal" not in first_migration.MODERATOR_PERMISSIONS
    Group.objects.all().delete()
    first_migration.grant(live_apps, None)
    assert held(MODERATORS_GROUP) == set(first_migration.MODERATOR_PERMISSIONS)
    assert held(SENIORS_GROUP) == set(first_migration.SENIOR_PERMISSIONS)


def test_part_11s_migration_keeps_its_own_lists_and_gives_the_groups_exactly_those():
    """`0004` is frozen too: it gives moderators no ledger permission."""
    assert appeal_migration.MODERATOR_PERMISSIONS == migration.PREVIOUS_MODERATOR_PERMISSIONS
    assert appeal_migration.SENIOR_PERMISSIONS == migration.SENIOR_PERMISSIONS
    assert "reputation.view_reputationevent" not in appeal_migration.MODERATOR_PERMISSIONS
    Group.objects.all().delete()
    appeal_migration.grant(live_apps, None)
    assert held(MODERATORS_GROUP) == set(appeal_migration.MODERATOR_PERMISSIONS)
    assert held(SENIORS_GROUP) == set(appeal_migration.SENIOR_PERMISSIONS)
    assert "moderation.view_appeal" in held(MODERATORS_GROUP)


def test_part_11bs_migration_gives_both_groups_exactly_the_declared_permissions():
    Group.objects.all().delete()
    migration.grant(live_apps, None)
    assert held(MODERATORS_GROUP) == set(roles.MODERATOR_PERMISSIONS)
    assert held(SENIORS_GROUP) == set(roles.SENIOR_PERMISSIONS)
    assert "reputation.view_reputationevent" in held(MODERATORS_GROUP)


def test_the_three_migrations_run_in_order_and_end_with_the_live_lists():
    Group.objects.all().delete()
    first_migration.grant(live_apps, None)
    appeal_migration.grant(live_apps, None)
    migration.grant(live_apps, None)
    assert held(MODERATORS_GROUP) == set(roles.MODERATOR_PERMISSIONS)


def test_the_migration_is_safe_to_run_again():
    migration.grant(live_apps, None)
    migration.grant(live_apps, None)
    assert Group.objects.filter(name=MODERATORS_GROUP).count() == 1
    assert held(MODERATORS_GROUP) == set(roles.MODERATOR_PERMISSIONS)


def test_going_back_over_part_10s_migration_clears_the_permissions_but_keeps_the_groups():
    first_migration.grant(live_apps, None)
    first_migration.revoke(live_apps, None)
    assert Group.objects.filter(name__in=[MODERATORS_GROUP, SENIORS_GROUP]).count() == 2
    assert held(MODERATORS_GROUP) == set() and held(SENIORS_GROUP) == set()


def test_going_back_over_part_11s_migration_returns_to_part_10s_lists_not_to_nothing():
    """`migrate moderation 0003` must leave moderators able to work (0002's own reverse would have
    cleared both groups)."""
    appeal_migration.grant(live_apps, None)
    appeal_migration.revoke(live_apps, None)
    assert held(MODERATORS_GROUP) == set(first_migration.MODERATOR_PERMISSIONS)
    assert held(SENIORS_GROUP) == set(first_migration.SENIOR_PERMISSIONS)


def test_going_back_over_part_11bs_migration_returns_to_part_11s_lists():
    """`migrate moderation 0004` leaves moderators the appeals, without the ledger."""
    migration.grant(live_apps, None)
    migration.revoke(live_apps, None)
    assert held(MODERATORS_GROUP) == set(appeal_migration.MODERATOR_PERMISSIONS)
    assert held(SENIORS_GROUP) == set(appeal_migration.SENIOR_PERMISSIONS)


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
        "moderation.change_appeal",
        "moderation.delete_appeal",
        "moderation.add_appeal",
        "reputation.add_reputationevent",
        "reputation.change_reputationevent",
        "reputation.delete_reputationevent",
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
        "moderation.add_appeal",
        "moderation.change_appeal",
        "moderation.delete_appeal",
        "admin.change_logentry",
        "admin.delete_logentry",
        "reputation.add_reputationevent",
        "reputation.change_reputationevent",
        "reputation.delete_reputationevent",
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


def test_a_moderator_and_a_senior_can_view_appeals_and_an_ordinary_user_cannot(role_groups):
    assert "moderation.view_appeal" in perms_of(UserFactory(role=Role.MODERATOR))
    assert "moderation.view_appeal" in perms_of(UserFactory(role=Role.SENIOR_MODERATOR))
    assert "moderation.view_appeal" not in perms_of(UserFactory())


def test_moderators_and_seniors_can_read_the_ledger_and_an_ordinary_user_cannot(role_groups):
    """User decision 2026-10-13 (Part 11B): moderators and up read the whole ledger."""
    assert "reputation.view_reputationevent" in perms_of(UserFactory(role=Role.MODERATOR))
    assert "reputation.view_reputationevent" in perms_of(UserFactory(role=Role.SENIOR_MODERATOR))
    assert "reputation.view_reputationevent" not in perms_of(UserFactory())
