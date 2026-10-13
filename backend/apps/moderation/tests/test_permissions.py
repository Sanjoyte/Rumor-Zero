"""The permission matrix of ARCHITECTURE §8, through the admin client, for each kind of person:
somebody with no staff access, a moderator, a senior moderator and a superuser."""

import pytest
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.accounts.tests.factories import UserFactory
from apps.core.models import PlatformSettings
from apps.moderation.tests.factories import AppealFactory, ModerationActionFactory
from apps.posts.models import FlaggedReason, PostStatus
from apps.posts.tests.factories import PostFactory
from apps.reports.tests.factories import ReportFactory
from apps.social.tests.factories import BookmarkFactory, CommentFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("role_groups")]

ROLES = ["nobody", "moderator", "senior", "superuser"]


def person(kind):
    if kind == "nobody":
        return UserFactory()
    if kind == "moderator":
        return UserFactory(role=Role.MODERATOR)
    if kind == "senior":
        return UserFactory(role=Role.SENIOR_MODERATOR)
    return UserFactory(is_superuser=True)


@pytest.fixture
def world():
    """One of everything the admin lists."""
    post = PostFactory(
        content="a post",
        fact=True,
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.PENDING,
    )
    return {
        "post": post,
        "report": ReportFactory(post=post),
        "comment": CommentFactory(),
        "action": ModerationActionFactory(post=post),
        "appeal": AppealFactory(),
        "bookmark": BookmarkFactory(),
        "target": UserFactory(role=Role.MODERATOR),
    }


PAGE_NAMES = [
    "admin index",
    "queue",
    "post page",
    "reports",
    "one report",
    "comments",
    "users",
    "a user's page",
    "platform settings",
    "appeals",
    "one appeal",
    "moderation log",
    "one log row",
    "admin log",
    "bookmarks",
    "likes",
    "follows",
    "reposts",
    "post history",
    "appeal history",
    "user history",
    "settings history",
    "comment history",
]


def pages(world):
    """name -> (url, expected status per role). A non-staff visitor is sent to the login (302)."""
    post, target = world["post"], world["target"]
    return {
        "admin index": (reverse("admin:index"), [302, 200, 200, 200]),
        "queue": (reverse("admin:posts_post_changelist"), [302, 200, 200, 200]),
        "post page": (reverse("admin:posts_post_change", args=[post.pk]), [302, 200, 200, 200]),
        "reports": (reverse("admin:reports_report_changelist"), [302, 200, 200, 200]),
        "one report": (
            reverse("admin:reports_report_change", args=[world["report"].pk]),
            [302, 200, 200, 200],
        ),
        "comments": (reverse("admin:social_comment_changelist"), [302, 200, 200, 200]),
        "users": (reverse("admin:accounts_user_changelist"), [302, 200, 200, 200]),
        "a user's page": (
            reverse("admin:accounts_user_change", args=[target.pk]),
            [302, 200, 200, 200],
        ),
        "platform settings": (
            reverse("admin:core_platformsettings_change", args=[1]),
            [302, 200, 200, 200],
        ),
        "appeals": (reverse("admin:moderation_appeal_changelist"), [302, 200, 200, 200]),
        "one appeal": (
            reverse("admin:moderation_appeal_change", args=[world["appeal"].pk]),
            [302, 200, 200, 200],
        ),
        "moderation log": (
            reverse("admin:moderation_moderationaction_changelist"),
            [302, 403, 200, 200],
        ),
        "one log row": (
            reverse("admin:moderation_moderationaction_change", args=[world["action"].pk]),
            [302, 403, 200, 200],
        ),
        "admin log": (reverse("admin:admin_logentry_changelist"), [302, 403, 200, 200]),
        "bookmarks": (reverse("admin:social_bookmark_changelist"), [302, 403, 403, 200]),
        "likes": (reverse("admin:social_like_changelist"), [302, 403, 403, 200]),
        "follows": (reverse("admin:social_follow_changelist"), [302, 403, 403, 200]),
        "reposts": (reverse("admin:social_repost_changelist"), [302, 403, 403, 200]),
        # History pages read the admin log, which is seniors-only (review finding 16).
        "post history": (reverse("admin:posts_post_history", args=[post.pk]), [302, 403, 200, 200]),
        "appeal history": (
            reverse("admin:moderation_appeal_history", args=[world["appeal"].pk]),
            [302, 403, 200, 200],
        ),
        "user history": (
            reverse("admin:accounts_user_history", args=[target.pk]),
            [302, 403, 200, 200],
        ),
        "settings history": (
            reverse("admin:core_platformsettings_history", args=[1]),
            [302, 403, 200, 200],
        ),
        "comment history": (
            reverse("admin:social_comment_history", args=[world["comment"].pk]),
            [302, 403, 200, 200],
        ),
    }


