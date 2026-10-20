"""GET /api/v1/me/export/ (ARCHITECTURE §9; Part 14)."""

import json

import pytest
from allauth.socialaccount.models import SocialAccount
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts import export
from apps.accounts.tests.conftest import access_token_for, walk_strings
from apps.accounts.tests.populate import fill
from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/export/"
SECTIONS = {
    "format",
    "version",
    "exported_at",
    "account",
    "posts",
    "comments",
    "likes",
    "following",
    "followers",
    "bookmarks",
    "reposts",
    "reports",
    "appeals",
    "credibility_history",
    "notifications",
}
# Anything of these anywhere in the file (as a key or a value) would be a leak.
FORBIDDEN = (
    "search_vector",
    "pipeline_result",
    "pipeline_attempts",
    "flagged_reason",
    "report_count",
    "counts_toward_threshold",
    "resolved_by",
    "moderated_by",
    "original_moderator",
    "notes",
    "password",
)


def get_export(client, user):
    return client.get(URL, HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}")


def test_the_download_has_every_section_and_a_file_name(api_client):
    user = VerifiedUserFactory(username="ada")
    response = get_export(api_client, user)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
    assert response["Content-Disposition"] == (
        f'attachment; filename="rumor-zero-ada-{timezone.now():%Y-%m-%d}.json"'
    )
    assert "no-cache" in response["Cache-Control"]
    data = response.json()
    assert set(data) == SECTIONS
    assert (data["format"], data["version"]) == ("rumor-zero-export", 1)
    for section in SECTIONS - {"format", "version", "exported_at", "account"}:
        assert data[section] == []


def test_the_account_section(api_client):
    user = VerifiedUserFactory(
        username="ada", display_name="Ada", bio="Hi", reputation_score=61, reputation_sample=4
    )
    SocialAccount.objects.create(user=user, provider="google", uid="g-1")
    account = get_export(api_client, user).json()["account"]
    assert account == {
        "id": str(user.pk),
        "username": "ada",
        "display_name": "Ada",
        "bio": "Hi",
        "email": user.email,
        "is_email_verified": True,
        "role": "user",
        "created_at": account["created_at"],
        "has_usable_password": True,
        "google_connected": True,
        "credibility": {"score": 61, "sample": 4, "public_score": 61},
    }


def test_the_score_is_null_publicly_below_the_sample(api_client):
    user = VerifiedUserFactory(reputation_score=70, reputation_sample=2)
    credibility = get_export(api_client, user).json()["account"]["credibility"]
    assert credibility == {"score": 70, "sample": 2, "public_score": None}


def test_everything_the_account_owns_is_in_it(api_client):
    user = VerifiedUserFactory(username="ada")
    posts = fill(user)
    data = get_export(api_client, user).json()

    by_content = {post["content"]: post for post in data["posts"]}
    assert set(by_content) == {"My fact", "Alert", "Bad", "Gone"}  # deleted and removed included
    fact = by_content["My fact"]
    assert fact["id"] == str(posts["fact"].pk)
    assert fact["sources"] == ["https://example.test/a", "10.1000/xyz"]
    assert (fact["status"], fact["verdict_source"], fact["confidence_score"]) == (
        "verified_false",
        "pipeline",
        "91.50",
    )
    assert fact["verdict_note"] == "Checked"
    assert fact["removal_reason"] == ""
    assert by_content["Alert"]["is_emergency"] is True
    assert by_content["Alert"]["emergency_expires_at"].endswith("Z")
    assert by_content["Bad"]["status"] == "removed"
    assert by_content["Bad"]["removal_reason"] == "Against the rules"
    assert by_content["Gone"]["deleted_at"] is not None
    assert [post["content"] for post in data["posts"]] == ["My fact", "Alert", "Bad", "Gone"]

    assert {c["content"] for c in data["comments"]} == {"Mine", "Hidden", "Deleted"}
    hidden = next(c for c in data["comments"] if c["content"] == "Hidden")
    assert hidden["hidden"] is True
    assert next(c for c in data["comments"] if c["content"] == "Deleted")["deleted_at"]

    assert len(data["likes"]) == len(data["bookmarks"]) == len(data["reposts"]) == 1
    assert data["reposts"][0]["status_at_repost"] == "published"
    assert [p["username"] for p in data["following"]] == ["other_person"]
    assert [p["username"] for p in data["followers"]] == ["other_person"]
    assert set(data["following"][0]) == {"user_id", "username", "created_at"}

    (report,) = data["reports"]
    assert set(report) == {
        "id",
        "post_id",
        "reason",
        "details",
        "status",
        "created_at",
        "resolved_at",
    }
    assert report["details"] == "Looks fake"
    (appeal,) = data["appeals"]
    assert set(appeal) == {"id", "post_id", "kind", "reason", "status", "created_at", "resolved_at"}
    assert (appeal["kind"], appeal["status"], appeal["reason"]) == ("label", "upheld", "I disagree")

    kinds = [row["kind"] for row in data["credibility_history"]]
    assert kinds == ["fact_false", "reversal", "fact_true"]
    history = data["credibility_history"]
    assert "appeal" not in history[0]
    assert history[1]["label"] == "Reversed: Fact labelled FALSE"
    assert history[0]["reversed"] is True and history[1]["reverses"] == history[0]["id"]
    # The post id stays even though the author deleted that post.
    assert history[2]["post_id"] == str(posts["deleted"].pk)

    notes = {row["type"]: row for row in data["notifications"]}
    assert set(notes) == {"follow", "comment", "under_review", "removed"}
    assert notes["follow"]["actor"] == "other_person"
    assert notes["under_review"]["actor"] is None
    assert notes["removed"]["is_read"] is True and notes["follow"]["is_read"] is False
    assert notes["comment"]["comment_id"] is not None and notes["follow"]["post_id"] is None


