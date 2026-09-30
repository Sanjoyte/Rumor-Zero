import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import Role, User
from apps.accounts.tests.factories import UserFactory
from apps.accounts.validators import RESERVED_USERNAMES, validate_username

pytestmark = pytest.mark.django_db


def group_names(user):
    return set(user.groups.values_list("name", flat=True))


def reloaded(user):
    return User.objects.get(pk=user.pk)


# ---------- normalisation and validation ----------


def test_create_user_normalises_email_and_username():
    user = User.objects.create_user(email="  Ada@Example.COM ", username=" ＡDA_1 ", password="x")
    assert user.email == "ada@example.com"
    assert user.username == "ada_1"  # NFKC folds the full-width "Ａ", then lower-cased


def test_save_normalises_a_directly_built_user():
    user = User(email="Bo@Example.com", username="Bo_Bo")
    user.set_password("x")
    user.save()
    stored = reloaded(user)
    assert (stored.email, stored.username) == ("bo@example.com", "bo_bo")


def test_full_clean_normalises_before_the_uniqueness_check():
    UserFactory(username="ada_love", email="ada@example.test")
    duplicate = User(username="Ada_Love", email="Other@Example.test")
    with pytest.raises(ValidationError) as excinfo:
        duplicate.full_clean(exclude=["password"])
    assert "username" in excinfo.value.message_dict


def test_password_none_makes_the_password_unusable():
    user = User.objects.create_user(email="g@example.test", username="google_user")
    assert not user.has_usable_password()


@pytest.mark.parametrize(
    "username", ["ab", "a" * 31, "ada-love", "ada love", "adé_", "ada.love", "ada\nlove", ""]
)
def test_username_format_is_rejected(username):
    with pytest.raises(ValidationError) as excinfo:
        validate_username(username)
    assert excinfo.value.code == "invalid_username"


@pytest.mark.parametrize("username", ["Ada", "ada_99", "A" * 30, "___", "ada_admin", "admin1"])
def test_valid_usernames_are_accepted(username):
    validate_username(username)


@pytest.mark.parametrize("word", sorted(RESERVED_USERNAMES))
def test_every_reserved_username_is_rejected_in_any_case(word):
    for variant in (word, word.upper(), word.title()):
        with pytest.raises(ValidationError) as excinfo:
            validate_username(variant)
        assert excinfo.value.code == "reserved_username"


def test_model_validator_rejects_reserved_username():
    user = User(username="Admin", email="x@example.test")
    with pytest.raises(ValidationError) as excinfo:
        user.full_clean(exclude=["password"])
    assert "username" in excinfo.value.message_dict


def test_get_by_natural_key_ignores_case():
    user = UserFactory(email="mixed@example.test")
    assert User.objects.get_by_natural_key("MIXED@Example.TEST") == user


# ---------- role → groups and is_staff ----------


def test_role_changes_sync_groups_and_is_staff():
    user = UserFactory()
    assert group_names(user) == set()
    assert user.is_staff is False

    user.role = Role.MODERATOR
    user.save()
    assert group_names(user) == {"Moderators"}
    assert reloaded(user).is_staff is True

    user.role = Role.SENIOR_MODERATOR
    user.save()
    assert group_names(user) == {"Moderators", "Senior moderators"}
    assert reloaded(user).is_staff is True

    user.role = Role.MODERATOR
    user.save()
    assert group_names(user) == {"Moderators"}

    user.role = Role.USER
    user.save()
    assert group_names(user) == set()
    assert reloaded(user).is_staff is False


def test_role_sync_leaves_unrelated_groups_alone():
    user = UserFactory()
    user.groups.add(Group.objects.create(name="Reviewers"))
    user.role = Role.MODERATOR
    user.save()
    user.role = Role.USER
    user.save()
    assert group_names(user) == {"Reviewers"}


def test_role_saved_through_update_fields_still_updates_is_staff():
    user = UserFactory()
    user.role = Role.MODERATOR
    user.save(update_fields=["role"])
    stored = reloaded(user)
    assert stored.is_staff is True
    assert group_names(stored) == {"Moderators"}


def test_superuser_keeps_is_staff_with_role_user_and_across_role_changes():
    superuser = User.objects.create_superuser(
        email="root@example.test", username="root_user", password="x"
    )
    assert superuser.role == Role.USER
    assert superuser.is_staff is True
    assert group_names(superuser) == set()

    superuser.role = Role.MODERATOR
    superuser.save()
    assert reloaded(superuser).is_staff is True
    assert group_names(superuser) == {"Moderators"}

    superuser.role = Role.USER
    superuser.save()
    assert reloaded(superuser).is_staff is True
    assert group_names(superuser) == set()


def test_last_login_only_save_is_a_single_query(django_assert_num_queries):
    user = reloaded(UserFactory())
    with django_assert_num_queries(1):
        user.save(update_fields=["last_login"])


# ---------- database constraints ----------


def test_new_users_start_at_score_50():
    user = UserFactory()
    assert reloaded(user).reputation_score == 50
    assert reloaded(user).reputation_sample == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"reputation_score": -1},
        {"reputation_score": 101},
        {"reputation_sample": -1},
        {"username": "UPPER_CASE"},
        {"email": "UPPER@EXAMPLE.TEST"},
        {"role": "superhero"},
    ],
)
def test_database_rejects_invalid_values(changes):
    user = UserFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=user.pk).update(**changes)


@pytest.mark.parametrize("score", [0, 100])
def test_database_accepts_the_score_bounds(score):
    user = UserFactory()
    User.objects.filter(pk=user.pk).update(reputation_score=score)
    assert reloaded(user).reputation_score == score
