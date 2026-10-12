"""The processor (ARCHITECTURE §6): claim → call → apply, the lease and its token, what happens
when something changes while a check is in flight, and the batch rules. One connection here; the
races with real threads are in `test_races.py`."""

import logging
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.moderation import services as moderation_services
from apps.moderation.tests.factories import moderator_user
from apps.pipeline import processor
from apps.pipeline.clients import StubPipelineClient
from apps.pipeline.contract import ContractError
from apps.pipeline.routing import MAX_ATTEMPTS, Outcome
from apps.pipeline.tests.conftest import FakeClient, answering, fact, failing, reported_fact
from apps.posts import services as post_services
from apps.posts.models import FlaggedReason, Post, PostStatus
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory
from apps.reports import services as report_services
from apps.reports.models import ReportReason
from apps.reports.tests.factories import ReportFactory, aged_user
from apps.social import services as social_services

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("pipeline_cfg")]


def fresh(post):
    return Post.objects.get(pk=post.pk)


# ---------- the claim ----------


def test_a_claim_counts_the_try_and_leases_the_post_without_touching_updated_at():
    post = fact()
    now = timezone.now()
    claim = processor.claim_next(now)
    assert (claim.post.pk, claim.attempts, claim.exhausted) == (post.pk, 1, False)
    after = fresh(post)
    assert after.pipeline_attempts == 1
    assert after.pipeline_next_attempt_at == now + processor.LEASE
    assert after.updated_at == post.updated_at
    assert after.status == PostStatus.PENDING


def test_a_leased_post_is_not_claimed_again_until_the_lease_ends():
    post = fact()
    now = timezone.now()
    processor.claim_next(now)
    assert processor.claim_next(now + processor.LEASE - timedelta(seconds=1)) is None
    again = processor.claim_next(now + processor.LEASE)
    assert (again.post.pk, again.attempts) == (post.pk, 2)


def test_nothing_due_claims_nothing():
    fact(pipeline_next_attempt_at=timezone.now() + timedelta(minutes=1))
    assert processor.claim_next(timezone.now()) is None
    assert processor.process_pending(client=FakeClient()) == 0


def test_the_claim_takes_only_what_the_request_needs_and_locks_with_skip_locked():
    fact()
    with CaptureQueriesContext(connection) as captured:
        processor.claim_next(timezone.now())
    queries = [q["sql"] for q in captured if "SAVEPOINT" not in q["sql"]]
    assert len(queries) == 2  # the locking select and the lease
    select, lease = queries
    assert "FOR NO KEY UPDATE OF" in select and "SKIP LOCKED" in select
    assert "LIMIT 1" in select
    assert '"posts_post"."pipeline_result"' not in select
    assert lease.startswith('UPDATE "posts_post" SET "pipeline_attempts"')
    assert '"updated_at"' not in lease


# ---------- a whole check ----------


@pytest.mark.parametrize(
    ("content", "status", "flag", "source", "confidence"),
    [
        ("Paris is in France #true", PostStatus.VERIFIED_TRUE, None, "pipeline", "95.00"),
        ("The Earth is flat #false", PostStatus.VERIFIED_FALSE, None, "pipeline", "92.00"),
        (
            "Coffee stunts growth #unsure",
            PostStatus.UNDER_REVIEW,
            FlaggedReason.PIPELINE,
            None,
            "40.00",
        ),
    ],
)
def test_the_stub_answers_each_tag(content, status, flag, source, confidence):
    post = fact(content)
    assert processor.process_pending(client=StubPipelineClient()) == 1
    after = fresh(post)
    assert (after.status, after.flagged_reason, after.verdict_source) == (status, flag, source)
    assert after.confidence_score == Decimal(confidence)
    assert after.pipeline_attempts == 1
    assert after.pipeline_next_attempt_at is None
    assert after.pipeline_checked_at is not None


def test_the_default_client_is_the_stub():
    post = fact("Paris is in France #true")
    assert processor.process_pending() == 1
    assert fresh(post).status == PostStatus.VERIFIED_TRUE


