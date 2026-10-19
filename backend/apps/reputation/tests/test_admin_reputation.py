"""The credibility ledger in Django Admin (ARCHITECTURE §8): the read-only list for moderators and
up, the inline on a post's page, and the Credibility field on an account's page."""

import pytest
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.moderation import services as moderation
from apps.reputation.models import EventKind as K
from apps.reputation.models import ReputationEvent
from apps.reputation.tests.factories import (
    FALSE_95,
    TRUE_95,
    EventFactory,
    PostFactory,
    UserFactory,
    VerifiedUserFactory,
    label_by_pipeline,
    moderator_user,
    pending_fact,
    reposted,
    senior_user,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("role_groups")]

LIST = "admin:reputation_reputationevent_changelist"


@pytest.fixture
def mod(client):
    user = moderator_user()
    client.force_login(user)
    return user


def body(response):
    assert response.status_code == 200
    return response.content.decode()


def a_relabel():
    """An author whose FALSE was overturned, and a reposter, written by the services."""
    author = VerifiedUserFactory(username="ada")
    post = pending_fact(author, content="The bridge opens on Monday")
    fan = reposted(post, VerifiedUserFactory(username="fan"))
    label_by_pipeline(post, FALSE_95)
    moderation.file_appeal(author=author, post_id=post.pk)
    moderation.mark_verified(post.pk, moderator=moderator_user())
    return author, fan, post


# ---------- the list ----------


def test_a_moderator_reads_the_whole_ledger(client, mod):
    author, fan, post = a_relabel()
    page = body(client.get(reverse(LIST)))
    assert page.count('class="field-kind"') == ReputationEvent.objects.count() == 6
    for text in (
        "Fact labelled FALSE",
        "Reversal",
        "Fact verified true",
        "Repost of a fact labelled FALSE",
        "N +1",
        "N −1",
        "P +0.25",
        "The bridge opens on Monday",
        reverse("admin:posts_post_change", args=[post.pk]),
    ):
        assert text in page


def test_a_senior_and_a_superuser_read_it_too(client):
    a_relabel()
    for user in (senior_user(), UserFactory(is_superuser=True)):
        client.force_login(user)
        assert client.get(reverse(LIST)).status_code == 200


def test_an_ordinary_user_is_sent_to_the_login_and_staff_without_the_permission_gets_403(client):
    client.force_login(VerifiedUserFactory())
    assert client.get(reverse(LIST)).status_code == 302
    staff = VerifiedUserFactory(role="moderator")
    staff.groups.clear()
    staff.user_permissions.add(Permission.objects.get(codename="view_post"))
    client.force_login(staff)
    assert client.get(reverse(LIST)).status_code == 403


def test_the_list_filters_by_kind_and_searches_by_username(client, mod):
    a_relabel()
    EventFactory(user=VerifiedUserFactory(username="bob"), kind=K.REPORT_UPHELD)
    by_kind = body(client.get(reverse(LIST), {"kind__exact": "reversal"}))
    assert by_kind.count('class="field-kind"') == 2
    by_name = body(client.get(reverse(LIST), {"q": "bob"}))
    assert by_name.count('class="field-kind"') == 1
    assert "Report upheld by a moderator" in by_name


def test_the_user_filter_the_account_page_links_to(client, mod):
    author, fan, _ = a_relabel()
    page = body(client.get(reverse(LIST), {"user__id__exact": str(fan.pk)}))
    assert page.count('class="field-kind"') == 3  # repost FALSE, its reversal, repost TRUE


def test_the_list_shows_which_rows_were_reversed(client, mod):
    a_relabel()
    page = body(client.get(reverse(LIST), {"kind__exact": "fact_false"}))
    assert 'alt="True"' in page  # the "Reversed" column's icon


