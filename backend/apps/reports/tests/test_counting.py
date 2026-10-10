"""Whether a report counts toward the threshold (ARCHITECTURE §5; user decision 2026-10-10)."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.reports import services
from apps.reports.tests.factories import NOW, VerifiedUserFactory
from apps.social.tests.factories import CommentFactory, PostFactory

pytestmark = pytest.mark.django_db

CFG = SimpleNamespace(report_min_account_age_hours=24)


def young(hours=1, **fields):
    return VerifiedUserFactory(created_at=NOW - timedelta(hours=hours), **fields)


def counts(user, cfg=CFG):
    return services.counts_toward_threshold(user, cfg, NOW)


# ---------- the age rule (inclusive) ----------


def test_an_account_exactly_at_the_minimum_age_counts():
    assert counts(young(hours=24)) is True


def test_an_account_a_microsecond_too_young_does_not_count():
    user = VerifiedUserFactory(created_at=NOW - timedelta(hours=24) + timedelta(microseconds=1))
    assert counts(user) is False


def test_an_older_account_counts_without_any_activity():
    assert counts(young(hours=500)) is True


def test_a_minimum_age_of_zero_makes_every_account_count():
    assert counts(young(hours=0), SimpleNamespace(report_min_account_age_hours=0)) is True


def test_the_minimum_age_is_read_from_the_settings():
    user = young(hours=5)
    assert counts(user, SimpleNamespace(report_min_account_age_hours=6)) is False
    assert counts(user, SimpleNamespace(report_min_account_age_hours=5)) is True


def test_an_established_account_costs_no_query(django_assert_num_queries):
    user = young(hours=48)
    with django_assert_num_queries(0):
        assert counts(user) is True


# ---------- a young account counts through its own posts ----------


@pytest.mark.parametrize(
    "traits",
    [
        {},  # published opinion
        {"fact": True},  # pending
        {"verified_pipeline": True},
        {"moderator_verdict": True},  # FALSE
        {"under_review": True},
        {"deleted": True},  # deleting undoes nothing
    ],
)
def test_a_young_account_with_a_post_counts(traits):
    user = young()
    PostFactory(author=user, **traits)
    assert counts(user) is True


def test_a_young_account_whose_only_post_was_removed_does_not_count():
    user = young()
    PostFactory(author=user, removed=True)
    assert counts(user) is False


def test_removed_and_deleted_is_still_removed():
    user = young()
    PostFactory(author=user, removed=True, deleted=True)
    assert counts(user) is False


def test_a_removed_post_next_to_a_good_one_still_counts():
    user = young()
    PostFactory(author=user, removed=True)
    PostFactory(author=user)
    assert counts(user) is True


# ---------- and through its comments ----------


def test_a_young_account_with_a_shown_comment_counts():
    user = young()
    CommentFactory(author=user)
    assert counts(user) is True


def test_a_comment_the_person_deleted_still_counts():
    user = young()
    CommentFactory(author=user, deleted=True)
    assert counts(user) is True


def test_a_comment_a_moderator_hid_does_not_count():
    user = young()
    CommentFactory(author=user, hidden=True)
    assert counts(user) is False


def test_hidden_and_deleted_is_still_hidden():
    user = young()
    CommentFactory(author=user, hidden=True, deleted=True)
    assert counts(user) is False


def test_someone_elses_posts_and_comments_do_not_help():
    user, other = young(), young()
    PostFactory(author=other)
    CommentFactory(author=other)
    assert counts(user) is False


def test_nothing_at_all_does_not_count():
    assert counts(young()) is False


def test_query_shape_is_at_most_two_exists_checks(django_assert_num_queries):
    user = young()
    with django_assert_num_queries(2):  # no post, then no comment
        assert counts(user) is False
    PostFactory(author=user)
    with django_assert_num_queries(1):  # the post is enough
        assert counts(user) is True


def test_the_real_clock_is_not_used():
    """`now` is a parameter: an account made just now is young now but old two days later."""
    user = VerifiedUserFactory(created_at=timezone.now())
    assert services.counts_toward_threshold(user, CFG, timezone.now()) is False
    assert services.counts_toward_threshold(user, CFG, timezone.now() + timedelta(days=2)) is True
