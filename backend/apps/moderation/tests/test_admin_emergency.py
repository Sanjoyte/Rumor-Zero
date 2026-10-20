"""Part 11C in Django Admin (ARCHITECTURE §8): active emergencies first in the queue, the
emergency filter, Demote emergency, Mark FALSE's confirmation, and Block / Unblock emergency
posting on accounts."""

from datetime import timedelta

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import MODERATORS_GROUP, Role, User
from apps.accounts.tests.factories import UserFactory
from apps.moderation import services
from apps.moderation.models import ActionKind, ModerationAction
from apps.moderation.tests.factories import moderator_user, senior_user
from apps.posts.models import FlaggedReason, Post, PostStatus, PostType
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("role_groups")]

POSTS = reverse("admin:posts_post_changelist")
USERS = reverse("admin:accounts_user_changelist")


@pytest.fixture
def mod(client):
    user = moderator_user()
    client.force_login(user)
    return user


def reviewed(content, *, reports=0, started_hours_ago=1, **fields):
    fields.setdefault("flagged_reason", FlaggedReason.REPORTS)
    fields.setdefault("pre_review_status", PostStatus.PENDING)
    return PostFactory(
        content=content,
        post_type=PostType.FACT,
        status=PostStatus.UNDER_REVIEW,
        review_started_at=timezone.now() - timedelta(hours=started_hours_ago),
        report_count=reports,
        **fields,
    )


def urgent(*, active=True, **fields):
    """The emergency fields of an active (or expired) emergency."""
    now = timezone.now()
    return {
        "is_emergency": True,
        "emergency_expires_at": now + timedelta(hours=20) if active else now - timedelta(hours=1),
        **fields,
    }


def position(page, text):
    return page.content.decode().index(text)


