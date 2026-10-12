"""The five moderator actions on a post (ARCHITECTURE §4, §8). Only this module and
`apps/posts/services.py` change `Post.status`.

Each service runs in one `transaction.atomic()` and does the same five things:

1. lock the post row with `FOR NO KEY UPDATE`, the lock reports, reposts and the pipeline's apply
   use, so a report or a pipeline answer that arrives meanwhile waits and then sees the new state;
2. re-check `rules.refusal` against the locked row (the screen the moderator saw may be old);
3. apply `rules.transition` and save exactly those fields;
4. resolve the post's open reports through `reports.services.resolve_open_reports`;
5. append the `ModerationAction`.

A refusal raises `ActionRefused` and writes nothing. There is no HTTP here: the admin turns the
exception into a message. Part 11B adds the reputation calls and Part 13 the notifications, in this
same transaction.
"""

from django.db import transaction
from django.utils import timezone

from apps.moderation import rules
from apps.moderation.models import ModerationAction
from apps.posts.models import Post
from apps.reports import services as report_services

# Exactly what `rules.transition` can change, plus `updated_at` (auto_now needs to be listed).
_SAVED_FIELDS = [
    "status",
    "flagged_reason",
    "pre_review_status",
    "pre_removal_status",
    "review_started_at",
    "escalated_at",
    "verdict_source",
    "verdict_note",
    "moderated_by",
    "moderated_at",
    "updated_at",
]


class ActionRefused(Exception):
    """The action isn't allowed on this post (see `rules.refusal`): nothing was written."""

    def __init__(self, refusal):
        super().__init__(refusal.text)
        self.refusal = refusal


def _perform(act, post_id, *, moderator, notes, public_note, now):
    with transaction.atomic():
        post = (
            Post.objects.select_for_update(no_key=True, of=("self",))
            .defer("pipeline_result")
            .filter(pk=post_id)
            .first()
        )
        # After the lock, not before: a moderator who waited stamps a later time than the one
        # whose change they saw, so the audit trail's order is the order things really happened.
        now = now or timezone.now()
        if post is None:
            # Not a post at all (a stale id): the same refusal as a post its author deleted.
            raise ActionRefused(rules.DELETED)
        refusal = rules.refusal(act, post, moderator)
        if refusal is not None:
            raise ActionRefused(refusal)
        effect = rules.transition(act, post, moderator=moderator, now=now, public_note=public_note)
        post.save(update_fields=_SAVED_FIELDS)
        if effect.report_status is not None:
            report_services.resolve_open_reports(
                post, status=effect.report_status, moderator=moderator, now=now
            )
        return ModerationAction.objects.create(
            post=post,
            post_snapshot=post.content,
            moderator=moderator,
            action=effect.kind,
            from_status=effect.from_status,
            to_status=effect.to_status,
            public_note=public_note,
            notes=notes,
            created_at=now,
        )


def mark_verified(post_id, *, moderator, notes="", public_note="", now=None):
    """A fact under review is true: `verified_true`, `verdict_source=moderator`. `public_note`
    becomes the post's `verdict_note` (blank clears it). Open reports become `actioned`."""
    return _perform(
        rules.Act.MARK_VERIFIED,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note=public_note,
        now=now,
    )


def mark_false(post_id, *, moderator, notes="", public_note="", now=None):
    """A fact under review is FALSE: `verified_false`, `verdict_source=moderator`, as above."""
    return _perform(
        rules.Act.MARK_FALSE,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note=public_note,
        now=now,
    )


def dismiss_reports(post_id, *, moderator, notes="", now=None):
    """The reports were not enough: a post flagged only by reports goes back to the status it had;
    one also flagged by the pipeline stays under review for the pipeline. Open reports become
    `dismissed` and never count again."""
    return _perform(
        rules.Act.DISMISS_REPORTS,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note="",
        now=now,
    )


def remove_post(post_id, *, moderator, notes="", public_note="", now=None):
    """Take the post down. Its status before review (or its current one) is kept in
    `pre_removal_status`. `public_note` is the reason shown to the author; it lives on the audit
    row only, never in `Post.verdict_note`. Open reports become `actioned`."""
    return _perform(
        rules.Act.REMOVE,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note=public_note,
        now=now,
    )


def escalate(post_id, *, moderator, notes="", now=None):
    """Mark a post under review for a senior moderator (`escalated_at`). It never locks the post:
    any moderator can still act on it."""
    return _perform(
        rules.Act.ESCALATE,
        post_id,
        moderator=moderator,
        notes=notes,
        public_note="",
        now=now,
    )
