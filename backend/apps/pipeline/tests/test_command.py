"""`manage.py process_pending` (ARCHITECTURE §6): the local-dev sweeper."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.pipeline.management.commands import process_pending as command
from apps.pipeline.tests.conftest import fact
from apps.posts.models import Post, PostStatus

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("pipeline_cfg")]


def run(*args):
    out = StringIO()
    call_command("process_pending", *args, stdout=out)
    return out.getvalue()


def test_one_run_clears_the_whole_backlog_in_batches():
    posts = [fact(f"Claim {n} #true", age_seconds=100 - n) for n in range(12)]
    assert run() == "Processed 12 fact posts.\n"
    statuses = Post.objects.filter(pk__in=[p.pk for p in posts]).values_list("status", flat=True)
    assert set(statuses) == {PostStatus.VERIFIED_TRUE}
    assert run() == "Processed 0 fact posts.\n"


def test_a_smaller_batch_still_clears_everything():
    for n in range(5):
        fact(f"Claim {n} #false", age_seconds=100 - n)
    assert run("--limit", "2") == "Processed 5 fact posts.\n"


def test_one_post_is_singular():
    fact("Claim #unsure")
    assert run() == "Processed 1 fact post.\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--limit", "0"], "--limit must be between 1 and 100"),
        (["--limit", "101"], "--limit must be between 1 and 100"),
        (["--loop", "--interval", "0"], "--interval must be at least 1 second"),
    ],
)
def test_bad_options_are_refused(args, message):
    with pytest.raises(CommandError, match=message):
        run(*args)


def test_loop_checks_every_interval_until_ctrl_c(monkeypatch):
    fact("First claim #true", age_seconds=10)
    sleeps, cleanups = [], []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 1:
            fact("Second claim #false", age_seconds=1)  # arrives while the loop waits
            return
        raise KeyboardInterrupt

    monkeypatch.setattr(command.time, "sleep", sleep)
    monkeypatch.setattr(command, "close_old_connections", lambda: cleanups.append(True))
    assert run("--loop", "--interval", "3").splitlines() == [
        "Checking fact posts every 3 s. Press Ctrl+C to stop.",
        "Processed 1 fact post.",
        "Processed 1 fact post.",
        "Stopped.",
    ]
    assert sleeps == [3, 3]
    assert len(cleanups) == 2
    assert set(Post.objects.values_list("status", flat=True)) == {
        PostStatus.VERIFIED_TRUE,
        PostStatus.VERIFIED_FALSE,
    }