def test_the_request_carries_the_post_and_its_sources_in_order():
    post = fact(sources=["https://z.example/a", "10.1000/xyz", "https://a.example/b"])
    client = FakeClient()
    processor.process_pending(client=client)
    [request] = client.requests
    assert request.post_id == post.pk
    assert request.content == post.content
    assert request.sources == ("https://z.example/a", "10.1000/xyz", "https://a.example/b")


def test_a_fact_without_sources_sends_none():
    fact()
    client = FakeClient()
    processor.process_pending(client=client)
    assert client.requests[0].sources == ()


def test_a_failed_try_is_retried_after_the_backoff_then_given_up_after_five(caplog):
    post = fact("A claim nobody can check")
    client = failing("http_status", "HTTP 503")
    when = timezone.now()
    waits = []
    with caplog.at_level(logging.INFO):
        for _ in range(MAX_ATTEMPTS):
            assert processor.process_pending(client=client, now=when) == 1
            after = fresh(post)
            if after.pipeline_next_attempt_at:
                waits.append(after.pipeline_next_attempt_at - when)
                # Not due a moment before the backoff ends.
                early = after.pipeline_next_attempt_at - timedelta(seconds=1)
                assert processor.process_pending(client=client, now=early) == 0
                when = after.pipeline_next_attempt_at
    assert waits == [timedelta(minutes=m) for m in (2, 4, 8, 16)]
    after = fresh(post)
    assert (after.status, after.flagged_reason) == (PostStatus.UNDER_REVIEW, FlaggedReason.PIPELINE)
    assert after.pipeline_result == {"error": "http_status", "detail": "HTTP 503", "attempt": 5}
    assert after.pipeline_next_attempt_at is None
    assert len(client.requests) == MAX_ATTEMPTS
    levels = [r.levelname for r in caplog.records if r.name == "apps.pipeline.processor"]
    assert levels == ["WARNING"] * 4 + ["ERROR"]
    assert "A claim nobody can check" not in caplog.text  # never the content


def test_a_post_whose_tries_all_died_mid_call_is_given_up_without_another_call(caplog):
    """Every claim counts a try, so a post that crashes the worker each time still ends."""
    post = fact(pipeline_attempts=MAX_ATTEMPTS)
    client = FakeClient()
    with caplog.at_level(logging.ERROR):
        assert processor.process_pending(client=client) == 1
    assert client.requests == []
    after = fresh(post)
    assert (after.status, after.flagged_reason) == (PostStatus.UNDER_REVIEW, FlaggedReason.PIPELINE)
    assert after.pipeline_attempts == MAX_ATTEMPTS
    assert after.pipeline_result["error"] == "lease_expired"
    assert "given up" in caplog.text


def test_a_try_that_dies_mid_call_comes_back_when_the_lease_ends():
    post = fact("Paris is in France #true")
    start = timezone.now()
    processor.claim_next(start)  # the worker dies here: no answer is ever written
    assert processor.process_pending(now=start + timedelta(minutes=4)) == 0
    assert processor.process_pending(now=start + processor.LEASE + timedelta(seconds=1)) == 1
    after = fresh(post)
    assert (after.status, after.pipeline_attempts) == (PostStatus.VERIFIED_TRUE, 2)


def test_the_answer_of_a_try_whose_lease_ran_out_is_dropped():
    """A slow first try outlives its lease; a second processor claims the post and answers. The
    first answer arrives last and must change nothing (its claim token is stale)."""
    post = fact()
    start = timezone.now()
    later = start + processor.LEASE + timedelta(seconds=1)
    second = answering("false", 99)

    def meanwhile(request):
        assert processor.process_pending(client=second, now=later) == 1

    first = answering("true", 95, during=meanwhile)
    assert processor.process_pending(client=first, now=start) == 1
    after = fresh(post)
    assert (after.status, after.confidence_score) == (PostStatus.VERIFIED_FALSE, Decimal("99.00"))
    assert after.pipeline_attempts == 2


# ---------- what changes while a check is in flight ----------


def seed_counting_reports(post, n):
    for _ in range(n):
        ReportFactory(post=post, reporter=aged_user(now=timezone.now()))
    Post.objects.filter(pk=post.pk).update(report_count=n)


