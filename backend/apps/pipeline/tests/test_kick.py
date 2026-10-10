"""The inline kick (ARCHITECTURE §6): after a fact post commits, a daemon thread checks it. It
never turns a saved post into an error, never outlives its work, and gives way when busy."""

import logging
import threading

import pytest
from django.db import connection, transaction

from apps.pipeline import processor
from apps.posts import services as post_services
from apps.posts.models import Post, PostStatus, PostType
from apps.posts.tests.conftest import auth_client, fact_limit  # noqa: F401  (fixtures)
from apps.posts.tests.factories import VerifiedUserFactory

db = pytest.mark.django_db
transactional = pytest.mark.django_db(transaction=True)
pytestmark = pytest.mark.usefixtures("pipeline_cfg", "fact_limit")


@pytest.fixture
def kicks(monkeypatch, settings):
    """Turn the kick on and record the posts it is started for (no thread is started)."""
    settings.PIPELINE_INLINE_KICK = True
    started = []
    monkeypatch.setattr(processor, "start_kick", started.append)
    return started


def create(post_type=PostType.FACT, content="A claim #true", author=None):
    return post_services.create_post(
        author=author or VerifiedUserFactory(), content=content, post_type=post_type
    )


@db
def test_a_fact_is_kicked_once_after_its_commit(kicks, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        post = create()
        assert kicks == []  # not before the commit
    assert kicks == [post.pk]


@db
def test_an_opinion_is_never_kicked(kicks, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        create(PostType.OPINION, "Just my view")
    assert kicks == []


@db
def test_nothing_is_kicked_with_the_setting_off(
    kicks, settings, django_capture_on_commit_callbacks
):
    settings.PIPELINE_INLINE_KICK = False
    with django_capture_on_commit_callbacks(execute=True):
        create()
    assert kicks == []


@db
def test_a_post_whose_transaction_rolls_back_is_never_kicked(
    kicks, django_capture_on_commit_callbacks
):
    class Boom(Exception):
        pass

    with (
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(Boom),
        transaction.atomic(),
    ):
        create()
        raise Boom
    assert kicks == []
    assert not Post.objects.exists()


@db
def test_a_kick_that_cannot_start_is_logged_and_never_raised(
    monkeypatch, settings, caplog, django_capture_on_commit_callbacks
):
    settings.PIPELINE_INLINE_KICK = True

    def cannot_start(post_id):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(processor, "start_kick", cannot_start)
    with caplog.at_level(logging.ERROR), django_capture_on_commit_callbacks(execute=True):
        post = create()
    assert Post.objects.filter(pk=post.pk).exists()
    assert "Could not start the inline pipeline check" in caplog.text


@transactional
def test_through_the_api_a_kick_that_cannot_start_still_answers_201_once(
    monkeypatch,
    settings,
    auth_client,  # noqa: F811
):
    """A real commit: the callback runs inside the request, so an error escaping it would be a
    500 for a post that is saved, and the client would post it again."""
    settings.PIPELINE_INLINE_KICK = True

    def cannot_start(post_id):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(processor, "start_kick", cannot_start)
    author = VerifiedUserFactory()
    response = auth_client(author).post(
        "/api/v1/posts/", {"content": "A claim #true", "post_type": "fact"}, format="json"
    )
    assert response.status_code == 201
    assert Post.objects.filter(author=author).count() == 1


@pytest.fixture
def started_threads(monkeypatch):
    """Let the real kick run, keeping its threads so the test can join them."""
    real = processor.start_kick
    threads = []

    def keep(post_id):
        thread = real(post_id)
        threads.append(thread)
        return thread

    monkeypatch.setattr(processor, "start_kick", keep)
    return threads


@transactional
def test_a_new_fact_is_checked_in_a_daemon_thread_that_closes_its_connection(
    settings, started_threads, monkeypatch
):
    settings.PIPELINE_INLINE_KICK = True
    closed = []
    real_close_all = processor.connections.close_all

    def close_all():
        real_close_all()
        closed.append((threading.current_thread().name, connection.connection is None))

    monkeypatch.setattr(processor.connections, "close_all", close_all)
    post = create(content="Paris is in France #true")
    [thread] = started_threads
    thread.join(timeout=30)
    assert thread.daemon
    assert thread.name == "pipeline-kick"
    assert closed == [("pipeline-kick", True)]
    after = Post.objects.get(pk=post.pk)
    assert (after.status, after.verdict_source) == (PostStatus.VERIFIED_TRUE, "pipeline")


@transactional
def test_an_error_inside_the_thread_is_logged_and_the_slot_is_freed(
    settings, started_threads, monkeypatch, caplog
):
    settings.PIPELINE_INLINE_KICK = True

    def broken(post_id, **kwargs):
        raise RuntimeError("pipeline exploded")

    monkeypatch.setattr(processor, "process_post", broken)
    with caplog.at_level(logging.ERROR):
        post = create()
        started_threads[0].join(timeout=30)
    assert "inline check of post" in caplog.text
    assert Post.objects.get(pk=post.pk).status == PostStatus.PENDING  # the sweeper retries it
    assert all(processor._kick_slots.acquire(blocking=False) for _ in range(4))
    for _ in range(4):
        processor._kick_slots.release()


def test_no_thread_starts_while_every_slot_is_busy(caplog):
    taken = [processor._kick_slots.acquire(blocking=False) for _ in range(4)]
    try:
        assert taken == [True] * 4
        with caplog.at_level(logging.INFO):
            assert processor.start_kick("any-post-id") is None
        assert "waits for the sweeper" in caplog.text
    finally:
        for _ in range(4):
            processor._kick_slots.release()


def test_a_thread_that_fails_to_start_gives_its_slot_back(monkeypatch):
    def refuse(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Thread, "start", refuse)
    with pytest.raises(RuntimeError):
        processor.start_kick("any-post-id")
    taken = [processor._kick_slots.acquire(blocking=False) for _ in range(4)]
    for _ in range(sum(taken)):
        processor._kick_slots.release()
    assert taken == [True] * 4