def test_nothing_private_or_internal_is_in_it(api_client):
    user = VerifiedUserFactory(username="ada")
    fill(user)
    response = get_export(api_client, user)
    text = response.content.decode()
    strings = list(walk_strings(response.json()))

    for word in FORBIDDEN:
        assert word not in strings, word
    assert "private@example.test" not in text  # another person's email
    assert "private moderator note" not in text
    assert "internals" not in text  # the pipeline blob
    assert "Someone else's post" not in text and "Not mine" not in text


def test_another_account_only_ever_sees_its_own_data(api_client):
    user = VerifiedUserFactory()
    fill(user)
    stranger = VerifiedUserFactory()
    data = get_export(api_client, stranger).json()
    assert data["posts"] == [] and data["comments"] == [] and data["notifications"] == []
    assert user.username not in json.dumps(data)


def test_the_query_count_is_fixed_whatever_the_volume(api_client):
    small, large = VerifiedUserFactory(), VerifiedUserFactory()
    fill(small, "_s")
    for n in range(3):
        fill(large, f"_l{n}")
    tokens = {small.pk: access_token_for(small), large.pk: access_token_for(large)}

    def count(user):
        with CaptureQueriesContext(connection) as queries:
            response = api_client.get(URL, HTTP_AUTHORIZATION=f"Bearer {tokens[user.pk]}")
        assert response.status_code == 200
        return len(queries), response.json()

    small_count, small_data = count(small)
    large_count, large_data = count(large)
    assert len(large_data["posts"]) == 3 * len(small_data["posts"])
    assert (
        small_count == large_count == 13
    )  # the user, the Google check, 11 sections, savepoint-free


def test_a_unicode_post_survives_the_round_trip(api_client):
    user = VerifiedUserFactory()
    PostFactory(author=user, content="Héllo 😀 “quoted”\nnew line")
    data = get_export(api_client, user).json()
    assert data["posts"][0]["content"] == "Héllo 😀 “quoted”\nnew line"


def test_the_filename_uses_the_time_it_is_given():
    user = UserFactory(username="bob")
    when = timezone.now().replace(year=2030, month=2, day=3)
    assert export.filename(user, when) == "rumor-zero-bob-2030-02-03.json"
    assert export.build_export(user, when)["exported_at"].startswith("2030-02-03T")


def test_anonymous_is_401(api_client):
    assert api_client.get(URL).status_code == 401


def test_an_unverified_account_can_still_export(api_client):
    user = UserFactory()
    assert get_export(api_client, user).status_code == 200


def test_ten_exports_an_hour_then_429(api_client):
    user = VerifiedUserFactory()
    token = access_token_for(user)
    codes = [
        api_client.get(URL, HTTP_AUTHORIZATION=f"Bearer {token}").status_code for _ in range(11)
    ]
    assert codes[:10] == [200] * 10
    assert codes[10] == 429


def test_a_post_view_that_is_not_json_serialisable_cannot_slip_in():
    """Every value is a string, number, bool, list, dict or None."""
    user = VerifiedUserFactory()
    fill(user)
    json.dumps(export.build_export(user, timezone.now()))
