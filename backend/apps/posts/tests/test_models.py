from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.posts.models import Post, PostStatus, PostType
from apps.posts.tests.factories import PostFactory, VerifiedUserFactory

pytestmark = pytest.mark.django_db

DOI = "10.1000/xyz"


def violated(constraint_name, **fields):
    """Creating the post must fail on exactly this constraint (not some other check)."""
    with pytest.raises(IntegrityError) as exc, transaction.atomic():
        PostFactory(**fields)
    assert exc.value.__cause__.diag.constraint_name == constraint_name


@pytest.mark.parametrize("status", ["verified_true", "verified_false", "pending"])
def test_an_opinion_cannot_carry_a_fact_status(status):
    violated("posts_post_opinion_status", post_type=PostType.OPINION, status=status)


def test_a_fact_cannot_be_published():
    violated("posts_post_fact_not_published", post_type=PostType.FACT, status="published")


def test_an_opinion_cannot_have_sources():
    violated("posts_post_sources_fact_only", post_type=PostType.OPINION, sources=[DOI])


def test_a_post_cannot_have_more_than_five_sources():
    violated("posts_post_sources_max", fact=True, sources=[f"10.1000/x{i}" for i in range(6)])


def test_five_sources_are_fine():
    post = PostFactory(fact=True, sources=[f"10.1000/x{i}" for i in range(5)])
    assert len(Post.objects.get(pk=post.pk).sources) == 5


def test_a_source_cannot_be_empty():
    violated("posts_post_sources_not_empty", fact=True, sources=[DOI, ""])


def test_a_source_cannot_be_null():
    violated("posts_post_sources_not_null", fact=True, sources=[DOI, None])


def test_the_column_never_stores_more_than_500_characters_per_source():
    # Django writes `%s::varchar(500)[]`, and an explicit cast truncates silently instead of
    # raising (a plain INSERT of a literal would raise "value too long"). So the column type can't
    # *refuse* a long source: `validators.normalize_source` does, before anything is saved.
    post = PostFactory(fact=True, sources=["https://example.org/" + "a" * 481])
    assert len(Post.objects.get(pk=post.pk).sources[0]) == 500


def test_an_opinion_cannot_be_an_emergency():
    violated(
        "posts_post_emergency_fact_only",
        post_type=PostType.OPINION,
        is_emergency=True,
        emergency_expires_at=timezone.now() + timedelta(hours=24),
    )


def test_an_emergency_needs_an_expiry():
    violated("posts_post_emergency_expiry", fact=True, is_emergency=True)


def test_an_expiry_needs_an_emergency():
    violated(
        "posts_post_emergency_expiry",
        fact=True,
        is_emergency=False,
        emergency_expires_at=timezone.now(),
    )


@pytest.mark.parametrize("content", ["", "x" * 501])
def test_content_must_be_1_to_500_characters(content):
    violated("posts_post_content_length", content=content)


def test_500_emoji_are_500_characters_not_1000():
    post = PostFactory(content="\U0001f600" * 500)
    assert len(Post.objects.get(pk=post.pk).content) == 500


@pytest.mark.parametrize("score", [Decimal("-0.01"), Decimal("100.01")])
def test_confidence_must_be_0_to_100(score):
    violated("posts_post_confidence_range", verified_pipeline=True, confidence_score=score)


@pytest.mark.parametrize("score", [Decimal("0"), Decimal("100"), None])
def test_confidence_edges_are_fine(score):
    PostFactory(verified_pipeline=True, confidence_score=score)


@pytest.mark.parametrize(
    ("constraint", "fields"),
    [
        ("posts_post_type_valid", {"post_type": "bogus"}),
        ("posts_post_status_valid", {"post_type": "fact", "status": "bogus"}),
        ("posts_post_flagged_reason_valid", {"flagged_reason": "bogus"}),
        ("posts_post_pre_review_status_valid", {"pre_review_status": "bogus"}),
        ("posts_post_pre_removal_status_valid", {"pre_removal_status": "bogus"}),
        ("posts_post_pipeline_verdict_valid", {"pipeline_verdict": "bogus"}),
        ("posts_post_verdict_source_valid", {"verdict_source": "bogus"}),
    ],
)
def test_enum_columns_only_take_their_choices(constraint, fields):
    violated(constraint, **fields)


@pytest.mark.parametrize("status", ["published", "under_review", "removed"])
def test_an_opinion_may_be_published_under_review_or_removed(status):
    PostFactory(post_type=PostType.OPINION, status=status)


@pytest.mark.parametrize(
    "status", ["pending", "verified_true", "verified_false", "under_review", "removed"]
)
def test_a_fact_may_have_any_status_but_published(status):
    PostFactory(post_type=PostType.FACT, status=status)


def test_an_emergency_fact_with_an_expiry_is_fine():
    PostFactory(
        fact=True, is_emergency=True, emergency_expires_at=timezone.now() + timedelta(hours=24)
    )


