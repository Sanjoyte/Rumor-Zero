from datetime import timedelta

import pytest
from django.utils import timezone

from apps.posts.models import Post, PostStatus
from apps.posts.tests.factories import PostFactory, UserFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/posts/"
# The §9 post object, in full (25 keys; Part 11C added `emergency_demoted`).
POST_KEYS = {
    "id",
    "author",
    "content",
    "post_type",
    "status",
    "sources",
    "is_emergency",
    "emergency_active",
    "emergency_expires_at",
    "emergency_demoted",
    "confidence_score",
    "verdict_source",
    "verdict_note",
    "like_count",
    "comment_count",
    "repost_count",
    "liked_by_me",
    "reposted_by_me",
    "bookmarked_by_me",
    "reported_by_me",
    "is_mine",
    "can_appeal",
    "appeal_status",
    "removal_reason",
    "created_at",
}


@pytest.fixture
def client(auth_client, verified_user, fact_limit):
    return auth_client(verified_user)


def submit(client, **body):
    return client.post(URL, body, format="json")


def opinion(client, content="I think rain is nice", **extra):
    return submit(client, content=content, post_type="opinion", **extra)


def fact(client, content="Water boils at 100C at sea level", **extra):
    return submit(client, content=content, post_type="fact", **extra)


# ---------- who may post ----------


def test_an_anonymous_visitor_cannot_post(api_client):
    response = api_client.post(URL, {"content": "x", "post_type": "opinion"}, format="json")
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"
    assert not Post.objects.exists()


def test_an_unverified_user_gets_403_and_nothing_is_saved(auth_client):
    response = opinion(auth_client(UserFactory()))
    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"
    assert not Post.objects.exists()


# ---------- the 201 answer ----------


def test_an_opinion_is_published(client, verified_user):
    response = opinion(client)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == POST_KEYS
    assert body["status"] == "published"
    assert body["post_type"] == "opinion"
    assert body["content"] == "I think rain is nice"
    assert body["sources"] == []
    assert body["is_mine"] is True
    assert body["author"] == {
        "id": str(verified_user.pk),
        "username": verified_user.username,
        "display_name": "",
        "avatar_url": None,
    }
    post = Post.objects.get()
    assert post.author == verified_user
    assert post.status == PostStatus.PUBLISHED