def texts(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def act(client, url, name, *objects, apply=False, **extra):
    data = {"action": name, "_selected_action": [str(o.pk) for o in objects], **extra}
    if apply:
        data["apply"] = "1"
    else:
        data.update({"index": "0", "select_across": "0"})
    return client.post(url, data)


# ---------- the queue ----------


def test_active_emergencies_come_first_whatever_their_reports(client, mod):
    reviewed("zz most reports", reports=9)
    reviewed("zz expired emergency", reports=2, **urgent(active=False))
    reviewed("zz active emergency", reports=0, started_hours_ago=0.1, **urgent())
    reviewed("zz demoted emergency", reports=1, **urgent(emergency_demoted_at=timezone.now()))
    page = client.get(POSTS)
    order = [
        "zz active emergency",
        "zz most reports",
        "zz expired emergency",
        "zz demoted emergency",
    ]
    positions = [position(page, text) for text in order]
    assert positions == sorted(positions)


def test_the_emergency_column_sorts_active_first(client, mod):
    reviewed("aa ordinary", reports=5)
    reviewed("bb active", **urgent())
    names = ["action_checkbox", *admin.site._registry[Post].get_list_display(None)]
    column = names.index("emergency")
    first = client.get(POSTS, {"o": str(column)})
    assert position(first, "bb active") < position(first, "aa ordinary")
    flipped = client.get(POSTS, {"o": f"-{column}"})
    assert position(flipped, "aa ordinary") < position(flipped, "bb active")


def test_the_emergency_filter_leaves_the_queue_so_an_active_one_can_be_found(client, mod):
    PostFactory(content="pinned and not reviewed", fact=True, **urgent())
    PostFactory(content="over", fact=True, **urgent(active=False))
    reviewed("ordinary review")
    queue = client.get(POSTS).content.decode()
    assert "pinned and not reviewed" not in queue  # not under review: not in the queue
    active = client.get(POSTS, {"emergency": "active"}).content.decode()
    assert "pinned and not reviewed" in active
    assert "over" not in active and "ordinary review" not in active
    ended = client.get(POSTS, {"emergency": "ended"}).content.decode()
    assert "over" in ended and "pinned and not reviewed" not in ended


def test_the_queue_page_still_costs_the_same_with_emergencies(
    client, mod, django_assert_max_num_queries
):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def count():
        with CaptureQueriesContext(connection) as captured:
            assert client.get(POSTS).status_code == 200
        return len(captured)

    for i in range(3):
        reviewed(f"emergency {i}", **urgent())
    small = count()
    for i in range(30):
        reviewed(f"more {i}", **(urgent() if i % 2 else {}))
    assert count() == small


# ---------- Demote emergency ----------


def test_demote_is_offered_only_on_an_active_emergency(client, mod):
    active = PostFactory(fact=True, **urgent())
    over = PostFactory(fact=True, **urgent(active=False))
    plain = reviewed("plain")
    for post, offered in ((active, True), (over, False), (plain, False)):
        page = client.get(reverse("admin:posts_post_change", args=[post.pk])).content.decode()
        assert ('value="demote_emergency"' in page) is offered


def test_demote_asks_first_then_logs_and_ends_the_priority(client, mod):
    post = PostFactory(content="Bridge out", fact=True, **urgent())
    page = act(client, POSTS + "?queue=all", "demote_emergency", post)
    body = page.content.decode()
    assert page.status_code == 200
    assert "Demote emergency: are you sure?" in body
    assert "Pending → Pending (priority ends)" in body.replace("&rarr;", "→")
    assert "<th>Emergency</th>" in body and "Active" in body
    assert 'name="public_note"' not in body  # internal notes only
    done = act(client, POSTS + "?queue=all", "demote_emergency", post, apply=True, notes="Hoax.")
    assert done.status_code == 302
    assert "Demoted 1 emergency post." in texts(done)
    row = ModerationAction.objects.get()
    assert (row.action, row.moderator, row.notes) == (ActionKind.EMERGENCY_DEMOTED, mod, "Hoax.")
    assert Post.objects.get(pk=post.pk).emergency_demoted_at is not None


def test_demote_skips_what_is_not_an_active_emergency(client, mod):
    over = PostFactory(content="Over now", fact=True, **urgent(active=False))
    body = act(client, POSTS + "?queue=all", "demote_emergency", over).content.decode()
    assert "not an active emergency" in body
    assert "None of the selected posts can have this done to them." in body


def test_an_opinions_only_list_offers_no_demote(client, mod):
    page = client.get(POSTS, {"post_type__exact": "opinion"}).content.decode()
    assert "demote_emergency" not in page
    assert "demote_emergency" in client.get(POSTS).content.decode()


def test_mark_false_says_the_priority_ends_and_the_author_is_blocked(client, mod):
    post = reviewed("A false alarm", **urgent())
    body = act(client, POSTS, "mark_false", post).content.decode().replace("&rarr;", "→")
    assert "Under review → Verified false (priority ends, author blocked 30 days)" in body


def test_mark_false_on_a_label_appeal_of_an_emergency_says_no_block(
    client, mod, emergency_settings
):
    post = reviewed(
        "Appealed",
        flagged_reason=FlaggedReason.APPEAL,
        pre_review_status=PostStatus.VERIFIED_FALSE,
        **urgent(active=False),
    )
    body = act(client, POSTS, "mark_false", post).content.decode().replace("&rarr;", "→")
    assert "Under review → Verified false</td>" in body
    emergency_settings(emergency_false_cooldown_days=0)
    fresh = reviewed("Fresh", **urgent(active=False))
    body = act(client, POSTS, "mark_false", fresh).content.decode().replace("&rarr;", "→")
    assert "author blocked" not in body


# ---------- Block / Unblock emergency posting (UserAdmin) ----------


@pytest.mark.parametrize("who", ["moderator", "senior", "superuser"])
def test_moderators_and_up_block_and_unblock_with_a_confirmation(client, who):
    actor = {
        "moderator": moderator_user,
        "senior": senior_user,
        "superuser": lambda: User.objects.create_superuser(
            "root@example.test", "root", "a-long-password-1"
        ),
    }[who]()
    client.force_login(actor)
    target = VerifiedUserFactory(username="target_person")
    page = act(client, USERS, "block_emergency", target)
    body = page.content.decode()
    assert page.status_code == 200
    assert "Block emergency posting: are you sure?" in body
    assert "A block lasts 30 days" in body and "target_person" in body
    done = act(client, USERS, "block_emergency", target, apply=True, notes="Repeated hoaxes.")
    assert done.status_code == 302
    assert "Blocked emergency posting on 1 account." in texts(done)
    row = ModerationAction.objects.get()
    assert (row.action, row.subject_user, row.moderator, row.post) == (
        ActionKind.EMERGENCY_BLOCKED,
        target,
        actor,
        None,
    )
    assert row.notes == "Repeated hoaxes."
    assert User.objects.get(pk=target.pk).emergency_blocked_until == row.blocked_until
    page = act(client, USERS, "unblock_emergency", target)
    assert "Unblocking lifts every block" in page.content.decode()
    done = act(client, USERS, "unblock_emergency", target, apply=True)
    assert "Unblocked emergency posting on 1 account." in texts(done)
    assert User.objects.get(pk=target.pk).emergency_blocked_until is None


def test_a_moderator_sees_the_actions_on_the_read_only_account_list(client, mod):
    VerifiedUserFactory()
    page = client.get(USERS).content.decode()
    assert 'value="block_emergency"' in page and 'value="unblock_emergency"' in page
    assert 'value="verify_email"' not in page  # that one needs `accounts.change_user`


def test_a_superuser_account_and_your_own_are_skipped(client, mod):
    root = User.objects.create_superuser("root@example.test", "root", "a-long-password-1")
    body = act(client, USERS, "block_emergency", root, mod).content.decode()
    assert "a superuser&#x27;s account" in body and "your own account" in body
    act(client, USERS, "block_emergency", root, mod, apply=True)
    assert not ModerationAction.objects.exists()


def test_an_account_that_is_not_blocked_is_skipped_by_unblock(client, mod):
    target = VerifiedUserFactory()
    response = act(client, USERS, "unblock_emergency", target, apply=True)
    assert "Skipped 1: 1 not blocked." in texts(response)


def test_staff_without_the_permission_and_non_staff_get_nothing(client):
    group = Group.objects.get(name=MODERATORS_GROUP)
    group.permissions.remove(Permission.objects.get(codename="block_emergency_posting"))
    moderator = moderator_user()
    client.force_login(moderator)
    target = VerifiedUserFactory()
    page = client.get(USERS).content.decode()
    assert "block_emergency" not in page
    act(client, USERS, "block_emergency", target, apply=True)
    assert not ModerationAction.objects.exists()
    client.force_login(VerifiedUserFactory())  # not staff
    response = act(client, USERS, "block_emergency", target, apply=True)
    assert response.status_code == 302 and "/login/" in response["Location"]
    assert not ModerationAction.objects.exists()


def test_the_apply_step_acts_on_the_shown_ids_never_select_across(client, mod):
    shown = VerifiedUserFactory()
    VerifiedUserFactory()
    response = client.post(
        USERS,
        {
            "action": "block_emergency",
            "apply": "1",
            "select_across": "1",
            "_selected_action": [str(shown.pk), "not-a-uuid"],
        },
    )
    assert response.status_code == 302
    assert list(ModerationAction.objects.values_list("subject_user", flat=True)) == [shown.pk]


def test_the_emergency_posting_filter(client, mod):
    blocked = VerifiedUserFactory(username="is_blocked")
    VerifiedUserFactory(username="is_free")
    VerifiedUserFactory(
        username="was_blocked", emergency_blocked_until=timezone.now() - timedelta(days=1)
    )
    services.block_emergency_posting(blocked.pk, moderator=senior_user())
    page = client.get(USERS, {"emergency_posting": "blocked"}).content.decode()
    assert "is_blocked" in page and "is_free" not in page and "was_blocked" not in page
    page = client.get(USERS, {"emergency_posting": "free"}).content.decode()
    assert "is_free" in page and "was_blocked" in page and "is_blocked" not in page


def test_the_account_page_lists_its_blocks_for_holders_of_the_permission(client, mod):
    author = VerifiedUserFactory()
    post = reviewed("A false alarm", author=author, **urgent())
    services.mark_false(post.pk, moderator=moderator_user(username="decider"))
    services.unblock_emergency_posting(author.pk, moderator=senior_user(username="lifter"))
    page = client.get(reverse("admin:accounts_user_change", args=[author.pk])).content.decode()
    assert "Emergency blocks" in page
    assert "Emergency posting blocked" in page and "Emergency posting unblocked" in page
    assert "decider" in page and "lifter" in page
    assert "Automatic: the emergency post was labelled FALSE." in page
    assert reverse("admin:posts_post_change", args=[post.pk]) in page


def test_the_account_page_hides_the_blocks_without_the_permission(client):
    group = Group.objects.get(name=MODERATORS_GROUP)
    group.permissions.remove(Permission.objects.get(codename="block_emergency_posting"))
    client.force_login(moderator_user())
    author = VerifiedUserFactory()
    page = client.get(reverse("admin:accounts_user_change", args=[author.pk])).content.decode()
    assert "Emergency blocks" not in page


def test_the_full_log_names_the_account_and_finds_it(client):
    client.force_login(senior_user())
    target = VerifiedUserFactory(username="subject_person")
    services.block_emergency_posting(target.pk, moderator=moderator_user())
    url = reverse("admin:moderation_moderationaction_changelist")
    page = client.get(url).content.decode()
    assert "subject_person" in page
    assert "subject_person" in client.get(url, {"q": "subject_person"}).content.decode()


def test_the_account_form_still_saves_for_a_superuser(client):
    """The history is a read-only field, so the account form's own POST is unchanged."""
    root = User.objects.create_superuser("root@example.test", "root", "a-long-password-1")
    client.force_login(root)
    target = UserFactory()
    services.block_emergency_posting(target.pk, moderator=root)
    until = User.objects.get(pk=target.pk).emergency_blocked_until
    response = client.post(
        reverse("admin:accounts_user_change", args=[target.pk]),
        {
            "email": target.email,
            "username": target.username,
            "display_name": "Renamed",
            "bio": "",
            "role": Role.USER,
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    fresh = User.objects.get(pk=target.pk)
    assert fresh.display_name == "Renamed"
    assert fresh.emergency_blocked_until == until  # the form never writes it