def test_a_post_under_review_needs_the_start_of_its_wait():
    violated("posts_post_review_started_consistent", under_review=True, review_started_at=None)


@pytest.mark.parametrize("status", ["published", "removed"])
def test_a_post_not_under_review_can_not_have_a_review_clock(status):
    violated(
        "posts_post_review_started_consistent",
        status=status,
        review_started_at=timezone.now(),
    )


def test_the_factory_starts_the_clock_of_a_post_made_under_review():
    review = PostFactory(under_review=True)
    assert review.review_started_at == review.created_at
    assert PostFactory().review_started_at is None


def test_the_nullable_columns_default_to_null():
    post = Post.objects.get(pk=PostFactory(fact=True).pk)
    assert post.sources == []
    assert post.flagged_reason is None
    assert post.pre_review_status is None
    assert post.pre_removal_status is None
    assert post.confidence_score is None
    assert post.pipeline_verdict is None
    assert post.verdict_source is None
    assert post.deleted_at is None
    assert post.review_started_at is None
    assert (post.report_count, post.pipeline_attempts, post.is_emergency) == (0, 0, False)


def constraint_and_index_names():
    with connection.cursor() as cursor:
        return set(connection.introspection.get_constraints(cursor, "posts_post"))


@pytest.mark.parametrize(
    "name",
    [
        "posts_post_content_length",
        "posts_post_type_valid",
        "posts_post_status_valid",
        "posts_post_flagged_reason_valid",
        "posts_post_pre_review_status_valid",
        "posts_post_pre_removal_status_valid",
        "posts_post_pipeline_verdict_valid",
        "posts_post_verdict_source_valid",
        "posts_post_opinion_status",
        "posts_post_fact_not_published",
        "posts_post_sources_max",
        "posts_post_sources_fact_only",
        "posts_post_sources_not_empty",
        "posts_post_sources_not_null",
        "posts_post_emergency_fact_only",
        "posts_post_emergency_expiry",
        "posts_post_confidence_range",
        "posts_post_review_started_consistent",
        "posts_status_created_idx",
        "posts_author_created_idx",
        "posts_pending_queue_idx",
        "posts_review_queue_idx",
        "posts_pinned_emerg_idx",
        "posts_recent_idx",
        "posts_search_idx",
    ],
)
def test_every_planned_constraint_and_index_exists(name):
    assert name in constraint_and_index_names()


def test_the_recent_index_is_partial_and_ordered_like_the_feed():
    with connection.cursor() as cursor:
        cursor.execute("SELECT indexdef FROM pg_indexes WHERE indexname = %s", ["posts_recent_idx"])
        (definition,) = cursor.fetchone()
    assert "created_at DESC, id DESC" in definition
    assert "deleted_at IS NULL" in definition
    assert "removed" in definition


def test_search_vector_is_a_stored_generated_column_with_a_gin_index():
    field = Post._meta.get_field("search_vector")
    assert field.generated and field.db_persist
    with connection.cursor() as cursor:
        cursor.execute("SELECT indexdef FROM pg_indexes WHERE indexname = %s", ["posts_search_idx"])
        (definition,) = cursor.fetchone()
    assert "USING gin (search_vector)" in definition


def test_visible_leaves_out_removed_and_deleted_posts():
    shown = PostFactory()
    pending = PostFactory(fact=True)
    review = PostFactory(under_review=True)
    PostFactory(removed=True)
    PostFactory(deleted=True)
    assert set(Post.objects.visible()) == {shown, pending, review}


def test_not_deleted_keeps_removed_posts_but_not_deleted_ones():
    shown = PostFactory()
    removed = PostFactory(removed=True)
    PostFactory(deleted=True)
    PostFactory(removed=True, deleted=True)
    assert set(Post.objects.not_deleted()) == {shown, removed}


def test_for_list_joins_the_author_and_defers_the_pipeline_blob(django_assert_num_queries):
    PostFactory(pipeline_result={"raw": True})
    with django_assert_num_queries(1):
        (post,) = list(Post.objects.for_list())
        assert post.author.username
        assert "pipeline_result" not in post.__dict__
        assert "search_vector" not in post.__dict__


def test_deleting_the_author_deletes_their_posts():
    post = PostFactory()
    post.author.delete()
    assert not Post.objects.filter(pk=post.pk).exists()


def test_deleting_the_moderator_keeps_the_post():
    moderator = VerifiedUserFactory()
    post = PostFactory(moderated_by=moderator)
    moderator.delete()
    post.refresh_from_db()
    assert post.moderated_by is None


def test_str_is_a_short_excerpt():
    assert str(PostFactory(content="Short")) == "Short"
    long = str(PostFactory(content="word " * 40))
    assert len(long) == 60
    assert long.endswith("…")
    assert "\n" not in str(PostFactory(content="a\nb"))


def test_the_status_enum_matches_the_architecture():
    assert set(PostStatus.values) == {
        "pending",
        "published",
        "verified_true",
        "verified_false",
        "under_review",
        "removed",
    }