def test_a_fact_is_pending_with_its_sources_in_order(client):
    response = fact(
        client, sources=["doi:10.1038/s41558-024-02102", "HTTPS://Example.org/report?x=1"]
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["post_type"] == "fact"
    assert body["sources"] == [
        {"value": "10.1038/s41558-024-02102", "kind": "doi"},
        {"value": "https://example.org/report?x=1", "kind": "url"},
    ]
    assert Post.objects.get().sources == [
        "10.1038/s41558-024-02102",
        "https://example.org/report?x=1",
    ]


def test_the_defaults_of_the_fields_later_parts_fill(client):
    body = fact(client).json()
    assert body["confidence_score"] is None
    assert body["verdict_source"] is None
    assert body["verdict_note"] == ""
    assert body["is_emergency"] is False
    assert body["emergency_active"] is False
    assert body["emergency_expires_at"] is None
    assert body["emergency_demoted"] is False
    assert (body["like_count"], body["comment_count"], body["repost_count"]) == (0, 0, 0)
    assert not any(
        body[key] for key in ("liked_by_me", "reposted_by_me", "bookmarked_by_me", "reported_by_me")
    )
    assert body["can_appeal"] is False
    assert body["appeal_status"] is None
    assert body["removal_reason"] == ""


def test_created_at_is_iso_utc(client):
    before = timezone.now()
    created = opinion(client).json()["created_at"]
    assert created.endswith("Z")
    assert before <= timezone.datetime.fromisoformat(created.replace("Z", "+00:00"))


def test_content_is_trimmed_and_inner_newlines_are_kept(client):
    body = opinion(client, content="  line one\nline two \n").json()
    assert body["content"] == "line one\nline two"


def test_the_answer_matches_the_feed_entry(client, api_client):
    created = opinion(client).json()
    (item,) = api_client.get(URL).json()["results"]
    assert item["post"] == {**created, "is_mine": False}


def test_a_post_answer_is_never_cached(client):
    assert "no-store" in opinion(client)["Cache-Control"]


# ---------- validation ----------


@pytest.mark.parametrize(
    ("body", "field", "message"),
    [
        ({"post_type": "opinion"}, "content", "Write something first."),
        ({"content": "", "post_type": "opinion"}, "content", "Write something first."),
        ({"content": "   \n ", "post_type": "opinion"}, "content", "Write something first."),
        ({"content": None, "post_type": "opinion"}, "content", "Write something first."),
        ({"content": "x" * 501, "post_type": "opinion"}, "content", "Keep it to 500 characters."),
        ({"content": "\U0001f600" * 501, "post_type": "fact"}, "content", "Keep it to 500"),
        ({"content": "Hello"}, "post_type", "Choose Opinion or Fact."),
        ({"content": "Hello", "post_type": ""}, "post_type", "Choose Opinion or Fact."),
        ({"content": "Hello", "post_type": "claim"}, "post_type", "Choose Opinion or Fact."),
        ({"content": "Hello", "post_type": None}, "post_type", "Choose Opinion or Fact."),
    ],
)
def test_bad_content_or_type_is_a_400_on_that_field(client, body, field, message):
    response = submit(client, **body)
    assert response.status_code == 400
    assert message in response.json()[field][0]
    assert not Post.objects.exists()


def test_500_characters_are_fine_and_so_are_500_emoji(client):
    assert opinion(client, content="x" * 500).status_code == 201
    assert opinion(client, content="\U0001f600" * 500).status_code == 201


def test_sources_on_an_opinion_are_refused(client):
    response = opinion(client, sources=["10.1000/xyz"])
    assert response.status_code == 400
    assert response.json() == {"sources": ["Only fact posts can have sources."]}
    assert not Post.objects.exists()


def test_empty_sources_on_an_opinion_are_fine(client):
    assert opinion(client, sources=[]).status_code == 201


def test_a_bad_source_is_reported_by_index_and_refuses_the_whole_post(client):
    response = fact(client, sources=["10.1000/ok", "javascript:alert(1)", "http://127.0.0.1/"])
    assert response.status_code == 400
    errors = response.json()["sources"]
    assert set(errors) == {"1", "2"}
    assert "https://" in errors["1"][0]
    assert "IP addresses" in errors["2"][0]
    assert not Post.objects.exists()


def test_a_duplicate_is_reported_on_the_later_index(client):
    response = fact(client, sources=["doi:10.1000/xyz", "https://doi.org/10.1000/XYZ"])
    assert response.json() == {"sources": {"1": ["Same as source 1."]}}


def test_six_sources_are_a_list_level_error_even_with_a_bad_element(client):
    sources = ["javascript:x"] + [f"10.1000/s{i}" for i in range(5)]
    response = fact(client, sources=sources)
    assert response.status_code == 400
    assert response.json() == {"sources": ["You can add up to 5 sources."]}


def test_five_sources_are_fine(client):
    assert fact(client, sources=[f"10.1000/s{i}" for i in range(5)]).status_code == 201


@pytest.mark.parametrize("sources", ["10.1000/xyz", {"a": 1}, 5])
def test_sources_must_be_a_list(client, sources):
    response = fact(client, sources=sources)
    assert response.status_code == 400
    assert "sources" in response.json()


def test_an_empty_source_string_is_reported(client):
    response = fact(client, sources=["10.1000/ok", ""])
    assert response.status_code == 400
    assert list(response.json()["sources"]) == ["1"]


# ---------- what the client may not decide ----------


def test_is_emergency_false_is_fine(client):
    assert fact(client, is_emergency=False).status_code == 201


# ---------- Part 11C: emergency posts (§4b) ----------


@pytest.fixture
def elder(fact_limit):
    """Eligible for an emergency: verified, 30 days old, the starting score of 50."""
    return VerifiedUserFactory(created_at=timezone.now() - timedelta(days=30))


def test_an_eligible_author_posts_an_emergency(auth_client, elder):
    before = timezone.now()
    response = fact(auth_client(elder), is_emergency=True)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == POST_KEYS
    assert body["status"] == "pending"
    assert (body["is_emergency"], body["emergency_active"], body["emergency_demoted"]) == (
        True,
        True,
        False,
    )
    post = Post.objects.get()
    assert post.is_emergency and post.emergency_expires_at == post.created_at + timedelta(hours=24)
    assert post.created_at >= before
    assert body["emergency_expires_at"].endswith("Z")


def test_an_emergency_opinion_is_a_400_on_the_field(client):
    response = opinion(client, is_emergency=True)
    assert response.status_code == 400
    assert response.json() == {"is_emergency": ["Only fact posts can be emergencies."]}
    assert not Post.objects.exists()


def _refused(response, reason):
    assert response.status_code == 403
    body = response.json()
    assert set(body) == {"detail", "code", "reason", "next_allowed_at"}
    assert (body["code"], body["reason"]) == ("emergency_not_allowed", reason)
    assert body["detail"] and "None" not in body["detail"]
    assert not Post.objects.exists()
    return body


def test_a_new_account_is_refused_with_the_day_it_may(auth_client, fact_limit):
    created = timezone.now() - timedelta(days=2)
    author = VerifiedUserFactory(created_at=created)
    body = _refused(fact(auth_client(author), is_emergency=True), "account_too_new")
    expected = (created + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    assert body["next_allowed_at"].startswith(expected) and body["next_allowed_at"].endswith("Z")
    assert "too new" in body["detail"]


def test_a_low_score_is_refused_with_no_time(auth_client, elder):
    from apps.accounts.models import User

    User.objects.filter(pk=elder.pk).update(reputation_score=39)
    body = _refused(fact(auth_client(elder), is_emergency=True), "score_too_low")
    assert body["next_allowed_at"] is None  # null, never the string "None"


def test_a_blocked_account_is_refused_until_the_block_ends(auth_client, elder):
    from apps.accounts.models import User

    until = timezone.now() + timedelta(days=12)
    User.objects.filter(pk=elder.pk).update(emergency_blocked_until=until)
    body = _refused(fact(auth_client(elder), is_emergency=True), "blocked")
    assert body["next_allowed_at"].startswith(until.strftime("%Y-%m-%dT%H:%M:%S"))


def test_the_daily_limit_is_refused_with_the_time_a_slot_frees(auth_client, elder):
    first = fact(auth_client(elder), content="First warning", is_emergency=True)
    assert first.status_code == 201
    response = fact(auth_client(elder), content="Second warning", is_emergency=True)
    assert response.status_code == 403
    body = response.json()
    assert body["reason"] == "daily_limit"
    made = Post.objects.get().created_at
    assert body["next_allowed_at"].startswith(
        (made + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    )
    # A plain fact is still fine: the emergency limit is its own.
    assert fact(auth_client(elder), content="A plain claim").status_code == 201


def test_a_full_fact_quota_refuses_an_emergency_with_its_reason(auth_client, elder, fact_limit):
    fact_limit(1)
    assert fact(auth_client(elder), content="A plain claim").status_code == 201
    response = fact(auth_client(elder), is_emergency=True)
    assert response.status_code == 403
    assert response.json()["reason"] == "fact_quota"
    assert Post.objects.count() == 1


def test_paused_settings_are_refused_with_no_time(auth_client, elder, emergency_settings):
    emergency_settings(emergency_posts_per_day=0)
    body = _refused(fact(auth_client(elder), is_emergency=True), "daily_limit")
    assert body["next_allowed_at"] is None
    assert body["detail"] == "Emergency posts are paused right now."


def test_an_unverified_author_hears_email_unverified_first(auth_client):
    """The permission answers before the service: the `unverified` reason reaches people through
    the quota endpoint (and the service's own test)."""
    old = UserFactory(created_at=timezone.now() - timedelta(days=30))
    response = fact(auth_client(old), is_emergency=True)
    assert (response.status_code, response.json()["code"]) == (403, "email_unverified")


def test_fields_the_client_must_not_set_are_ignored(client, verified_user):
    other = VerifiedUserFactory()
    response = opinion(
        client,
        status="verified_true",
        author=str(other.pk),
        created_at="2001-01-01T00:00:00Z",
        confidence_score="99.00",
        verdict_source="moderator",
        report_count=99,
        deleted_at="2001-01-01T00:00:00Z",
    )
    assert response.status_code == 201
    post = Post.objects.get()
    assert post.status == PostStatus.PUBLISHED
    assert post.author == verified_user
    assert post.created_at.year != 2001
    assert post.confidence_score is None
    assert post.verdict_source is None
    assert (post.report_count, post.deleted_at) == (0, None)


# ---------- the fact quota ----------


def test_the_eleventh_fact_post_in_24_hours_is_a_429_with_retry_after(client):
    for i in range(10):
        assert fact(client, content=f"Claim {i}").status_code == 201
    response = fact(client, content="Claim 11")
    assert response.status_code == 429
    body = response.json()
    assert body["code"] == "fact_quota_exceeded"
    assert "all 10 of your fact posts" in body["detail"]
    assert "UTC" in body["detail"]
    assert 0 < int(response["Retry-After"]) <= 24 * 3600
    assert Post.objects.count() == 10


def test_opinions_are_not_limited_by_the_fact_quota(client):
    for i in range(10):
        fact(client, content=f"Claim {i}")
    assert opinion(client).status_code == 201


def test_a_limit_of_zero_pauses_fact_posts_with_403(client, fact_limit):
    fact_limit(0)
    response = fact(client)
    assert response.status_code == 403
    assert response.json()["code"] == "fact_posts_paused"
    assert "Retry-After" not in response
    assert opinion(client).status_code == 201


def test_deleted_facts_still_count(client, verified_user):
    PostFactory.create_batch(10, author=verified_user, fact=True, deleted=True)
    assert fact(client).status_code == 429


# ---------- the throttle ----------


def test_the_31st_post_in_an_hour_is_throttled(client):
    for i in range(30):
        assert opinion(client, content=f"Opinion {i}").status_code == 201
    response = opinion(client, content="Opinion 31")
    assert response.status_code == 429
    assert response.json()["code"] == "throttled"
    assert "Retry-After" in response


def test_reading_the_feed_does_not_use_up_the_posting_allowance(client):
    for _ in range(40):
        assert client.get(URL).status_code == 200
    for i in range(30):
        assert opinion(client, content=f"Opinion {i}").status_code == 201
    assert opinion(client).status_code == 429


def test_refused_attempts_that_fail_permissions_do_not_count(auth_client):
    unverified = auth_client(UserFactory())
    for _ in range(35):
        assert opinion(unverified).status_code == 403


def test_a_quota_refusal_does_count_against_the_throttle(client):
    for i in range(10):
        fact(client, content=f"Claim {i}")
    for _ in range(20):
        assert fact(client).status_code == 429  # the quota, not the throttle
    assert fact(client).json()["code"] == "throttled"
