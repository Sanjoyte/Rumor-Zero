"""Checking a fact never fetches its sources (ARCHITECTURE §4c, §12): the stub ignores them, and
only the HTTP client (`clients.py`, see `apps/reports/tests/test_no_network.py`) may connect, and
only to `PIPELINE_URL`."""

import pytest

from apps.pipeline import processor
from apps.pipeline.tests.conftest import fact
from apps.posts.models import Post, PostStatus
from apps.posts.tests.test_no_network import blocked  # noqa: F401  (fixture)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("pipeline_cfg")]


def test_checking_a_fact_with_sources_through_the_stub_makes_no_network_request(blocked):  # noqa: F811
    post = fact(
        "A claim with sources #true",
        sources=[
            "https://example.org/report",
            "https://xn--bcher-kva.example/%C3%BCber",
            "10.1038/x",
        ],
    )
    assert processor.process_pending() == 1
    assert Post.objects.get(pk=post.pk).status == PostStatus.VERIFIED_TRUE
    assert blocked == []