def fifth_report(post):
    def during(request):
        report_services.file_report(
            reporter=aged_user(now=timezone.now()),
            post_id=post.pk,
            reason=ReportReason.INACCURATE,
            details="",
        )
        assert fresh(post).status == PostStatus.UNDER_REVIEW

    return during


def test_reports_that_send_the_post_to_review_mid_check_get_the_late_true_rule():
    post = fact()
    seed_counting_reports(post, 4)
    assert processor.process_pending(client=answering("true", 95, during=fifth_report(post))) == 1
    after = fresh(post)
    assert (after.status, after.flagged_reason) == (PostStatus.UNDER_REVIEW, FlaggedReason.REPORTS)
    assert after.pre_review_status == PostStatus.VERIFIED_TRUE
    assert after.verdict_source == "pipeline"


def test_reports_that_send_the_post_to_review_mid_check_get_the_late_false_rule():
    post = fact()
    seed_counting_reports(post, 4)
    assert processor.process_pending(client=answering("false", 92, during=fifth_report(post))) == 1
    after = fresh(post)
    assert (after.status, after.flagged_reason) == (PostStatus.UNDER_REVIEW, FlaggedReason.BOTH)
    assert after.pre_review_status == PostStatus.PENDING
    assert after.verdict_source is None


def test_a_post_the_author_deletes_mid_check_keeps_no_verdict():
    post = fact()

    def delete(request):
        post_services.delete_post(post_id=post.pk, user=post.author)

    assert processor.process_pending(client=answering("false", 92, during=delete)) == 1
    after = fresh(post)
    assert after.deleted_at is not None
    assert (after.status, after.verdict_source, after.pipeline_checked_at) == (
        PostStatus.PENDING,
        None,
        None,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"status": PostStatus.REMOVED},
        {"status": PostStatus.VERIFIED_TRUE, "verdict_source": "moderator"},
    ],
    ids=["removed", "decided by a moderator"],
)
def test_a_post_removed_or_decided_mid_check_is_left_alone(change):
    post = fact()

    def act(request):
        Post.objects.filter(pk=post.pk).update(**change)

    processor.process_pending(client=answering("false", 99, during=act))
    after = fresh(post)
    for field, value in change.items():
        assert getattr(after, field) == value
    assert after.pipeline_verdict is None
    assert after.confidence_score is None


def test_a_dismissal_mid_check_routes_the_answer_like_a_pending_post():
    post = reported_fact()

    def dismiss(request):
        # The real service (Part 10), so the post is left exactly as a moderator leaves it.
        moderation_services.dismiss_reports(post.pk, moderator=moderator_user())

    processor.process_pending(client=answering("true", 95, during=dismiss))
    after = fresh(post)
    assert (after.status, after.verdict_source) == (PostStatus.VERIFIED_TRUE, "pipeline")


def test_a_reported_fact_found_false_late_can_still_be_reposted_so_nothing_reveals_it():
    """User decision 2026-10-11: the late FALSE goes to a moderator and is never stored as the
    label to restore, so Part 8's repost refusal can't reveal it."""
    post = reported_fact("A claim people reported #false")
    processor.process_pending()
    assert fresh(post).flagged_reason == FlaggedReason.BOTH
    assert social_services.repost(user=VerifiedUserFactory(), post_id=post.pk) is True


def test_a_post_found_false_before_the_reports_still_cannot_be_reposted():
    post = fact("A claim the pipeline labels #false")
    processor.process_pending()
    assert fresh(post).status == PostStatus.VERIFIED_FALSE
    seed_counting_reports(post, 4)
    fifth_report(post)(None)
    after = fresh(post)
    assert (after.status, after.pre_review_status) == (
        PostStatus.UNDER_REVIEW,
        PostStatus.VERIFIED_FALSE,
    )
    with pytest.raises(social_services.CannotRepostFalse):
        social_services.repost(user=VerifiedUserFactory(), post_id=post.pk)


# ---------- the batch ----------