@pytest.mark.parametrize("page", PAGE_NAMES)
def test_who_can_open_each_page(client, world, page):
    url, expected = pages(world)[page]
    seen = []
    for kind in ROLES:
        client.logout()
        client.force_login(person(kind))
        seen.append(client.get(url).status_code)
    assert seen == expected, f"{page}: nobody, moderator, senior, superuser"


def test_the_admin_index_lists_only_what_a_person_may_open(client, world):
    client.force_login(person("moderator"))
    body = client.get(reverse("admin:index")).content.decode()
    assert "Posts" in body and "Reports" in body and "Comments" in body and "Appeals" in body
    assert "Moderation actions" not in body and "Log entries" not in body
    assert "Bookmarks" not in body
    client.force_login(person("senior"))
    body = client.get(reverse("admin:index")).content.decode()
    assert "Moderation actions" in body and "Log entries" in body
    assert "Bookmarks" not in body


# ---------- who can change what ----------


def post_form(user, **overrides):
    data = {
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "role": user.role,
        "is_active": "on" if user.is_active else "",
    }
    return {k: v for k, v in {**data, **overrides}.items() if v != ""}


def user_url(user, name="change"):
    if name == "password":
        return reverse("admin:auth_user_password_change", args=[user.pk])
    return reverse(f"admin:accounts_user_{name}", args=[user.pk])


def test_a_moderator_can_look_at_an_account_but_not_change_it(client, world):
    client.force_login(person("moderator"))
    target = world["target"]
    page = client.get(user_url(target))
    assert page.status_code == 200 and b'name="_save"' not in page.content
    assert (
        client.post(user_url(target), post_form(target, role=Role.SENIOR_MODERATOR)).status_code
        == 403
    )
    assert User.objects.get(pk=target.pk).role == Role.MODERATOR


def test_a_senior_changes_the_role_and_suspends_with_nothing_else_moving(client, world):
    client.force_login(person("senior"))
    target = world["target"]
    response = client.post(
        user_url(target),
        post_form(
            target,
            role=Role.USER,
            is_active="",
            email="hijacked@example.test",
            username="hijacked_name",
            bio="rewritten",
        ),
    )
    assert response.status_code == 302
    after = User.objects.get(pk=target.pk)
    assert (after.role, after.is_active, after.is_staff) == (Role.USER, False, False)
    # Everything else is read-only for a senior: the posted values were ignored.
    assert (after.email, after.username, after.bio) == (target.email, target.username, target.bio)


def test_a_senior_can_promote_to_senior_but_the_form_cannot_make_a_superuser(client, world):
    client.force_login(person("senior"))
    target = world["target"]
    client.post(user_url(target), post_form(target, role=Role.SENIOR_MODERATOR, is_superuser="on"))
    after = User.objects.get(pk=target.pk)
    assert after.role == Role.SENIOR_MODERATOR
    assert after.is_superuser is False


def test_a_senior_never_sees_the_password_hash_or_the_password_page(client, world):
    client.force_login(person("senior"))
    target = world["target"]
    body = client.get(user_url(target)).content.decode()
    assert "pbkdf2" not in body and "md5" not in body and "algorithm" not in body
    assert "id_password" not in body and "password/" not in body
    assert client.get(user_url(target, "password")).status_code == 403
    assert (
        client.post(
            user_url(target, "password"),
            {"password1": "N3w-pass-phrase!", "password2": "N3w-pass-phrase!"},
        ).status_code
        == 403
    )
    assert User.objects.get(pk=target.pk).check_password("correct-horse-battery-staple")


def test_a_superuser_still_has_the_whole_form_and_the_password_page(client, world):
    client.force_login(person("superuser"))
    target = world["target"]
    body = client.get(user_url(target)).content.decode()
    assert "Password" in body and "id_email" in body and "id_username" in body
    assert client.get(user_url(target, "password")).status_code == 200
    response = client.post(user_url(target), post_form(target, bio="a new bio"))
    assert response.status_code == 302
    assert User.objects.get(pk=target.pk).bio == "a new bio"


