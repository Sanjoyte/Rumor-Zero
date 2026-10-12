"""The review queue (`PostAdmin`): what the list shows and in what order, the post page and its
inlines, and that the whole thing is read-only (ARCHITECTURE §8)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib import admin
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.moderation.models import ActionKind
from apps.moderation.tests.factories import ModerationActionFactory, moderator_user, senior_user
from apps.posts.models import FlaggedReason, Post, PostStatus
from apps.posts.tests.factories import PostFactory
from apps.reports.models import ReportReason
from apps.reports.tests.factories import ReportFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("role_groups")]

LIST = "admin:posts_post_changelist"


@pytest.fixture
def mod(client):
    user = moderator_user()
    client.force_login(user)
    return user


def reviewed(content, *, reports=0, started_hours_ago=1, **fields):
    fields.setdefault("flagged_reason", FlaggedReason.REPORTS)
    fields.setdefault("pre_review_status", PostStatus.PUBLISHED)
    return PostFactory(
        content=content,
        status=PostStatus.UNDER_REVIEW,
        review_started_at=timezone.now() - timedelta(hours=started_hours_ago),
        report_count=reports,
        **fields,
    )


def position(page, text):
    return page.content.decode().index(text)


def test_post_is_registered_with_the_queue_admin():
    assert Post in admin.site._registry
    assert type(admin.site._registry[Post]).__module__ == "apps.moderation.admin"


def test_the_default_view_is_the_review_queue_without_deleted_posts(client, mod):
    reviewed("in the queue")
    PostFactory(content="published and fine")
    PostFactory(content="already removed", removed=True)
    reviewed("deleted by its author", deleted_at=timezone.now())
    page = client.get(reverse(LIST))
    assert page.status_code == 200
    body = page.content.decode()
    assert "in the queue" in body
    assert "published and fine" not in body
    assert "already removed" not in body
    assert "deleted by its author" not in body


def test_all_posts_shows_everything_and_choosing_a_status_leaves_the_queue(client, mod):
    reviewed("in the queue")
    PostFactory(content="published and fine")
    removed = PostFactory(content="already removed", removed=True)
    everything = client.get(reverse(LIST), {"queue": "all"}).content.decode()
    assert "in the queue" in everything and "published and fine" in everything
    # "Status: removed" is a look at other posts, so it is not intersected with the queue.
    removed_only = client.get(reverse(LIST), {"status__exact": "removed"}).content.decode()
    assert "already removed" in removed_only and "in the queue" not in removed_only
    assert str(removed.pk) in removed_only
    deleted = PostFactory(content="the author deleted it", deleted=True)
    page = client.get(reverse(LIST), {"deleted_at__isempty": "0"}).content.decode()
    assert str(deleted.pk) in page and "in the queue" not in page


def test_the_show_filter_labels_its_choices(client, mod):
    page = client.get(reverse(LIST)).content.decode()
    assert "Review queue" in page and "All posts" in page


def test_the_columns_show_what_a_moderator_decides_on(client, mod):
    post = reviewed(
        "A claim that was reported",
        reports=7,
        started_hours_ago=30,
        post_type="fact",
        pipeline_verdict="false",
        confidence_score=Decimal("92.00"),
        flagged_reason=FlaggedReason.BOTH,
        pre_review_status=PostStatus.PENDING,
        escalated_at=timezone.now(),
    )
    page = client.get(reverse(LIST))
    body = page.content.decode()
    assert "A claim that was reported" in body
    assert "FALSE 92%" in body
    assert "Both" in body  # the reason
    assert "1\xa0day" in body  # waiting: timesince uses a no-break space
    assert ">7<" in body  # reports
    assert "icon-yes" in body  # escalated
    assert post.author.username in body


@pytest.mark.parametrize(
    ("verdict", "confidence", "expected"),
    [
        ("true", Decimal("95.00"), "TRUE 95%"),
        ("false", Decimal("87.50"), "FALSE 87.5%"),
        ("inconclusive", Decimal("40.00"), "Inconclusive 40%"),
        (None, None, "—"),
    ],
)
def test_the_pipeline_column(client, mod, verdict, confidence, expected):
    reviewed("verdict column", pipeline_verdict=verdict, confidence_score=confidence)
    assert expected in client.get(reverse(LIST)).content.decode()


def test_the_emergency_column_says_active_ended_or_nothing(client, mod):
    now = timezone.now()
    reviewed(
        "emergency one",
        post_type="fact",
        is_emergency=True,
        emergency_expires_at=now + timedelta(hours=5),
    )
    reviewed(
        "emergency two",
        post_type="fact",
        is_emergency=True,
        emergency_expires_at=now - timedelta(hours=5),
    )
    reviewed("ordinary")
    body = client.get(reverse(LIST)).content.decode()

    def row(text):
        start = body.index(text)
        return body[body.rindex("<tr", 0, start) : body.index("</tr>", start)]

    assert "Active" in row("emergency one") and "Ended" not in row("emergency one")
    assert "Ended" in row("emergency two") and "Active" not in row("emergency two")
    assert "Active" not in row("ordinary") and "Ended" not in row("ordinary")


def test_the_default_order_is_most_reported_then_longest_waiting_then_newest(client, mod):
    reviewed("zz fewer reports old wait", reports=1, started_hours_ago=50)
    reviewed("zz most reports", reports=9, started_hours_ago=1)
    reviewed("zz tie older wait", reports=3, started_hours_ago=20)
    reviewed("zz tie newer wait", reports=3, started_hours_ago=2)
    page = client.get(reverse(LIST))
    order = [
        "zz most reports",
        "zz tie older wait",
        "zz tie newer wait",
        "zz fewer reports old wait",
    ]
    positions = [position(page, text) for text in order]
    assert positions == sorted(positions)


def test_the_columns_that_the_task_names_are_sortable(client, mod):
    reviewed("aa low", reports=1, started_hours_ago=1)
    reviewed("bb high", reports=8, started_hours_ago=9)
    url = reverse(LIST)
    # The changelist's `o` parameter counts the columns from 0, and the checkbox column is 0.
    names = ["action_checkbox", *admin.site._registry[Post].get_list_display(None)]
    columns = {name: i for i, name in enumerate(names)}
    for column in ("report_total", "waiting", "posted"):
        assert client.get(url, {"o": str(columns[column])}).status_code == 200
    by_reports = client.get(url, {"o": str(columns["report_total"])})
    assert position(by_reports, "aa low") < position(by_reports, "bb high")
    by_reports_down = client.get(url, {"o": f"-{columns['report_total']}"})
    assert position(by_reports_down, "bb high") < position(by_reports_down, "aa low")
    by_wait = client.get(
        url, {"o": str(columns["waiting"])}
    )  # the longest wait is the earliest start
    assert position(by_wait, "bb high") < position(by_wait, "aa low")


def test_search_finds_content_and_author_username(client, mod):
    reviewed("the needle sentence", author=UserFactory(username="plain_writer"))
    reviewed("another", author=UserFactory(username="needle_name"))
    reviewed("nothing here")
    by_text = client.get(reverse(LIST), {"q": "needle sentence"}).content.decode()
    assert "the needle sentence" in by_text and "another" not in by_text
    by_author = client.get(reverse(LIST), {"q": "needle_name"}).content.decode()
    assert "another" in by_author and "the needle sentence" not in by_author


def test_the_filters(client, mod):
    reviewed("flag reports", flagged_reason=FlaggedReason.REPORTS)
    reviewed(
        "flag pipeline",
        post_type="fact",
        flagged_reason=FlaggedReason.PIPELINE,
        pre_review_status=PostStatus.PENDING,
    )
    reviewed("was escalated", escalated_at=timezone.now())
    url = reverse(LIST)
    page = client.get(url, {"flagged_reason__exact": "pipeline"}).content.decode()
    assert "flag pipeline" in page and "flag reports" not in page
    page = client.get(url, {"post_type__exact": "opinion"}).content.decode()
    assert "flag reports" in page and "flag pipeline" not in page
    page = client.get(url, {"escalated": "yes"}).content.decode()
    assert "was escalated" in page and "flag reports" not in page
    page = client.get(url, {"escalated": "no"}).content.decode()
    assert "was escalated" not in page and "flag reports" in page


def test_a_moderators_cannot_add_change_or_delete_through_the_admin(client, mod):
    post = reviewed("hands off")
    assert client.get(reverse("admin:posts_post_add")).status_code == 403
    change = reverse("admin:posts_post_change", args=[post.pk])
    assert client.post(change, {"content": "edited"}).status_code == 403
    assert client.get(reverse("admin:posts_post_delete", args=[post.pk])).status_code == 403
    assert (
        client.post(reverse("admin:posts_post_delete", args=[post.pk]), {"post": "yes"}).status_code
        == 403
    )
    assert Post.objects.get(pk=post.pk).content == "hands off"


def test_even_a_superuser_gets_a_view_only_post_page(client):
    root = UserFactory(is_superuser=True)
    client.force_login(root)
    post = reviewed("look but do not touch")
    change = reverse("admin:posts_post_change", args=[post.pk])
    page = client.get(change)
    assert page.status_code == 200
    assert b'name="_save"' not in page.content and b"deletelink" not in page.content
    assert client.post(change, {"content": "edited"}).status_code == 403
    assert Post.objects.get(pk=post.pk).content == "look but do not touch"


def test_the_post_page_groups_its_fields_and_shows_the_pipeline_answer(client, mod):
    post = reviewed(
        "A grouped claim",
        post_type="fact",
        pipeline_verdict="false",
        confidence_score=Decimal("91.00"),
        pipeline_result={"stub": True, "rule": "#false"},
        flagged_reason=FlaggedReason.BOTH,
        pre_review_status=PostStatus.PENDING,
    )
    body = client.get(reverse("admin:posts_post_change", args=[post.pk])).content.decode()
    for heading in ("Post", "Review", "Pipeline", "Emergency"):
        assert f'class="fieldset-heading">{heading}</h2>' in body
    assert "A grouped claim" in body
    assert "91.00" in body
    assert "&quot;rule&quot;" in body or "#false" in body  # the raw answer, escaped


def test_the_post_page_lists_the_reports_with_the_reporters_account_age(client, mod):
    post = reviewed("reported claim")
    reporter = UserFactory(username="the_reporter", created_at=timezone.now() - timedelta(days=3))
    ReportFactory(
        post=post,
        reporter=reporter,
        reason=ReportReason.OTHER,
        details="a private accusation",
        created_at=timezone.now(),
    )
    body = client.get(reverse("admin:posts_post_change", args=[post.pk])).content.decode()
    assert "the_reporter" in body
    assert "a private accusation" in body
    assert "3\xa0days" in body or "3 days" in body
    assert "Other" in body or "Something else" in body


def test_a_moderator_sees_the_posts_history_without_the_full_log(client, mod):
    post = reviewed("with a history")
    boss = senior_user(username="the_boss")
    ModerationActionFactory(
        post=post,
        moderator=boss,
        action=ActionKind.ESCALATED,
        from_status="under_review",
        to_status="under_review",
        notes="needs a senior eye",
        public_note="",
    )
    body = client.get(reverse("admin:posts_post_change", args=[post.pk])).content.decode()
    assert "Moderation history" in body
    assert "the_boss" in body and "needs a senior eye" in body
    assert "Escalated" in body
    # ...but the full log is still seniors-only.
    assert client.get(reverse("admin:moderation_moderationaction_changelist")).status_code == 403


def test_the_queue_page_uses_the_same_number_of_queries_for_100_posts_as_for_5(client, mod):
    for index in range(5):
        reviewed(f"five {index}", reports=index)
    url = reverse(LIST)
    client.get(url)  # warm the content-type and permission caches
    with CaptureQueriesContext(connection) as small:
        assert client.get(url).status_code == 200
    for index in range(95):
        reviewed(f"hundred {index}", reports=index % 7, post_type="fact")
    with CaptureQueriesContext(connection) as large:
        page = client.get(url)
    assert page.content.decode().count('name="_selected_action"') == 100
    assert len(large) == len(small)


def test_the_post_page_uses_the_same_number_of_queries_with_50_reports_and_10_history_rows(
    client, mod
):
    quiet = reviewed("quiet")
    ReportFactory(post=quiet)
    ModerationActionFactory(post=quiet)
    busy = reviewed("busy", reports=50)
    for _ in range(50):
        ReportFactory(post=busy)
    for _ in range(10):
        ModerationActionFactory(post=busy)
    client.get(reverse("admin:posts_post_change", args=[quiet.pk]))  # warm caches
    with CaptureQueriesContext(connection) as small:
        client.get(reverse("admin:posts_post_change", args=[quiet.pk]))
    with CaptureQueriesContext(connection) as large:
        page = client.get(reverse("admin:posts_post_change", args=[busy.pk]))
    assert page.status_code == 200
    assert len(large) == len(small)
