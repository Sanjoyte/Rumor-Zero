"""`POST /api/v1/posts/{id}/report/` (ARCHITECTURE §5, §9)."""

import uuid

import pytest
from django.utils import timezone

from apps.posts.models import Post, PostStatus
from apps.reports.models import Report, ReportReason, ReportStatus
from apps.reports.tests.factories import ReportFactory, UserFactory, aged_user
from apps.social.tests.factories import PostFactory

pytestmark = pytest.mark.django_db


def url(post_id):
    return f"/api/v1/posts/{post_id}/report/"


@pytest.fixture
def reporter():
    return aged_user(now=timezone.now())


@pytest.fixture
def post():
    return PostFactory()


def report(client, post_id, **body):
    body.setdefault("reason", "spam")
    return client.post(url(post_id), body, format="json")


def code(client, post_id, **body):
    """The status code of a report."""
    return report(client, post_id, **body).status_code


# ---------- the happy path ----------


def test_a_report_is_201_with_a_fixed_body(auth_client, reporter, post):
    response = report(auth_client(reporter), post.pk, reason="spam")
    assert response.status_code == 201
    assert response.json() == {"reported": True}
    stored = Report.objects.get()
    assert (stored.post_id, stored.reporter_id, stored.reason) == (post.pk, reporter.pk, "spam")
    assert stored.status == ReportStatus.OPEN


def test_the_answer_is_the_same_whether_or_not_it_sent_the_post_to_review(
    auth_client, reporter, post, report_settings
):
    report_settings(threshold=2)
    first = report(auth_client(reporter), post.pk)
    second = report(auth_client(aged_user(now=timezone.now())), post.pk)
    assert first.json() == second.json() == {"reported": True}
    assert Post.objects.get(pk=post.pk).status == PostStatus.UNDER_REVIEW


@pytest.mark.parametrize("reason", ReportReason.values)
def test_every_reason_is_accepted(auth_client, reporter, post, reason):
    body = {"reason": reason, "details": "Because."}
    assert auth_client(reporter).post(url(post.pk), body, format="json").status_code == 201


def test_details_are_trimmed_and_optional_for_the_first_four(auth_client, reporter):
    client = auth_client(reporter)
    one, two = PostFactory(), PostFactory()
    assert (
        report(client, one.pk, reason="harassment", details="  It targets me.  ").status_code == 201
    )
    assert code(client, two.pk, reason="spam") == 201
    stored = {r.post_id: r.details for r in Report.objects.all()}
    assert stored == {one.pk: "It targets me.", two.pk: ""}


def test_null_details_are_read_as_nothing_typed(auth_client, reporter, post):
    assert (
        report(auth_client(reporter), post.pk, reason="misleading", details=None).status_code == 201
    )
    assert Report.objects.get().details == ""


def test_undeclared_fields_are_ignored(auth_client, post):
    young = UserFactory(is_email_verified=True)  # a brand-new account: its report doesn't count
    body = {
        "reason": "spam",
        "status": "actioned",
        "counts_toward_threshold": True,
        "reporter": str(uuid.uuid4()),
        "resolved_at": "2026-01-01T00:00:00Z",
        "created_at": "2020-01-01T00:00:00Z",
    }
    assert auth_client(young).post(url(post.pk), body, format="json").status_code == 201
    stored = Report.objects.get()
    assert stored.status == ReportStatus.OPEN and stored.resolved_at is None
    assert stored.counts_toward_threshold is False
    assert stored.reporter_id == young.pk
    assert stored.created_at.year == timezone.now().year


def test_the_post_stays_visible_while_it_is_under_review(
    auth_client, reporter, post, report_settings, api_client
):
    report_settings(threshold=1)
    assert report(auth_client(reporter), post.pk).status_code == 201
    detail = api_client.get(f"/api/v1/posts/{post.pk}/")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "under_review" and body["content"] == post.content
    listed = api_client.get("/api/v1/posts/").json()["results"]
    assert str(post.pk) in [item["post"]["id"] for item in listed]