def test_a_batch_takes_at_most_the_limit():
    posts = [fact(f"Claim {n} #true", age_seconds=100 - n) for n in range(12)]
    assert processor.process_pending(limit=10) == 10
    pending = [p for p in posts if fresh(p).status == PostStatus.PENDING]
    assert pending == posts[10:]  # the two newest wait for the next batch
    assert processor.process_pending(limit=10) == 2


def test_with_a_deadline_the_first_post_is_always_taken(monkeypatch):
    for n in range(3):
        fact(f"Claim {n}", age_seconds=10 - n)
    clock = {"now": 1000.0}

    def monotonic():
        clock["now"] += 0.001
        return clock["now"]

    monkeypatch.setattr(processor.time, "monotonic", monotonic)
    slow = FakeClient(max_seconds=25)
    assert processor.process_pending(client=slow, deadline=1000.0 + 25) == 1
    fast = FakeClient(max_seconds=0)
    assert processor.process_pending(client=fast, deadline=clock["now"] + 25) == 2


def test_one_post_that_fails_unexpectedly_does_not_stop_the_batch(monkeypatch, caplog):
    first, second = fact("first", age_seconds=20), fact("second #true", age_seconds=10)
    real = post_services.record_pipeline_result

    def broken_for_first(post_id, *args, **kwargs):
        if post_id == first.pk:
            raise RuntimeError("database hiccup")
        return real(post_id, *args, **kwargs)

    monkeypatch.setattr(post_services, "record_pipeline_result", broken_for_first)
    with caplog.at_level(logging.ERROR):
        assert processor.process_pending() == 2
    assert fresh(second).status == PostStatus.VERIFIED_TRUE
    stuck = fresh(first)
    assert stuck.status == PostStatus.PENDING
    assert stuck.pipeline_next_attempt_at > timezone.now()  # its lease brings it back
    assert "could not be handled" in caplog.text


@pytest.mark.parametrize(
    ("exc", "kind", "detail"),
    [
        (ContractError("verdict must be one of: true, false, inconclusive"), "contract", None),
        (KeyError("secret-looking message"), "error", "KeyError"),
    ],
)
def test_any_exception_from_the_client_is_a_failed_try(exc, kind, detail):
    post = fact()

    def answer(request):
        raise exc

    processor.process_pending(client=FakeClient(answer))
    result = fresh(post).pipeline_result
    assert result["error"] == kind
    if detail:
        assert result["detail"] == detail
    assert "secret-looking" not in str(result)


def test_process_post_checks_only_that_post_and_only_while_it_is_due():
    target, other = fact("target #true", age_seconds=10), fact("older #true", age_seconds=99)
    client = FakeClient()
    assert processor.process_post(target.pk, client=client) is True
    assert client.post_ids == [target.pk]
    assert fresh(other).status == PostStatus.PENDING
    assert processor.process_post(target.pk, client=client) is False  # already checked


def test_process_post_leaves_a_leased_post_and_an_opinion_alone():
    leased = fact(pipeline_next_attempt_at=timezone.now() + timedelta(minutes=3))
    opinion = PostFactory()
    client = FakeClient()
    assert processor.process_post(leased.pk, client=client) is False
    assert processor.process_post(opinion.pk, client=client) is False
    assert client.requests == []


def test_the_outcome_of_each_try_is_returned_for_part_13():
    post = fact("Claim #true")
    claim = processor.claim_next(timezone.now())
    assert processor._try(claim, StubPipelineClient(), None) == Outcome.LABELLED
    assert fresh(post).status == PostStatus.VERIFIED_TRUE


def test_the_claim_refuses_to_run_inside_a_callers_transaction():
    """`durable=True`: inside an outer transaction the lease would stay invisible to the other
    processors and the row lock would last until the caller commits."""
    from django.db import transaction

    fact()
    with pytest.raises(RuntimeError, match="durable"), transaction.atomic():
        processor.claim_next(timezone.now())


def test_tests_run_with_the_stub_and_without_the_kick(settings):
    """The root conftest pins both, whatever the developer's backend/.env says."""
    assert settings.PIPELINE_BACKEND == "stub"
    assert settings.PIPELINE_INLINE_KICK is False