def test_nothing_can_be_added_changed_or_deleted(client):
    client.force_login(UserFactory(is_superuser=True))
    row = EventFactory()
    assert client.get(reverse("admin:reputation_reputationevent_add")).status_code == 403
    change = reverse("admin:reputation_reputationevent_change", args=[row.pk])
    page = body(client.get(change))
    assert 'name="_save"' not in page
    assert client.post(change, {"score_after": 1}).status_code == 403
    delete = reverse("admin:reputation_reputationevent_delete", args=[row.pk])
    assert client.post(delete, {"post": "yes"}).status_code == 403
    assert ReputationEvent.objects.get(pk=row.pk).score_after == 55
    changelist = body(client.get(reverse(LIST)))
    assert "delete_selected" not in changelist


def test_a_rows_page_shows_its_action_and_the_row_it_reverses(client, mod):
    a_relabel()
    reversal = ReputationEvent.objects.get(kind=K.REVERSAL, reverses__kind=K.FACT_FALSE)
    page = body(client.get(reverse("admin:reputation_reputationevent_change", args=[reversal.pk])))
    assert "Marked verified" in page  # the moderation action
    assert "Fact labelled FALSE" in page  # the row it reverses


def test_the_list_costs_the_same_number_of_queries_for_5_and_60_rows(client, mod):
    for _ in range(5):
        EventFactory(post=PostFactory())
    client.get(reverse(LIST))  # warm caches
    with CaptureQueriesContext(connection) as small:
        client.get(reverse(LIST))
    for _ in range(55):
        EventFactory(post=PostFactory())
    with CaptureQueriesContext(connection) as large:
        page = body(client.get(reverse(LIST)))
    assert page.count('class="field-kind"') == 60
    assert len(large) == len(small)


# ---------- the inline on a post's page ----------


def test_a_posts_page_lists_its_credibility_events(client, mod):
    _, _, post = a_relabel()
    page = body(client.get(reverse("admin:posts_post_change", args=[post.pk])))
    assert "Credibility events" in page
    assert page.count("<p>Reversal</p>") == 2
    assert page.count("<p>Fact labelled FALSE</p>") == 1
    assert page.count("<p>Fact verified true</p>") == 1
    assert page.count("<p>Repost of a fact labelled FALSE</p>") == 1
    assert page.count("<p>Repost of a fact verified true</p>") == 1
    assert "fan" in page and "ada" in page
    assert "N +0.5" in page


def test_staff_without_the_ledger_permission_doesnt_see_the_inline(client):
    _, _, post = a_relabel()
    staff = VerifiedUserFactory(role="moderator")
    staff.groups.clear()
    staff.user_permissions.add(
        *Permission.objects.filter(codename__in=["view_post", "change_post"])
    )
    client.force_login(staff)
    page = body(client.get(reverse("admin:posts_post_change", args=[post.pk])))
    assert "Credibility events" not in page


# ---------- the account page ----------


def account_page(client, user):
    return body(client.get(reverse("admin:accounts_user_change", args=[user.pk])))


@pytest.mark.parametrize("viewer", [moderator_user, senior_user])
def test_the_account_page_shows_the_score_with_a_link_to_its_rows(client, viewer):
    client.force_login(viewer())
    author = VerifiedUserFactory()
    for _ in range(3):
        label_by_pipeline(pending_fact(author), TRUE_95)
    page = account_page(client, author)
    assert "62 · 3 counted events" in page
    link = f"{reverse(LIST)}?user__id__exact={author.pk}"
    assert f'href="{link}"' in page
    assert client.get(link).status_code == 200


def test_the_account_page_says_new_below_three_events(client, mod):
    author = VerifiedUserFactory()
    label_by_pipeline(pending_fact(author), FALSE_95)
    page = account_page(client, author)
    assert "New (1 counted event, score 45)" in page
    assert "View events" in page


def test_the_account_page_has_no_raw_score_fields_to_edit(client):
    client.force_login(UserFactory(is_superuser=True))
    target = VerifiedUserFactory()
    page = account_page(client, target)
    assert 'name="reputation_score"' not in page
    assert 'name="reputation_sample"' not in page
    assert "New (0 counted events, score 50)" in page