def test_five_counting_reports_move_the_post_to_review_through_the_api(auth_client, post):
    for n in range(5):
        response = report(auth_client(aged_user(now=timezone.now())), post.pk)
        assert response.status_code == 201
        expected = PostStatus.UNDER_REVIEW if n == 4 else PostStatus.PUBLISHED
        assert Post.objects.get(pk=post.pk).status == expected
    after = Post.objects.get(pk=post.pk)
    assert (after.flagged_reason, after.pre_review_status) == ("reports", PostStatus.PUBLISHED)


# ---------- who can report ----------


def test_an_anonymous_visitor_is_401(api_client, post):
    response = api_client.post(url(post.pk), {"reason": "spam"}, format="json")
    assert response.status_code == 401
    assert Report.objects.count() == 0


def test_an_unverified_email_is_403_email_unverified(auth_client, post):
    response = report(auth_client(UserFactory()), post.pk)
    assert response.status_code == 403
    assert response.json()["code"] == "email_unverified"
    assert Report.objects.count() == 0


def test_your_own_post_is_403_cannot_report_own(auth_client, post):
    response = report(auth_client(post.author), post.pk)
    assert response.status_code == 403
    assert response.json() == {
        "detail": "You can't report your own post.",
        "code": "cannot_report_own",
    }
    assert Report.objects.count() == 0 and Post.objects.get(pk=post.pk).report_count == 0


def test_reporting_twice_is_409_already_reported(auth_client, reporter, post):
    client = auth_client(reporter)
    assert report(client, post.pk).status_code == 201
    again = report(client, post.pk, reason="harassment", details="x")
    assert again.status_code == 409
    assert again.json() == {"detail": "You already reported this post.", "code": "already_reported"}
    assert Report.objects.count() == 1 and Post.objects.get(pk=post.pk).report_count == 1


def test_a_dismissed_report_still_blocks_a_second_one(auth_client, post):
    old = ReportFactory(post=post, dismissed=True)
    response = report(auth_client(old.reporter), post.pk)
    assert response.status_code == 409


# ---------- which posts ----------


@pytest.mark.parametrize("traits", [{"removed": True}, {"deleted": True}])
def test_a_removed_or_deleted_post_is_404(auth_client, reporter, traits):
    gone = PostFactory(**traits)
    response = report(auth_client(reporter), gone.pk)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert Report.objects.count() == 0


def test_your_own_removed_post_is_404_not_403(auth_client):
    mine = PostFactory(removed=True)
    assert report(auth_client(mine.author), mine.pk).status_code == 404


@pytest.mark.parametrize("post_id", [str(uuid.uuid4()), "not-a-uuid", "123", "%00"])
def test_an_unknown_or_malformed_id_is_a_json_404(auth_client, reporter, post_id):
    response = auth_client(reporter).post(url(post_id), {"reason": "spam"}, format="json")
    assert response.status_code == 404
    assert response["Content-Type"].startswith("application/json")


@pytest.mark.parametrize(
    "traits",
    [
        {"fact": True},
        {},
        {"verified_pipeline": True},
        {"moderator_verdict": True},
        {"under_review": True},
    ],
)
def test_every_visible_status_can_be_reported(auth_client, reporter, traits):
    target = PostFactory(**traits)
    assert report(auth_client(reporter), target.pk).status_code == 201


# ---------- the body ----------


def test_a_missing_or_unknown_reason_is_one_message(auth_client, reporter, post):
    client = auth_client(reporter)
    for body in ({}, {"reason": None}, {"reason": ""}, {"reason": "nonsense"}, {"reason": 7}):
        response = client.post(url(post.pk), body, format="json")
        assert response.status_code == 400, body
        assert response.json() == {"reason": ["Choose a reason."]}, body
    assert Report.objects.count() == 0


