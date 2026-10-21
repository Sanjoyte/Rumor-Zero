"""Remove photo, Block photo uploads and Allow photo uploads (Part 14B; ARCHITECTURE §4e, §8): the
rules, the service, its audit rows and its locks."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts import avatars
from apps.accounts.models import Avatar, User
from apps.accounts.tests import photo_fixtures as fx
from apps.accounts.tests.conftest import run_together
from apps.moderation import rules, services
from apps.moderation.models import ActionKind, ModerationAction
from apps.moderation.tests.factories import moderator_user, senior_user
from apps.notifications.models import Notification
from apps.posts.tests.factories import VerifiedUserFactory

pytestmark = pytest.mark.django_db

Act = rules.AccountAct
PHOTO_KINDS = {ActionKind.AVATAR_REMOVED, ActionKind.AVATAR_BLOCKED, ActionKind.AVATAR_UNBLOCKED}


def person(*, photo=True, blocked=False, **fields):
    user = VerifiedUserFactory(**fields)
    if photo:
        fx.give_photo(user)
    if blocked:
        User.objects.filter(pk=user.pk).update(avatar_uploads_blocked=True)
    return User.objects.get(pk=user.pk)


def rows():
    return list(ModerationAction.objects.order_by("created_at", "id"))


def state(user):
    fresh = User.objects.get(pk=user.pk)
    return (
        fresh.avatar_version,
        fresh.avatar_uploads_blocked,
        Avatar.objects.filter(user=user).exists(),
    )


# ---------- the rules ----------


def target(*, photo=False, blocked=False, superuser=False, pk=1):
    return SimpleNamespace(
        pk=pk,
        is_superuser=superuser,
        avatar_version="0123456789abcdef" if photo else None,
        avatar_uploads_blocked=blocked,
        emergency_blocked_until=None,
    )


def refusal(act, who, **kwargs):
    return rules.account_refusal(
        act, who, SimpleNamespace(pk=99, is_superuser=False), block_days=0, now=None, **kwargs
    )


@pytest.mark.parametrize(
    ("act", "account", "code"),
    [
        (Act.REMOVE_PHOTO, target(photo=False), "no_photo"),
        (Act.REMOVE_PHOTO, target(photo=True), None),
        (Act.REMOVE_PHOTO, target(photo=True, blocked=True), None),
        (Act.BLOCK_PHOTO_UPLOADS, target(blocked=True), "uploads_already_blocked"),
        (Act.BLOCK_PHOTO_UPLOADS, target(photo=True, blocked=True), "uploads_already_blocked"),
        (Act.BLOCK_PHOTO_UPLOADS, target(photo=False), None),
        (Act.BLOCK_PHOTO_UPLOADS, target(photo=True), None),
        (Act.ALLOW_PHOTO_UPLOADS, target(blocked=False), "uploads_not_blocked"),
        (Act.ALLOW_PHOTO_UPLOADS, target(blocked=True), None),
        (Act.ALLOW_PHOTO_UPLOADS, target(photo=True, blocked=True), None),
    ],
)
def test_the_photo_rules(act, account, code):
    result = refusal(act, account)
    assert (result.code if result else None) == code


def test_nobody_but_a_superuser_acts_on_a_superuser_or_themselves():
    root = target(photo=True, superuser=True, pk=7)
    for act in rules.PHOTO_ACTS:
        assert refusal(act, root).code == "superuser_account"
    me = target(photo=True, pk=99)
    for act in rules.PHOTO_ACTS:
        assert refusal(act, me).code == "own_account"
    boss = SimpleNamespace(pk=99, is_superuser=True)
    assert rules.account_refusal(Act.REMOVE_PHOTO, root, boss, block_days=0, now=None) is None


def test_the_photo_acts_and_the_emergency_acts_are_apart():
    assert rules.PHOTO_ACTS.isdisjoint(rules.EMERGENCY_ACTS)
    assert set(Act) == rules.PHOTO_ACTS | rules.EMERGENCY_ACTS


# ---------- Remove photo ----------


def test_remove_photo_takes_the_photo_down_and_logs_it_with_the_account():
    account, moderator = person(), moderator_user()
    entry = services.remove_photo(account.pk, moderator=moderator, notes="Not a face.")

    assert state(account) == (None, False, False)
    assert (entry.action, entry.subject_user, entry.moderator, entry.post) == (
        ActionKind.AVATAR_REMOVED,
        account,
        moderator,
        None,
    )
    assert (entry.post_snapshot, entry.public_note, entry.notes) == ("", "", "Not a face.")
    assert (entry.from_status, entry.to_status, entry.blocked_until, entry.appeal) == (
        None,
        None,
        None,
        None,
    )
    assert rows() == [entry]


def test_remove_photo_leaves_uploads_allowed_so_a_new_photo_can_follow(client):
    account = person()
    services.remove_photo(account.pk, moderator=moderator_user())
    assert avatars.save_photo(account.pk, fx.jpeg(colour=fx.BLUE))
    assert state(account)[2] is True


def test_remove_photo_only_touches_that_account():
    ada, bo = person(), person()
    before = Avatar.objects.get(user=bo).version
    services.remove_photo(ada.pk, moderator=moderator_user())
    assert (
        Avatar.objects.get(user=bo).version == before == User.objects.get(pk=bo.pk).avatar_version
    )


def test_remove_photo_with_no_photo_is_refused_and_writes_nothing():
    account = person(photo=False)
    with pytest.raises(services.ActionRefused) as refused:
        services.remove_photo(account.pk, moderator=moderator_user())
    assert refused.value.refusal.code == "no_photo"
    assert not ModerationAction.objects.exists()


def test_the_action_uses_the_given_clock():
    moment = timezone.now() - timedelta(days=3)
    entry = services.remove_photo(person().pk, moderator=moderator_user(), now=moment)
    assert entry.created_at == moment


# ---------- Block photo uploads ----------


def test_block_removes_the_photo_too_and_logs_removed_then_blocked_a_microsecond_apart():
    account, moderator = person(), moderator_user()
    entry = services.block_photo_uploads(account.pk, moderator=moderator, notes="Abusive.")

    assert state(account) == (None, True, False)
    removed, blocked = rows()
    assert (removed.action, blocked.action) == (
        ActionKind.AVATAR_REMOVED,
        ActionKind.AVATAR_BLOCKED,
    )
    assert blocked.created_at - removed.created_at == timedelta(microseconds=1)
    assert entry == blocked
    for row in (removed, blocked):
        assert (row.subject_user, row.moderator, row.post, row.notes) == (
            account,
            moderator,
            None,
            "Abusive.",
        )


def test_block_on_an_account_with_no_photo_logs_only_the_block():
    account = person(photo=False)
    services.block_photo_uploads(account.pk, moderator=moderator_user())
    assert [row.action for row in rows()] == [ActionKind.AVATAR_BLOCKED]
    assert state(account) == (None, True, False)


def test_an_already_blocked_account_is_refused_and_writes_nothing():
    account = person(photo=False, blocked=True)
    with pytest.raises(services.ActionRefused) as refused:
        services.block_photo_uploads(account.pk, moderator=moderator_user())
    assert refused.value.refusal.code == "uploads_already_blocked"
    assert not ModerationAction.objects.exists()


def test_uploads_fail_with_403_while_blocked(api_client):
    from apps.accounts.tests.conftest import access_token_for

    account = person(photo=False)
    services.block_photo_uploads(account.pk, moderator=moderator_user())
    response = api_client.put(
        "/api/v1/me/avatar/",
        {"file": fx.upload(fx.jpeg())},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {access_token_for(account)}",
    )
    assert response.status_code == 403 and response.json()["code"] == "photo_uploads_blocked"
    with pytest.raises(avatars.PhotoUploadsBlocked):
        avatars.save_photo(account.pk, fx.jpeg())


def test_the_avatar_url_is_null_in_the_account_payload_at_once(api_client):
    from apps.accounts.tests.conftest import access_token_for

    account = person()
    token = access_token_for(account)
    services.block_photo_uploads(account.pk, moderator=moderator_user())
    me = api_client.get("/api/v1/me/", HTTP_AUTHORIZATION=f"Bearer {token}").json()
    assert me["avatar_url"] is None and me["avatar_uploads_blocked"] is True


# ---------- Allow photo uploads ----------


def test_allow_lifts_the_block_logs_it_and_lets_a_new_photo_in():
    account = person(photo=False, blocked=True)
    moderator = senior_user()
    entry = services.allow_photo_uploads(account.pk, moderator=moderator, notes="Appealed, fine.")

    assert state(account) == (None, False, False)
    assert (entry.action, entry.subject_user, entry.moderator, entry.notes) == (
        ActionKind.AVATAR_UNBLOCKED,
        account,
        moderator,
        "Appealed, fine.",
    )
    assert avatars.save_photo(account.pk, fx.jpeg())


def test_allow_does_not_bring_a_removed_photo_back():
    account = person()
    services.block_photo_uploads(account.pk, moderator=moderator_user())
    services.allow_photo_uploads(account.pk, moderator=moderator_user())
    assert state(account) == (None, False, False)


def test_allow_on_an_account_that_is_not_blocked_is_refused():
    account = person(photo=False)
    with pytest.raises(services.ActionRefused) as refused:
        services.allow_photo_uploads(account.pk, moderator=moderator_user())
    assert refused.value.refusal.code == "uploads_not_blocked"
    assert not ModerationAction.objects.exists()


# ---------- Every action ----------


@pytest.mark.parametrize(
    "run",
    [services.remove_photo, services.block_photo_uploads, services.allow_photo_uploads],
)
def test_an_unknown_account_is_refused(run):
    import uuid

    with pytest.raises(services.ActionRefused) as refused:
        run(uuid.uuid4(), moderator=moderator_user())
    assert refused.value.refusal.code == "no_account"


@pytest.mark.parametrize(
    "run",
    [services.remove_photo, services.block_photo_uploads],
)
def test_a_moderator_cannot_act_on_a_superuser_or_on_themselves(run):
    root = User.objects.create_superuser("root@example.test", "root", "a-long-password-1")
    fx.give_photo(root)
    moderator = moderator_user()
    fx.give_photo(moderator)
    for account, code in ((root, "superuser_account"), (moderator, "own_account")):
        with pytest.raises(services.ActionRefused) as refused:
            run(account.pk, moderator=moderator)
        assert refused.value.refusal.code == code
    assert not ModerationAction.objects.exists()
    assert Avatar.objects.count() == 2


def test_a_superuser_may_act_on_anyone_including_themselves():
    root = User.objects.create_superuser("root@example.test", "root", "a-long-password-1")
    fx.give_photo(root)
    services.remove_photo(root.pk, moderator=root)
    assert state(root) == (None, False, False)


def test_nobody_is_told_the_nine_notification_kinds_stay_nine():
    account = person()
    services.remove_photo(account.pk, moderator=moderator_user())
    services.block_photo_uploads(account.pk, moderator=moderator_user())
    services.allow_photo_uploads(account.pk, moderator=moderator_user())
    assert not Notification.objects.exists()


def test_photo_rows_never_disturb_the_emergency_block():
    account = person()
    services.block_emergency_posting(account.pk, moderator=senior_user())
    until = User.objects.get(pk=account.pk).emergency_blocked_until
    assert until is not None
    services.block_photo_uploads(account.pk, moderator=moderator_user())
    services.allow_photo_uploads(account.pk, moderator=moderator_user())
    assert User.objects.get(pk=account.pk).emergency_blocked_until == until
    emergency = {ActionKind.EMERGENCY_BLOCKED, ActionKind.EMERGENCY_UNBLOCKED}
    assert (
        rules.standing_block_end(
            [
                rules.BlockRow(r.action, r.post_id, r.blocked_until)
                for r in rows()
                if r.action in emergency
            ]
        )
        == until
    )


def test_the_audit_row_and_the_removal_are_one_transaction(monkeypatch):
    account = person()

    def fail(*args, **kwargs):
        raise RuntimeError("the log is down")

    monkeypatch.setattr(services, "_write_photo_row", fail)
    with pytest.raises(RuntimeError):
        services.block_photo_uploads(account.pk, moderator=moderator_user())
    assert state(account)[1:] == (False, True)  # not blocked, photo still there
    assert User.objects.get(pk=account.pk).avatar_version is not None


def test_the_decision_is_made_on_the_locked_row_not_on_what_the_page_showed():
    """The owner took the photo down after the moderator's page loaded."""
    account = person()
    avatars.delete_photo(account.pk)
    with pytest.raises(services.ActionRefused) as refused:
        services.remove_photo(account.pk, moderator=moderator_user())
    assert refused.value.refusal.code == "no_photo"


