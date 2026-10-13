"""Appeals in Django Admin (ARCHITECTURE §8): removal appeals in the review queue, the appeal
filter, the Reason and Waiting columns, Restore post and Keep removed through the admin client, the
buttons on a post's page, the appeal inline and `AppealAdmin`."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.moderation import services
from apps.moderation.models import ActionKind, Appeal, AppealStatus, ModerationAction
from apps.moderation.tests.factories import AppealFactory, moderator_user, senior_user
from apps.posts.models import FlaggedReason, Post, PostStatus
from apps.posts.tests.factories import PostFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("role_groups")]

LIST = reverse("admin:posts_post_changelist")
APPEALS = reverse("admin:moderation_appeal_changelist")


@pytest.fixture
def mod(client):
    user = moderator_user()
    client.force_login(user)
    return user


def label_appeal(content="a label appeal", *, hours_ago=3, **fields):
    appeal = AppealFactory(
        post__content=content,
        created_at=timezone.now() - timedelta(hours=hours_ago),
        **fields,
    )
    Post.objects.filter(pk=appeal.post_id).update(
        review_started_at=timezone.now() - timedelta(hours=hours_ago)
    )
    return appeal


def removal_appeal(content="a removal appeal", *, hours_ago=3, **fields):
    return AppealFactory(
        removal=True,
        post__content=content,
        created_at=timezone.now() - timedelta(hours=hours_ago),
        **fields,
    )


def page(client, **query):
    response = client.get(LIST, query)
    assert response.status_code == 200
    return response.content.decode()


def position(text, needle):
    return text.index(needle)


def first_post(client, name, *posts, query=""):
    return client.post(
        LIST + query,
        {
            "action": name,
            "index": "0",
            "select_across": "0",
            "_selected_action": [str(p.pk) for p in posts],
        },
    )


def confirm(client, name, *posts, query="", **fields):
    return client.post(
        LIST + query,
        {"action": name, "apply": "1", "_selected_action": [str(p.pk) for p in posts], **fields},
    )


def texts(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


# ---------- the queue ----------


def test_a_removed_post_with_an_open_appeal_is_in_the_default_queue_next_to_posts_under_review(
    client, mod
):
    label = label_appeal("under review for a label appeal")
    removal = removal_appeal("removed and appealed")
    resolved = removal_appeal(
        "appeal decided",
        status=AppealStatus.UPHELD,
        resolved_at=timezone.now(),
        resolved_by=moderator_user(),
    )
    Post.objects.filter(pk=resolved.post_id).update(flagged_reason=None)
    plain = PostFactory(post_type="fact", status=PostStatus.REMOVED, content="removed, no appeal")
    deleted = removal_appeal("appealed but deleted by its author")
    Post.objects.filter(pk=deleted.post_id).update(deleted_at=timezone.now())
    body = page(client)
    assert label.post.content in body and removal.post.content in body
    for hidden in (resolved.post.content, plain.content, deleted.post.content):
        assert hidden not in body


def test_all_posts_still_shows_everything(client, mod):
    removal = removal_appeal()
    plain = PostFactory(status=PostStatus.REMOVED, content="removed, no appeal")
    body = page(client, queue="all")
    assert removal.post.content in body and plain.content in body


def test_the_appeal_filter_picks_posts_with_an_open_appeal_of_a_kind(client, mod):
    label = label_appeal("label one")
    removal = removal_appeal("removal one")
    other = PostFactory(
        status=PostStatus.UNDER_REVIEW, flagged_reason=FlaggedReason.REPORTS, content="reports only"
    )
    by_label = page(client, appeal="label")
    assert label.post.content in by_label
    assert removal.post.content not in by_label and other.content not in by_label
    by_removal = page(client, appeal="removal")
    assert removal.post.content in by_removal and label.post.content not in by_removal
    # A resolved appeal isn't "open": its post is not picked.
    AppealFactory(
        removal=True,
        post__content="decided removal",
        status=AppealStatus.OVERTURNED,
        resolved_at=timezone.now(),
        resolved_by=moderator_user(),
    )
    assert "decided removal" not in page(client, appeal="removal", queue="all")
    # An unknown value filters nothing out.
    assert label.post.content in page(client, appeal="nonsense")


def test_the_appeal_filter_is_offered_with_its_two_kinds(client, mod):
    body = page(client)
    assert "By appeal" in body
    assert "FALSE label" in body and "Removal" in body


def test_the_reason_column_names_the_kind_of_appeal(client, mod):
    label_appeal("label one")
    removal_appeal("removal one")
    body = page(client)
    assert "Appeal (FALSE label)" in body and "Appeal (removal)" in body


def test_the_reason_column_of_an_ordinary_flag_is_unchanged(client, mod):
    PostFactory(
        status=PostStatus.UNDER_REVIEW,
        flagged_reason=FlaggedReason.REPORTS,
        pre_review_status=PostStatus.PUBLISHED,
        content="just reports",
    )
    assert "Appeal (" not in page(client) and "Reports" in page(client)


def test_a_removed_post_waits_from_its_appeal_not_from_a_clock_it_does_not_have(client, mod):
    removal_appeal("long wait", hours_ago=30)
    body = page(client)
    assert "1\xa0day" in body or "1 day" in body  # timesince(appeal.created_at): 30 hours


def test_the_default_order_puts_the_longest_wait_first_whichever_kind_of_queue_entry(client, mod):
    newest = label_appeal("newest label", hours_ago=1)
    oldest = removal_appeal("oldest removal", hours_ago=20)
    middle = label_appeal("middle label", hours_ago=5)
    body = page(client)
    assert (
        position(body, oldest.post.content)
        < position(body, middle.post.content)
        < position(body, newest.post.content)
    )


def test_sorting_by_waiting_orders_removed_posts_by_their_appeal(client, mod):
    removal_appeal("removal old", hours_ago=40)
    label_appeal("label mid", hours_ago=10)
    removal_appeal("removal new", hours_ago=2)
    # `o` counts the columns from 0 with the checkbox as column 0: claim, kind, status, reason,
    # pipeline, report_total, then waiting.
    column = 7
    ascending = client.get(LIST, {"o": str(column)}).content.decode()
    assert position(ascending, "removal old") < position(ascending, "label mid")
    assert position(ascending, "label mid") < position(ascending, "removal new")
    descending = client.get(LIST, {"o": f"-{column}"}).content.decode()
    assert position(descending, "removal new") < position(descending, "label mid")


def test_the_queue_page_uses_the_same_number_of_queries_with_100_appeals_as_with_5(client, mod):
    for index in range(5):
        (removal_appeal if index % 2 else label_appeal)(f"five {index}")
    client.get(LIST)  # warm the content-type and permission caches
    with CaptureQueriesContext(connection) as small:
        assert client.get(LIST).status_code == 200
    for index in range(95):
        (removal_appeal if index % 2 else label_appeal)(f"hundred {index}")
    with CaptureQueriesContext(connection) as large:
        body = client.get(LIST).content.decode()
    assert body.count('name="_selected_action"') == 100
    assert len(large) == len(small)


# ---------- Restore post and Keep removed ----------


def test_restore_posts_shows_the_new_status_and_applies(client, mod):
    appeal = removal_appeal("restore me")
    post = appeal.post
    preview = first_post(client, "restore_posts", post)
    body = preview.content.decode()
    assert "1 post will change" in body and "Removed" in body and "Verified false" in body
    assert "Internal notes" in body and "public_note" not in body  # internal notes only
    assert Post.objects.get(pk=post.pk).status == PostStatus.REMOVED
    response = confirm(client, "restore_posts", post, notes="fine on rereading")
    assert response.status_code == 302
    assert any("Restored 1 post." in text for text in texts(response))
    after = Post.objects.get(pk=post.pk)
    assert (after.status, after.flagged_reason) == (PostStatus.VERIFIED_FALSE, None)
    resolved = Appeal.objects.get(pk=appeal.pk)
    assert (resolved.status, resolved.resolved_by) == (AppealStatus.OVERTURNED, mod)
    row = ModerationAction.objects.get()
    assert (row.action, row.appeal, row.notes, row.public_note) == (
        ActionKind.RESTORED,
        resolved,
        "fine on rereading",
        "",
    )


def test_a_restore_that_goes_to_review_says_so_on_the_confirmation_page(client, mod):
    appeal = removal_appeal(
        "checked before it was removed",
        post__pre_removal_status=PostStatus.PENDING,
        post__pipeline_checked_at=timezone.now() - timedelta(days=1),
    )
    body = first_post(client, "restore_posts", appeal.post).content.decode()
    assert "Removed" in body and "Under review" in body
    confirm(client, "restore_posts", appeal.post)
    after = Post.objects.get(pk=appeal.post_id)
    assert (after.status, after.flagged_reason) == (PostStatus.UNDER_REVIEW, FlaggedReason.PIPELINE)


def test_keep_removed_closes_the_appeal_and_says_so(client, mod):
    appeal = removal_appeal("keep me removed")
    response = confirm(client, "keep_removed", appeal.post, notes="clear violation")
    assert any("Kept 1 post removed." in text for text in texts(response))
    after = Post.objects.get(pk=appeal.post_id)
    assert (after.status, after.flagged_reason) == (PostStatus.REMOVED, None)
    assert Appeal.objects.get(pk=appeal.pk).status == AppealStatus.UPHELD
    assert ModerationAction.objects.get().action == ActionKind.KEPT_REMOVED


@pytest.mark.parametrize("name", ["restore_posts", "keep_removed"])
def test_a_mixed_selection_changes_what_it_can_and_names_what_it_skipped(client, mod, name):
    good = removal_appeal("good one")
    never_appealed = PostFactory(post_type="fact", status=PostStatus.REMOVED, content="no appeal")
    mine = removal_appeal("my own first decision", original_moderator=mod)
    response = confirm(client, name, good.post, never_appealed, mine.post)
    after = Post.objects.get(pk=good.post_id)
    assert (
        Appeal.objects.get(pk=good.pk).status != AppealStatus.OPEN and after.flagged_reason is None
    )
    assert Appeal.objects.get(pk=mine.pk).status == AppealStatus.OPEN
    skipped = [text for text in texts(response) if text.startswith("Skipped 2")]
    assert skipped and "1 no open removal appeal" in skipped[0]
    assert "1 you made the first decision" in skipped[0]
    assert ModerationAction.objects.count() == 1


def test_the_preview_lists_a_post_you_decided_first_as_skipped_with_the_reason(client, mod):
    mine = removal_appeal("mine", original_moderator=mod)
    body = first_post(client, "restore_posts", mine.post).content.decode()
    assert "you made the first decision" in body
    assert "None of the selected posts" in body


def test_a_senior_moderator_can_decide_an_appeal_the_moderator_started(client):
    first = moderator_user()
    appeal = removal_appeal("senior decides", original_moderator=first)
    boss = senior_user()
    client.force_login(boss)
    confirm(client, "keep_removed", appeal.post)
    assert Appeal.objects.get(pk=appeal.pk).resolved_by == boss


def test_a_label_appeal_is_decided_with_the_ordinary_verdict_actions(client, mod):
    appeal = label_appeal("a label appeal")
    response = confirm(client, "mark_verified", appeal.post, public_note="Rechecked")
    assert any("Marked 1 post verified." in text for text in texts(response))
    resolved = Appeal.objects.get(pk=appeal.pk)
    assert (resolved.status, resolved.resolved_by) == (AppealStatus.OVERTURNED, mod)
    assert ModerationAction.objects.get().appeal == resolved


# ---------- the buttons on a post's page ----------


def buttons(client, post):
    body = client.get(reverse("admin:posts_post_change", args=[post.pk])).content.decode()
    return {
        name
        for name in (
            "mark_verified",
            "mark_false",
            "dismiss_reports",
            "remove_posts",
            "escalate",
            "restore_posts",
            "keep_removed",
        )
        if f'name="action" value="{name}"' in body
    }


def test_a_removal_appeal_offers_restore_keep_removed_and_escalate_only(client, mod):
    appeal = removal_appeal()
    assert buttons(client, appeal.post) == {"restore_posts", "keep_removed", "escalate"}


def test_a_label_appeal_offers_the_verdicts_remove_and_escalate_but_not_restore(client, mod):
    appeal = label_appeal()
    assert buttons(client, appeal.post) == {
        "mark_verified",
        "mark_false",
        "remove_posts",
        "escalate",
    }


def test_a_removed_post_without_an_appeal_offers_nothing(client, mod):
    assert buttons(client, PostFactory(status=PostStatus.REMOVED)) == set()


def test_a_decided_appeal_offers_nothing(client, mod):
    appeal = removal_appeal(
        status=AppealStatus.UPHELD, resolved_at=timezone.now(), resolved_by=moderator_user()
    )
    Post.objects.filter(pk=appeal.post_id).update(flagged_reason=None)
    assert buttons(client, appeal.post) == set()


def test_the_buttons_follow_the_original_moderator_rule(client, mod):
    mine = removal_appeal("mine", original_moderator=mod)
    assert buttons(client, mine.post) == {"escalate"}  # escalating is what they should do
    label_mine = label_appeal("label mine", original_moderator=mod)
    assert buttons(client, label_mine.post) == {"escalate"}


def test_escalate_works_on_a_removal_appeal_through_the_admin(client, mod):
    appeal = removal_appeal()
    response = confirm(client, "escalate", appeal.post, notes="needs a senior")
    assert any("Escalated 1 post" in text for text in texts(response))
    after = Post.objects.get(pk=appeal.post_id)
    assert (after.status, after.escalated_at is not None) == (PostStatus.REMOVED, True)
    assert Appeal.objects.get(pk=appeal.pk).status == AppealStatus.OPEN


# ---------- the inline on a post's page ----------


def post_page(client, post):
    return client.get(reverse("admin:posts_post_change", args=[post.pk])).content.decode()


def test_the_post_page_shows_the_appeal_with_the_authors_words_and_who_decided(client, mod):
    first = moderator_user(username="the_first_mod")
    appeal = removal_appeal(reason="It was a quote from a book", original_moderator=first)
    body = post_page(client, appeal.post)
    assert "Appeals" in body or "Appeal" in body
    assert "It was a quote from a book" in body
    assert "the_first_mod" in body and "Removal" in body and "Open" in body


def test_a_resolved_appeal_shows_its_outcome_and_resolver(client, mod):
    decider = moderator_user(username="the_decider")
    appeal = label_appeal(
        status=AppealStatus.UPHELD, resolved_at=timezone.now(), resolved_by=decider
    )
    body = post_page(client, appeal.post)
    assert "Upheld" in body and "the_decider" in body


def test_a_post_with_no_appeal_has_an_empty_appeal_inline_and_no_error(client, mod):
    post = PostFactory(status=PostStatus.PUBLISHED)
    response = client.get(reverse("admin:posts_post_change", args=[post.pk]))
    assert response.status_code == 200


def test_the_inline_needs_the_view_appeal_permission(client):
    user = moderator_user()
    user.groups.clear()
    user.user_permissions.add(
        *Permission.objects.filter(
            codename__in=["view_post", "change_post"], content_type__app_label="posts"
        )
    )
    client.force_login(user)
    appeal = removal_appeal(reason="secret words")
    assert "secret words" not in post_page(client, appeal.post)


def test_the_post_page_costs_the_same_number_of_queries_with_a_resolved_appeal(client, mod):
    quiet = PostFactory(status=PostStatus.PUBLISHED, content="quiet")
    busy = removal_appeal(
        "busy", status=AppealStatus.UPHELD, resolved_at=timezone.now(), resolved_by=senior_user()
    ).post
    client.get(reverse("admin:posts_post_change", args=[quiet.pk]))  # warm caches
    with CaptureQueriesContext(connection) as small:
        client.get(reverse("admin:posts_post_change", args=[quiet.pk]))
    with CaptureQueriesContext(connection) as large:
        response = client.get(reverse("admin:posts_post_change", args=[busy.pk]))
    assert response.status_code == 200 and len(large) == len(small)


# ---------- AppealAdmin ----------


def test_the_appeal_list_shows_the_columns_but_not_the_authors_words(client, mod):
    appeal = removal_appeal(
        "listed", reason="my private reason", original_moderator=moderator_user(username="orig")
    )
    response = client.get(APPEALS)
    assert response.status_code == 200
    body = response.content.decode()
    assert "listed" in body and appeal.author.username in body and "orig" in body
    assert "Removal" in body and "Open" in body
    assert "my private reason" not in body  # the reason is on an appeal's own page


def test_an_appeals_own_page_shows_the_reason(client, mod):
    appeal = label_appeal(reason="please look again")
    body = client.get(reverse("admin:moderation_appeal_change", args=[appeal.pk])).content.decode()
    assert "please look again" in body
    assert 'name="_save"' not in body  # nothing to save


def test_the_appeal_list_filters_and_searches(client, mod):
    one = label_appeal("one")
    two = removal_appeal("two")
    by_kind = client.get(APPEALS, {"kind__exact": "removal"}).content.decode()
    assert "two" in by_kind and "one</a>" not in by_kind
    by_status = client.get(APPEALS, {"status__exact": "open"}).content.decode()
    assert "one" in by_status and "two" in by_status
    found = client.get(APPEALS, {"q": two.author.username}).content.decode()
    assert "two" in found and one.author.username not in found


def test_the_appeal_list_costs_the_same_number_of_queries_for_5_and_60_appeals(client, mod):
    for index in range(5):
        label_appeal(f"five {index}", original_moderator=moderator_user())
    client.get(APPEALS)
    with CaptureQueriesContext(connection) as small:
        client.get(APPEALS)
    for index in range(55):
        removal_appeal(f"sixty {index}", original_moderator=moderator_user())
    with CaptureQueriesContext(connection) as large:
        assert client.get(APPEALS).status_code == 200
    assert len(large) == len(small)


@pytest.mark.parametrize(
    ("role", "expected"),
    [("nobody", 302), ("moderator", 200), ("senior", 200), ("superuser", 200)],
)
def test_who_can_open_the_appeals(client, role, expected):
    appeal = label_appeal()
    user = {
        "nobody": lambda: UserFactory(),
        "moderator": lambda: UserFactory(role=Role.MODERATOR),
        "senior": lambda: UserFactory(role=Role.SENIOR_MODERATOR),
        "superuser": lambda: UserFactory(is_superuser=True),
    }[role]()
    client.force_login(user)
    assert client.get(APPEALS).status_code == expected
    assert (
        client.get(reverse("admin:moderation_appeal_change", args=[appeal.pk])).status_code
        == expected
    )


def test_nobody_can_add_change_or_delete_an_appeal_not_even_a_superuser(client):
    appeal = label_appeal()
    client.force_login(UserFactory(is_superuser=True))
    change = reverse("admin:moderation_appeal_change", args=[appeal.pk])
    assert client.get(reverse("admin:moderation_appeal_add")).status_code == 403
    assert client.post(change, {"status": "overturned"}).status_code == 403
    assert (
        client.get(reverse("admin:moderation_appeal_delete", args=[appeal.pk])).status_code == 403
    )
    assert Appeal.objects.get(pk=appeal.pk).status == AppealStatus.OPEN


def test_the_appeal_history_page_is_for_seniors_like_every_other_history_page(client):
    appeal = label_appeal()
    url = reverse("admin:moderation_appeal_history", args=[appeal.pk])
    client.force_login(moderator_user())
    assert client.get(url).status_code == 403
    client.force_login(senior_user())
    assert client.get(url).status_code == 200


def test_the_moderation_log_links_the_appeal_a_row_resolved(client):
    appeal = removal_appeal()
    services.keep_removed(appeal.post_id, moderator=senior_user())
    client.force_login(senior_user())
    row = ModerationAction.objects.get(action=ActionKind.KEPT_REMOVED)
    url = reverse("admin:moderation_moderationaction_change", args=[row.pk])
    assert "Removal appeal" in client.get(url).content.decode()