@pytest.mark.parametrize("details", ["", None, "   ", "\n\t"])
def test_something_else_needs_details(auth_client, reporter, post, details):
    body = {"reason": "other"}
    if details is not None:
        body["details"] = details
    response = auth_client(reporter).post(url(post.pk), body, format="json")
    assert response.status_code == 400
    assert response.json() == {"details": ["Tell us what's wrong."]}


def test_something_else_with_words_is_fine(auth_client, reporter, post):
    assert (
        report(auth_client(reporter), post.pk, reason="other", details="It's a scam.").status_code
        == 201
    )


def test_details_over_500_characters_are_refused_and_500_are_fine(auth_client, reporter):
    client = auth_client(reporter)
    refused = report(client, PostFactory().pk, reason="other", details="x" * 501)
    assert refused.status_code == 400
    assert refused.json() == {"details": ["Keep it to 500 characters."]}
    assert report(client, PostFactory().pk, reason="other", details="x" * 500).status_code == 201


def test_details_are_counted_in_code_points(auth_client, reporter):
    client = auth_client(reporter)
    assert report(client, PostFactory().pk, reason="other", details="😀" * 500).status_code == 201
    assert report(client, PostFactory().pk, reason="other", details="😀" * 501).status_code == 400


def test_the_details_are_trimmed_before_they_are_counted(auth_client, reporter, post):
    padded = " " * 40 + "x" * 500 + " " * 40
    assert report(auth_client(reporter), post.pk, reason="other", details=padded).status_code == 201
    assert Report.objects.get().details == "x" * 500


def test_a_bad_body_stores_nothing_and_reads_the_post_not_at_all(auth_client, reporter, post):
    report(auth_client(reporter), post.pk, reason="nonsense")
    assert Report.objects.count() == 0 and Post.objects.get(pk=post.pk).report_count == 0


# ---------- the method, the cache and the throttle ----------


def test_only_post_is_allowed(auth_client, reporter, post):
    client = auth_client(reporter)
    for method in ("get", "put", "patch", "delete"):
        assert getattr(client, method)(url(post.pk)).status_code == 405


def test_the_answer_is_never_cached(auth_client, reporter, post):
    response = report(auth_client(reporter), post.pk)
    assert "no-store" in response["Cache-Control"]


def test_the_eleventh_report_in_an_hour_is_429(auth_client, reporter):
    client = auth_client(reporter)
    for _ in range(10):
        assert report(client, PostFactory().pk).status_code == 201
    response = report(client, PostFactory().pk)
    assert response.status_code == 429
    assert response["Retry-After"].isdigit()
    assert response.json()["code"] == "throttled"
    assert Report.objects.count() == 10


def test_a_400_counts_against_the_allowance_but_a_401_or_403_does_not(
    auth_client, api_client, reporter, post
):
    # 12 anonymous and 12 unverified attempts use nothing up.
    unverified = auth_client(UserFactory())
    for _ in range(12):
        assert api_client.post(url(post.pk), {"reason": "spam"}, format="json").status_code == 401
        assert report(unverified, post.pk).status_code == 403
    # Ten bad bodies do: the eleventh request is refused whatever it holds.
    client = auth_client(reporter)
    for _ in range(10):
        assert client.post(url(post.pk), {}, format="json").status_code == 400
    assert report(client, post.pk).status_code == 429


def test_the_report_allowance_is_its_own(auth_client, reporter):
    """Likes and reposts have their own buckets: using up the reports leaves them alone."""
    client = auth_client(reporter)
    for _ in range(10):
        report(client, PostFactory().pk)
    assert report(client, PostFactory().pk).status_code == 429
    other = PostFactory()
    assert client.post(f"/api/v1/posts/{other.pk}/like/").status_code == 201
    assert client.post(f"/api/v1/posts/{other.pk}/repost/").status_code == 201
