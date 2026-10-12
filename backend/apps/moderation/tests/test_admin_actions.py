"""The five actions through the admin client: the confirmation page, the apply step, the messages,
the audit rows, and the guards (the batch cap, own posts, opinions, `select_across`)."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.moderation.admin import BATCH_CAP
from apps.moderation.models import ActionKind, ModerationAction
from apps.moderation.tests.factories import moderator_user
from apps.posts.models import FlaggedReason, Post, PostStatus, PostType
from apps.posts.tests.factories import PostFactory
from apps.reports.models import ReportStatus
from apps.reports.tests.factories import ReportFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("role_groups")]

LIST = reverse("admin:posts_post_changelist")


@pytest.fixture
def mod(client):
    user = moderator_user()
    client.force_login(user)
    return user


def reviewed(content="a reported claim", *, post_type=PostType.FACT, **fields):
    fields.setdefault("flagged_reason", FlaggedReason.REPORTS)
    fields.setdefault(
        "pre_review_status",
        PostStatus.PENDING if post_type == PostType.FACT else PostStatus.PUBLISHED,
    )
    return PostFactory(
        content=content,
        post_type=post_type,
        status=PostStatus.UNDER_REVIEW,
        review_started_at=timezone.now() - timedelta(hours=2),
        **fields,
    )


def first_post(client, name, *posts, query="", **extra):
    """What the changelist's action form sends when the moderator ticks rows and presses Go."""
    return client.post(
        LIST + query,
        {
            "action": name,
            "index": "0",
            "select_across": "0",
            "_selected_action": [str(p.pk) for p in posts],
            **extra,
        },
    )


def confirm(client, name, *posts, query="", **fields):
    """What the confirmation page's form sends."""
    return client.post(
        LIST + query,
        {"action": name, "apply": "1", "_selected_action": [str(p.pk) for p in posts], **fields},
    )