def test_a_moderator_cannot_use_the_password_page(client, world):
    client.force_login(person("moderator"))
    assert client.get(user_url(world["target"], "password")).status_code == 403


def test_a_senior_cannot_edit_suspend_or_delete_a_superuser(client):
    root = UserFactory(is_superuser=True)
    client.force_login(person("senior"))
    page = client.get(user_url(root))
    assert page.status_code == 200 and b'name="_save"' not in page.content  # view only
    assert client.post(user_url(root), post_form(root, is_active="")).status_code == 403
    assert client.get(user_url(root, "delete")).status_code == 403
    assert client.post(user_url(root, "delete"), {"post": "yes"}).status_code == 403
    root.refresh_from_db()
    assert root.is_active is True


def test_a_senior_cannot_edit_or_delete_themselves(client):
    senior = person("senior")
    client.force_login(senior)
    page = client.get(user_url(senior))
    assert b'name="_save"' not in page.content
    assert client.post(user_url(senior), post_form(senior, role=Role.USER)).status_code == 403
    assert client.post(user_url(senior, "delete"), {"post": "yes"}).status_code == 403
    senior.refresh_from_db()
    assert senior.role == Role.SENIOR_MODERATOR and User.objects.filter(pk=senior.pk).exists()


def test_a_superuser_can_edit_themselves_and_other_superusers(client):
    root = person("superuser")
    other = UserFactory(is_superuser=True)
    client.force_login(root)
    assert client.post(user_url(root), post_form(root, bio="mine")).status_code == 302
    assert client.post(user_url(other), post_form(other, bio="theirs")).status_code == 302


def test_a_moderator_cannot_delete_an_account(client, world):
    client.force_login(person("moderator"))
    target = world["target"]
    assert client.get(user_url(target, "delete")).status_code == 403
    assert client.post(user_url(target, "delete"), {"post": "yes"}).status_code == 403
    assert User.objects.filter(pk=target.pk).exists()


def test_a_senior_deletes_an_account_one_at_a_time_from_its_page(client):
    client.force_login(person("senior"))
    target = UserFactory(role=Role.MODERATOR)
    PostFactory(author=target, content="their post")
    page = client.get(user_url(target, "delete"))
    assert page.status_code == 200
    response = client.post(user_url(target, "delete"), {"post": "yes"})
    assert response.status_code == 302
    assert not User.objects.filter(pk=target.pk).exists()


def test_the_bulk_delete_is_a_superuser_thing(client, world):
    target = world["target"]
    data = {
        "action": "delete_selected",
        "index": "0",
        "_selected_action": [str(target.pk)],
        "post": "yes",
    }
    url = reverse("admin:accounts_user_changelist")
    client.force_login(person("senior"))
    assert b'value="delete_selected"' not in client.get(url).content
    client.post(url, data)
    assert User.objects.filter(pk=target.pk).exists()
    client.force_login(person("superuser"))
    assert b'value="delete_selected"' in client.get(url).content
    client.post(url, data)
    assert not User.objects.filter(pk=target.pk).exists()


def test_who_is_offered_mark_email_verified(client, world):
    url = reverse("admin:accounts_user_changelist")
    for kind, offered in (("moderator", False), ("senior", True), ("superuser", True)):
        client.force_login(person(kind))
        assert (b'value="verify_email"' in client.get(url).content) is offered, kind


# ---------- platform settings ----------


def settings_form(**changes):
    row = PlatformSettings.objects.get(pk=1)
    data = {
        "report_threshold": row.report_threshold,
        "report_window_hours": row.report_window_hours,
        "report_min_account_age_hours": row.report_min_account_age_hours,
        "confidence_threshold": row.confidence_threshold,
        "fact_posts_per_day": row.fact_posts_per_day,
        "emergency_duration_hours": row.emergency_duration_hours,
        "emergency_posts_per_day": row.emergency_posts_per_day,
        "emergency_min_account_age_days": row.emergency_min_account_age_days,
        "emergency_min_reputation": row.emergency_min_reputation,
        "emergency_report_threshold": row.emergency_report_threshold,
        "emergency_false_cooldown_days": row.emergency_false_cooldown_days,
    }
    return {**data, **changes}