def test_the_photo_kinds_are_what_the_log_calls_them():
    labels = {kind: kind.label for kind in PHOTO_KINDS}
    assert labels == {
        ActionKind.AVATAR_REMOVED: "Photo removed",
        ActionKind.AVATAR_BLOCKED: "Photo uploads blocked",
        ActionKind.AVATAR_UNBLOCKED: "Photo uploads allowed",
    }


# ---------- Races ----------


@pytest.mark.django_db(transaction=True)
def test_two_moderators_removing_the_same_photo_at_once_log_one_removal():
    account = person()

    def remove():
        try:
            services.remove_photo(account.pk, moderator=moderator_user())
            return "removed"
        except services.ActionRefused as refused:
            return refused.refusal.code

    results = run_together(remove, remove)
    assert sorted(results) == ["no_photo", "removed"]
    assert [row.action for row in rows()] == [ActionKind.AVATAR_REMOVED]


@pytest.mark.django_db(transaction=True)
def test_a_block_and_an_upload_at_the_same_moment_always_end_blocked_with_no_photo():
    """Either the upload commits first and the block takes it down, or the block commits first and
    the upload is refused under the lock. Never a blocked account with a photo."""
    for _ in range(6):
        account = person(photo=False)
        blob = fx.jpeg()

        def upload(account=account, blob=blob):
            try:
                avatars.save_photo(account.pk, blob)
                return "saved"
            except avatars.PhotoUploadsBlocked:
                return "refused"

        def block(account=account):
            services.block_photo_uploads(account.pk, moderator=moderator_user())
            return "blocked"

        outcomes = run_together(upload, block)
        assert outcomes[1] == "blocked" and outcomes[0] in ("saved", "refused")
        assert state(account) == (None, True, False)
        User.objects.filter(pk=account.pk).delete()