def texts(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def reload(post):
    return Post.objects.get(pk=post.pk)


ACTIONS = [
    ("mark_verified", PostStatus.VERIFIED_TRUE, ActionKind.VERIFIED, "Marked 1 post verified."),
    ("mark_false", PostStatus.VERIFIED_FALSE, ActionKind.MARKED_FALSE, "Marked 1 post FALSE."),
    ("dismiss_reports", PostStatus.PENDING, ActionKind.DISMISSED_REPORT, "Dismissed the reports"),
    ("remove_posts", PostStatus.REMOVED, ActionKind.REMOVED, "Removed 1 post."),
    ("escalate", PostStatus.UNDER_REVIEW, ActionKind.ESCALATED, "Escalated 1 post"),
]


# ---------- the confirmation page ----------


def test_the_first_post_shows_what_would_change_and_what_would_be_skipped_and_changes_nothing(
    client, mod
):
    fact = reviewed("a fact to label")
    opinion = reviewed("an opinion to skip", post_type=PostType.OPINION)
    response = first_post(client, "mark_verified", fact, opinion)
    assert response.status_code == 200
    body = response.content.decode()
    assert "1 post will change" in body and "1 will be skipped" in body
    assert "a fact to label" in body and "an opinion to skip" in body
    assert "opinion: no verdict" in body  # the reason it is skipped
    assert "Under review" in body and "Verified true" in body  # status → new status
    assert reload(fact).status == PostStatus.UNDER_REVIEW
    assert ModerationAction.objects.count() == 0
    assert 'name="apply" value="1"' in body


def test_the_form_asks_for_a_public_note_for_a_verdict_and_a_reason_for_a_removal(client, mod):
    fact = reviewed()
    verdict = first_post(client, "mark_false", fact).content.decode()
    assert "Public note" in verdict and "Internal notes" in verdict
    removal = first_post(client, "remove_posts", fact).content.decode()
    assert "Reason shown to the author" in removal
    dismissal = first_post(client, "dismiss_reports", fact).content.decode()
    assert "Internal notes" in dismissal
    assert "public_note" not in dismissal


def test_the_confirmation_posts_the_evaluated_ids_and_never_select_across(client, mod):
    fact = reviewed()
    response = first_post(client, "escalate", fact, select_across="1")
    body = response.content.decode()
    assert f'name="_selected_action" value="{fact.pk}"' in body
    assert "select_across" not in body


def test_the_confirmation_form_goes_back_to_the_same_url_with_its_filters(client, mod):
    fact = reviewed()
    response = first_post(client, "escalate", fact, query="?queue=all&post_type__exact=fact")
    assert (
        'action="/admin/posts/post/?queue=all&amp;post_type__exact=fact"'
        in response.content.decode()
    )


def test_nothing_that_can_change_shows_the_skipped_list_and_a_way_back_but_no_form(client, mod):
    opinion = reviewed(post_type=PostType.OPINION)
    body = first_post(client, "mark_false", opinion).content.decode()
    assert "None of the selected posts" in body
    assert 'name="apply"' not in body and "Back" in body


# ---------- applying ----------


@pytest.mark.parametrize(("name", "status", "kind", "message"), ACTIONS)
def test_each_action_changes_the_post_writes_one_row_and_says_so(
    client, mod, name, status, kind, message
):
    post = reviewed()
    ReportFactory(post=post)
    response = confirm(client, name, post, query="?queue=all", notes="my reasons")
    assert response.status_code == 302 and response.url == LIST + "?queue=all"
    assert reload(post).status == status
    row = ModerationAction.objects.get()
    assert (row.action, row.post, row.moderator, row.notes) == (kind, post, mod, "my reasons")
    assert any(message in text for text in texts(response))


def test_a_verdict_stores_its_public_note_on_the_post_and_the_row(client, mod):
    post = reviewed()
    confirm(client, "mark_verified", post, public_note="  Two filings agree.  ", notes="")
    assert reload(post).verdict_note == "Two filings agree."
    assert ModerationAction.objects.get().public_note == "Two filings agree."


def test_a_removal_stores_its_reason_on_the_row_and_leaves_the_verdict_note_alone(client, mod):
    post = reviewed(verdict_note="An older public note")
    confirm(client, "remove_posts", post, public_note="Harassment of a private person")
    assert reload(post).verdict_note == "An older public note"
    assert ModerationAction.objects.get().public_note == "Harassment of a private person"


def test_a_note_longer_than_500_characters_shows_the_form_again_and_changes_nothing(client, mod):
    post = reviewed()
    response = confirm(client, "mark_verified", post, public_note="n" * 501)
    assert response.status_code == 200
    assert "at most 500" in response.content.decode()
    assert reload(post).status == PostStatus.UNDER_REVIEW
    assert ModerationAction.objects.count() == 0
    ok = confirm(client, "mark_verified", post, public_note="n" * 500)
    assert ok.status_code == 302


def test_internal_notes_are_limited_to_2000_characters(client, mod):
    post = reviewed()
    assert confirm(client, "escalate", post, notes="n" * 2001).status_code == 200
    assert confirm(client, "escalate", post, notes="n" * 2000).status_code == 302


def test_a_mixed_selection_changes_what_it_can_and_names_what_it_skipped(client, mod):
    fact = reviewed("fact one")
    other = reviewed("fact two")
    opinion = reviewed("an opinion", post_type=PostType.OPINION)
    published = PostFactory(fact=True, status=PostStatus.PENDING)
    response = confirm(client, "mark_false", fact, other, opinion, published)
    assert reload(fact).status == reload(other).status == PostStatus.VERIFIED_FALSE
    assert reload(opinion).status == PostStatus.UNDER_REVIEW
    assert ModerationAction.objects.count() == 2
    messages_ = texts(response)
    assert "Marked 2 posts FALSE." in messages_
    skipped = next(m for m in messages_ if m.startswith("Skipped"))
    assert skipped.startswith("Skipped 2:")
    assert "1 opinion: no verdict" in skipped and "1 not under review" in skipped


def test_a_post_deleted_between_the_preview_and_the_confirmation_is_skipped(client, mod):
    keep, gone = reviewed("keep"), reviewed("gone")
    Post.objects.filter(pk=gone.pk).update(deleted_at=timezone.now())
    response = confirm(client, "escalate", keep, gone)
    assert reload(keep).escalated_at is not None and reload(gone).escalated_at is None
    assert "Skipped 1: 1 deleted by its author." in texts(response)
    assert ModerationAction.objects.count() == 1


def test_dismissing_resolves_the_reports_with_the_moderator_and_the_time(client, mod):
    post = reviewed()
    ReportFactory(post=post)
    confirm(client, "dismiss_reports", post)
    report = post.reports.get()
    assert (report.status, report.resolved_by) == (ReportStatus.DISMISSED, mod)
    assert report.resolved_at is not None


def test_ids_that_are_not_ids_are_ignored_at_the_confirmation(client, mod):
    post = reviewed()
    response = client.post(
        LIST,
        {"action": "escalate", "apply": "1", "_selected_action": [str(post.pk), "not-a-uuid"]},
    )
    assert response.status_code == 302
    assert reload(post).escalated_at is not None
    nothing = client.post(
        LIST, {"action": "escalate", "index": "0", "_selected_action": ["not-a-uuid"]}
    )
    assert nothing.status_code == 302
    assert any("must be selected" in text for text in texts(nothing))


# ---------- the guards ----------


def test_more_than_100_posts_is_an_error_not_a_confirmation_page(client, mod):
    posts = [reviewed(f"post {i}") for i in range(BATCH_CAP + 1)]
    response = first_post(client, "escalate", *posts)
    assert response.status_code == 302
    assert any("at most 100" in text for text in texts(response))
    assert ModerationAction.objects.count() == 0
    # exactly 100 is fine
    assert first_post(client, "escalate", *posts[:100]).status_code == 200


def test_select_across_over_the_cap_is_refused_too(client, mod):
    for i in range(BATCH_CAP + 1):
        reviewed(f"post {i}")
    response = client.post(
        LIST,
        {"action": "escalate", "index": "0", "select_across": "1", "_selected_action": ["x"]},
    )
    assert response.status_code == 302
    assert any("at most 100" in text for text in texts(response))
    assert ModerationAction.objects.count() == 0


def test_select_across_at_the_confirmation_acts_only_on_the_posts_that_were_shown(client, mod):
    shown = reviewed("shown on the page")
    first_post(client, "escalate", shown, select_across="1")  # the preview (nothing else queued)
    late = reviewed("entered the queue meanwhile")
    # A hand-made confirmation that still says select_across: Django would run the whole queue.
    response = client.post(
        LIST,
        {
            "action": "escalate",
            "apply": "1",
            "select_across": "1",
            "index": "0",
            "_selected_action": [str(shown.pk)],
        },
    )
    assert response.status_code == 302
    assert reload(shown).escalated_at is not None
    assert reload(late).escalated_at is None
    assert ModerationAction.objects.count() == 1


def test_remove_on_a_post_outside_the_queue_needs_the_full_list(client, mod):
    verified = PostFactory(verified_pipeline=True, content="a verified claim")
    # Posted to the default (queue-only) list nothing is selected: the post isn't in it.
    nothing = first_post(client, "remove_posts", verified)
    assert nothing.status_code == 302 and any("No posts" in text for text in texts(nothing))
    everything = first_post(client, "remove_posts", verified, query="?queue=all")
    assert everything.status_code == 200 and "a verified claim" in everything.content.decode()
    done = confirm(client, "remove_posts", verified, query="?queue=all")
    assert done.status_code == 302
    after = reload(verified)
    assert (after.status, after.pre_removal_status) == (
        PostStatus.REMOVED,
        PostStatus.VERIFIED_TRUE,
    )


def test_nobody_acts_on_their_own_post_but_a_superuser_may(client, mod):
    mine = reviewed("my own post", author=mod)
    page = first_post(client, "escalate", mine).content.decode()
    assert "your own post" in page and "None of the selected posts" in page
    response = confirm(client, "escalate", mine)
    assert "Skipped 1: 1 your own post." in texts(response)
    assert reload(mine).escalated_at is None
    root = UserFactory(is_superuser=True)
    client.force_login(root)
    theirs = reviewed("the root's own post", author=root)
    confirm(client, "escalate", theirs)
    assert reload(theirs).escalated_at is not None


def test_a_deleted_post_in_the_full_list_is_skipped(client, mod):
    deleted = reviewed("withdrawn by the author", deleted_at=timezone.now())
    body = first_post(client, "remove_posts", deleted, query="?queue=all").content.decode()
    assert "deleted by its author" in body and "None of the selected posts" in body


# ---------- opinions ----------


def test_an_opinions_page_offers_no_verdict_but_the_other_actions(client, mod):
    opinion = reviewed("opinion page", post_type=PostType.OPINION)
    body = client.get(reverse("admin:posts_post_change", args=[opinion.pk])).content.decode()
    assert 'value="mark_verified"' not in body and 'value="mark_false"' not in body
    for name in ("dismiss_reports", "remove_posts", "escalate"):
        assert f'value="{name}"' in body


def test_a_facts_page_offers_the_verdicts(client, mod):
    fact = reviewed("fact page")
    body = client.get(reverse("admin:posts_post_change", args=[fact.pk])).content.decode()
    for name in ("mark_verified", "mark_false", "dismiss_reports", "remove_posts", "escalate"):
        assert f'value="{name}"' in body


def test_a_list_filtered_to_opinions_drops_the_two_verdict_actions(client, mod):
    reviewed("one", post_type=PostType.OPINION)
    everything = client.get(LIST).content.decode()
    assert 'value="mark_verified"' in everything and 'value="mark_false"' in everything
    only_opinions = client.get(LIST, {"post_type__exact": "opinion"}).content.decode()
    assert 'value="mark_verified"' not in only_opinions
    assert 'value="mark_false"' not in only_opinions
    assert 'value="dismiss_reports"' in only_opinions and 'value="escalate"' in only_opinions


def test_the_dropdown_names_and_has_no_delete_action(client, mod):
    reviewed()
    body = client.get(LIST).content.decode()
    for label in (
        "Mark verified (facts only)",
        "Mark FALSE (facts only)",
        "Dismiss reports",
        "Remove posts",
        "Escalate to senior",
    ):
        assert label in body
    assert 'value="delete_selected"' not in body


# ---------- the buttons on a post's page ----------


def test_the_buttons_sit_outside_the_pages_own_form(client, mod):
    post = reviewed()
    body = client.get(reverse("admin:posts_post_change", args=[post.pk])).content.decode()
    assert body.index('class="moderation-action"') < body.index('id="post_form"')
    assert body.count('class="moderation-action"') == 5
    assert "/admin/posts/post/?queue=all" in body  # an action's queryset is the filtered list


def test_only_the_buttons_that_apply_to_this_post_are_offered(client, mod):
    removed = PostFactory(removed=True)
    published = PostFactory()
    escalated = reviewed("already escalated", escalated_at=timezone.now())
    assert (
        'class="moderation-action"'
        not in client.get(reverse("admin:posts_post_change", args=[removed.pk])).content.decode()
    )
    assert (
        'value="remove_posts"'
        in client.get(reverse("admin:posts_post_change", args=[published.pk])).content.decode()
    )
    page = client.get(reverse("admin:posts_post_change", args=[escalated.pk])).content.decode()
    assert 'value="escalate"' not in page and 'value="dismiss_reports"' in page


def test_a_button_confirms_and_then_returns_to_the_post_page(client, mod):
    post = reviewed()
    page = first_post(client, "escalate", post, query="?queue=all", _from_post="1")
    assert page.status_code == 200
    body = page.content.decode()
    assert 'name="_from_post" value="1"' in body
    assert f'href="{reverse("admin:posts_post_change", args=[post.pk])}"' in body  # cancel
    done = confirm(client, "escalate", post, query="?queue=all", _from_post="1")
    assert done.status_code == 302
    assert done.url == reverse("admin:posts_post_change", args=[post.pk])
    assert reload(post).escalated_at is not None


# ---------- who may act ----------


def test_staff_without_the_change_permission_get_no_actions_and_no_buttons(client):
    staff = UserFactory(role=Role.MODERATOR)
    staff.groups.clear()
    staff.user_permissions.set(Permission.objects.filter(codename="view_post"))
    client.force_login(staff)
    post = reviewed()
    page = client.get(LIST).content.decode()
    assert 'name="action"' not in page
    assert (
        'class="moderation-action"'
        not in client.get(reverse("admin:posts_post_change", args=[post.pk])).content.decode()
    )
    response = first_post(client, "escalate", post)
    assert reload(post).escalated_at is None
    assert ModerationAction.objects.count() == 0
    assert response.status_code in (200, 302)


def test_an_ordinary_user_cannot_reach_the_list_or_act(client):
    client.force_login(UserFactory())
    post = reviewed()
    assert client.get(LIST).status_code == 302
    assert first_post(client, "escalate", post).status_code == 302
    assert reload(post).escalated_at is None