SETTINGS_URL = "admin:core_platformsettings_change"


def test_a_moderator_reads_the_settings_but_cannot_change_them(client):
    client.force_login(person("moderator"))
    url = reverse(SETTINGS_URL, args=[1])
    page = client.get(url)
    assert page.status_code == 200 and b'name="_save"' not in page.content
    before = PlatformSettings.objects.get(pk=1).report_threshold
    assert client.post(url, settings_form(report_threshold=before + 1)).status_code == 403
    assert PlatformSettings.objects.get(pk=1).report_threshold == before


@pytest.mark.parametrize("kind", ["senior", "superuser"])
def test_seniors_and_superusers_edit_the_settings_and_it_is_attributed(client, kind):
    editor = person(kind)
    client.force_login(editor)
    before = PlatformSettings.objects.get(pk=1)
    response = client.post(
        reverse(SETTINGS_URL, args=[1]),
        settings_form(report_threshold=before.report_threshold + 1),
    )
    assert response.status_code == 302
    after = PlatformSettings.objects.get(pk=1)
    assert after.report_threshold == before.report_threshold + 1
    assert after.updated_by == editor


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("emergency_duration_hours", 12),
        ("emergency_posts_per_day", 1),
        ("emergency_min_account_age_days", 3),
        ("emergency_min_reputation", 55),
        ("emergency_report_threshold", 3),
        ("emergency_false_cooldown_days", 9),
    ],
)
def test_a_senior_can_edit_each_of_the_six_emergency_limits(client, field, value):
    client.force_login(person("senior"))
    assert (
        client.post(reverse(SETTINGS_URL, args=[1]), settings_form(**{field: value})).status_code
        == 302
    )
    assert getattr(PlatformSettings.objects.get(pk=1), field) == value


def test_the_settings_page_has_no_add_or_delete_for_anyone(client):
    for kind in ("moderator", "senior", "superuser"):
        client.force_login(person(kind))
        assert client.get(reverse("admin:core_platformsettings_add")).status_code == 403
        assert (
            client.get(reverse("admin:core_platformsettings_delete", args=[1])).status_code == 403
        )


def test_a_senior_may_add_the_settings_only_when_the_row_is_gone(client):
    client.force_login(person("superuser"))
    assert client.get(reverse("admin:core_platformsettings_add")).status_code == 403  # a row exists
    PlatformSettings.objects.all().delete()
    assert client.get(reverse("admin:core_platformsettings_add")).status_code == 200
    client.force_login(person("moderator"))
    assert client.get(reverse("admin:core_platformsettings_add")).status_code == 403
    client.force_login(person("senior"))
    assert client.get(reverse("admin:core_platformsettings_add")).status_code == 403  # no add_ perm


# ---------- comments and the posts' actions ----------


def test_moderators_hide_comments_and_seniors_too(client, world):
    comment = world["comment"]
    url = reverse("admin:social_comment_changelist")
    for kind in ("moderator", "senior"):
        client.force_login(person(kind))
        body = client.get(url).content
        assert b'value="hide_comments"' in body and b'value="unhide_comments"' in body
    client.force_login(person("moderator"))
    client.post(url, {"action": "hide_comments", "_selected_action": [str(comment.pk)]})
    comment.refresh_from_db()
    assert comment.is_hidden is True


def test_only_those_with_posts_change_permission_are_offered_the_five_actions(client, world):
    url = reverse("admin:posts_post_changelist")
    for kind, offered in (("moderator", True), ("senior", True), ("superuser", True)):
        client.force_login(person(kind))
        body = client.get(url).content
        assert (b'value="escalate"' in body) is offered, kind


def test_the_post_page_is_view_only_for_every_role(client, world):
    url = reverse("admin:posts_post_change", args=[world["post"].pk])
    for kind in ("moderator", "senior", "superuser"):
        client.force_login(person(kind))
        assert b'name="_save"' not in client.get(url).content
        assert client.post(url, {"content": "edited"}).status_code == 403
    world["post"].refresh_from_db()
    assert world["post"].content == "a post"


def test_the_history_link_is_hidden_from_those_who_cannot_open_it(client, world):
    url = reverse("admin:accounts_user_change", args=[world["target"].pk])
    client.force_login(person("moderator"))
    assert b"historylink" not in client.get(url).content
    client.force_login(person("senior"))
    assert b"historylink" in client.get(url).content
