"""The fact-check queue (ARCHITECTURE §6; ANALYSIS c-21): the `posts` table is the queue, and no
worker or Celery runs it. Three triggers: the inline kick after a fact post commits
(`start_kick`), the hourly secret-protected tick, and `manage.py process_pending`.

One post at a time, in three steps, so the post's row is never locked while the pipeline thinks
(up to 20 s; reports, reposts, deletes and moderators would queue behind it):

1. **Claim** (a short transaction): lock the next due post, count the try in `pipeline_attempts`
   (that number is the claim's token) and lease it: `pipeline_next_attempt_at = now + LEASE`, so
   no other processor takes it meanwhile. A process that dies mid-call leaves the post due again
   when the lease ends, with the try already counted, so a crashing post still ends at
   `MAX_ATTEMPTS`.
2. **Call** the client, outside any transaction.
3. **Apply** through `posts.services.record_pipeline_result` / `record_pipeline_failure`, which
   drop the answer if the post was deleted or claimed again since (a stale token).
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import timedelta

from django.db import connections, transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from apps.pipeline import routing
from apps.pipeline.clients import PipelineError, get_client
from apps.pipeline.contract import ContractError, PipelineRequest
from apps.posts import services as post_services
from apps.posts.emergency import active_emergency_q
from apps.posts.models import Post

logger = logging.getLogger(__name__)

BATCH_SIZE = 10  # posts per tick (§3)
LEASE = timedelta(minutes=5)  # far above the worst call (20 s), so a lease ends only on a crash
KICK_THREAD_NAME = "pipeline-kick"
MAX_KICK_THREADS = 4  # per process; past that a post waits for the sweeper
_kick_slots = threading.BoundedSemaphore(MAX_KICK_THREADS)


def due_posts(now):
    """The queue: posts still owed a check (`routing.awaiting_check_q`) whose next try is due,
    **active emergencies first** (§4b: an expired or demoted one waits its turn), then oldest."""
    due = Q(pipeline_next_attempt_at__isnull=True) | Q(pipeline_next_attempt_at__lte=now)
    emergency_first = Case(
        When(active_emergency_q(now), then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )
    return (
        Post.objects.filter(routing.awaiting_check_q())
        .filter(due)
        .order_by(emergency_first.desc(), "created_at", "id")
    )


@dataclass(frozen=True)
class Claim:
    post: Post  # only what the request needs: id, content, sources
    attempts: int  # the token: `pipeline_attempts` after this claim
    exhausted: bool  # every earlier try died mid-call: give up without calling again


def claim_next(now, *, post_id=None):
    """Lease the next due post (or the post `post_id`, if it is due) for one try, or None.

    The sweeper skips rows other transactions hold (`SKIP LOCKED`), so two processors never wait
    for each other or take the same post. The kick (`post_id`) waits for the lock instead: a
    report or a repost holds the row for a moment, and skipping would leave the new post to the
    hourly tick. `pipeline_attempts` already at `MAX_ATTEMPTS` means every earlier try died: the
    post is leased without counting again and given up at once (`Claim.exhausted`).
    """
    with transaction.atomic(durable=True):
        query = due_posts(now).only(
            "id", "content", "sources", "pipeline_attempts", "pipeline_next_attempt_at"
        )
        if post_id is None:
            query = query.select_for_update(no_key=True, skip_locked=True, of=("self",))
        else:
            query = query.filter(pk=post_id).select_for_update(no_key=True, of=("self",))
        post = query.first()
        if post is None:
            return None
        exhausted = post.pipeline_attempts >= routing.MAX_ATTEMPTS
        if not exhausted:
            post.pipeline_attempts += 1
        post.pipeline_next_attempt_at = now + LEASE
        # Bookkeeping only: `updated_at` moves when the post itself changes (apply).
        post.save(update_fields=["pipeline_attempts", "pipeline_next_attempt_at"])
        return Claim(post=post, attempts=post.pipeline_attempts, exhausted=exhausted)


def _as_error(exc):
    if isinstance(exc, PipelineError):
        return exc
    if isinstance(exc, ContractError):
        return PipelineError("contract", str(exc))
    # Only the class: an unexpected message could hold anything.
    return PipelineError("error", type(exc).__name__)


def _try(claim, client, now):
    """Call the client for a claimed post and write what happened. Returns the `Outcome`, or None
    when the answer was dropped."""
    post_id = claim.post.pk
    if claim.exhausted:
        error = PipelineError("lease_expired", "the last try never finished")
        outcome = post_services.record_pipeline_failure(
            post_id, error, claimed_attempts=claim.attempts, now=now or timezone.now()
        )
        logger.error(
            "Pipeline: post %s given up after %s tries (%s)", post_id, claim.attempts, error
        )
        return outcome
    try:
        # Building the request is part of the try: a row the contract refuses is a failed try.
        result = client.check(PipelineRequest.for_post(claim.post))
    except Exception as exc:  # every failure is a failed try, retried or given up
        error = _as_error(exc)
        outcome = post_services.record_pipeline_failure(
            post_id, error, claimed_attempts=claim.attempts, now=now or timezone.now()
        )
        if outcome == routing.Outcome.RETRY:
            logger.warning(
                "Pipeline: post %s, try %s failed (%s)", post_id, claim.attempts, error.kind
            )
        elif outcome in (routing.Outcome.ENTERED_REVIEW, routing.Outcome.UPDATED_REVIEW):
            logger.error(
                "Pipeline: post %s given up after %s tries (%s)",
                post_id,
                claim.attempts,
                error.kind,
            )
        else:
            logger.info("Pipeline: post %s, failed try not recorded (%s)", post_id, outcome)
        return outcome
    outcome = post_services.record_pipeline_result(
        post_id, result, claimed_attempts=claim.attempts, now=now or timezone.now()
    )
    logger.info("Pipeline: post %s -> %s", post_id, outcome or "dropped")
    return outcome


def process_pending(*, limit=BATCH_SIZE, now=None, client=None, deadline=None):
    """Check up to `limit` due posts, one at a time. Returns how many were handled.

    `deadline` (a `time.monotonic()` value) is for the tick: the first post is always taken, and
    another only if the worst case (`client.max_seconds`) still ends before it. The stub takes no
    time, so it always does `limit`; a real pipeline does fewer. One post that fails in an
    unexpected way is logged and skipped (its lease brings it back); a failing claim ends the run.
    `now` is for tests: by default each step reads the clock.
    """
    client = client or get_client()
    handled = 0
    while handled < limit:
        if handled and deadline is not None and time.monotonic() + client.max_seconds > deadline:
            break
        claim = claim_next(now or timezone.now())
        if claim is None:
            break
        handled += 1
        try:
            _try(claim, client, now)
        except Exception:
            logger.exception("Pipeline: post %s could not be handled; it comes back", claim.post.pk)
    return handled


def process_post(post_id, *, now=None, client=None):
    """Check one post if it is due (the kick). Returns True when it was handled."""
    client = client or get_client()
    claim = claim_next(now or timezone.now(), post_id=post_id)
    if claim is None:
        return False
    _try(claim, client, now)
    return True


def _run_kick(post_id):
    try:
        process_post(post_id)
    except Exception:
        logger.exception(
            "Pipeline: the inline check of post %s failed; the sweeper retries", post_id
        )
    finally:
        _kick_slots.release()
        connections.close_all()  # this thread's connections only


def start_kick(post_id):
    """Check a new fact post in a background thread (the inline kick, run after the commit).

    A daemon thread, at most `MAX_KICK_THREADS` per process: when all are busy nothing starts and
    the sweeper takes the post. Returns the thread (tests join it), or None.
    """
    if not _kick_slots.acquire(blocking=False):
        logger.info(
            "Pipeline: %s checks running; post %s waits for the sweeper", MAX_KICK_THREADS, post_id
        )
        return None
    thread = threading.Thread(target=_run_kick, args=(post_id,), name=KICK_THREAD_NAME, daemon=True)
    try:
        thread.start()
    except BaseException:
        _kick_slots.release()
        raise
    return thread
