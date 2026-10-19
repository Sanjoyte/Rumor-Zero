"""Seeded random walks through the real services (ARCHITECTURE §4a; Part 11B acceptance criteria 2
and 5): pipeline results, reports, reposts and their undoing, appeals, every moderator action and
author deletes, in any order the services allow.

After every step the ledger must match each post's state (`pending_changes` is empty). After each
walk:

- `recompute_reputation --check` passes (stored scores, `score_after`, times, reversal pairs);
- every person's stored score and sample equal what an **independent simulator** of the rules
  says, written here from the rules' text rather than from `scoring.changes`;
- each author equals a control author whose posts went straight to their final outcome ("an
  overturned appeal or a restore returns the author to exactly the score they would have had").
"""

import random
from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.db.models import F
from django.utils import timezone

from apps.moderation import rules
from apps.moderation import services as moderation
from apps.moderation.rules import Act
from apps.posts import services as post_services
from apps.posts.models import Post, PostStatus, PostType
from apps.reports import services as report_services
from apps.reports.models import Report, ReportStatus
from apps.reputation import services
from apps.reputation.models import EventKind as K
from apps.reputation.scoring import score
from apps.reputation.tests.factories import (
    FALSE_95,
    LOW_40,
    TRUE_95,
    EventFactory,
    PostFactory,
    VerifiedUserFactory,
    label_by_pipeline,
    moderator_user,
    senior_user,
    stored,
)
from apps.social import services as social_services
from apps.social.models import Repost

pytestmark = pytest.mark.django_db

SEEDS = range(40)
COVERAGE_SEEDS = range(12)  # a subset: enough to reach everything, half the time
STEPS = 40

# The table, written out again for the simulator.
WEIGHT = {
    K.FACT_TRUE: ("1", "0"),
    K.FACT_FALSE: ("0", "1"),
    K.EMERGENCY_FALSE: ("0", "3"),
    K.POST_REMOVED: ("0", "2"),
    K.REPOST_TRUE: ("0.25", "0"),
    K.REPOST_FALSE: ("0", "0.5"),
    K.REPOST_EMERGENCY_FALSE: ("0", "1"),
    K.REPOST_REMOVED: ("0", "0.5"),
    K.REPORT_UPHELD: ("0.25", "0"),
}
UNDECIDED = (PostStatus.PENDING, PostStatus.UNDER_REVIEW)
ACTS = {
    "mark_verified": Act.MARK_VERIFIED,
    "mark_false": Act.MARK_FALSE,
    "dismiss_reports": Act.DISMISS_REPORTS,
    "remove_post": Act.REMOVE,
    "escalate": Act.ESCALATE,
    "restore_post": Act.RESTORE,
    "keep_removed": Act.KEEP_REMOVED,
}


class Simulator:
    """Which outcome rows stand (un-reversed) for whom. A reversal cancels a row exactly, so a
    person's sums are the sums of their standing rows."""

    def __init__(self):
        # (user, post, slot, role) -> kind
        self.standing = {}
        self.refused_by_cap = 0

    def _holders(self, post_id, slot, role):
        return {u for (u, p, s, r) in self.standing if (p, s, r) == (post_id, slot, role)}

    def _drop(self, post_id, slot):
        for key in [k for k in self.standing if k[1:3] == (post_id, slot)]:
            del self.standing[key]

    def _credits(self, user):
        return sum(1 for (u, _, _, r) in self.standing if u == user and r == "reporter")

    def settle(self, post, reposts, *, credited=(), action=None):
        counted = {user for user, status in reposts if status in UNDECIDED}
        if post.status in (PostStatus.VERIFIED_TRUE, PostStatus.VERIFIED_FALSE):
            if post.status == PostStatus.VERIFIED_TRUE:
                mine, theirs = K.FACT_TRUE, K.REPOST_TRUE
            elif post.is_emergency:
                mine, theirs = K.EMERGENCY_FALSE, K.REPOST_EMERGENCY_FALSE
            else:
                mine, theirs = K.FACT_FALSE, K.REPOST_FALSE
            self.standing[(post.author_id, post.pk, "label", "author")] = mine
            for user in self._holders(post.pk, "label", "reposter") | counted:
                self.standing[(user, post.pk, "label", "reposter")] = theirs
            if post.status == PostStatus.VERIFIED_TRUE:
                for user in self._holders(post.pk, "label", "reporter"):
                    del self.standing[(user, post.pk, "label", "reporter")]
            elif action == "marked_false":
                self._credit(credited, post.pk, "label")
        # A review, `pending` or `published` leave the label as it was.
        if post.status == PostStatus.REMOVED:
            self.standing[(post.author_id, post.pk, "removal", "author")] = K.POST_REMOVED
            for user in self._holders(post.pk, "removal", "reposter") | counted:
                self.standing[(user, post.pk, "removal", "reposter")] = K.REPOST_REMOVED
            if action == "removed":
                self._credit(credited, post.pk, "removal")
        else:
            self._drop(post.pk, "removal")

    def _credit(self, reporters, post_id, slot):
        for user in sorted(reporters):
            key = (user, post_id, slot, "reporter")
            if key in self.standing:
                continue
            if self._credits(user) < 4:
                self.standing[key] = K.REPORT_UPHELD
            else:
                self.refused_by_cap += 1

    def expected(self, user):
        p = n = Decimal("0")
        sample = 0
        for (u, _, _, role), kind in self.standing.items():
            if u != user:
                continue
            p += Decimal(WEIGHT[kind][0])
            n += Decimal(WEIGHT[kind][1])
            sample += role == "author"
        return score(p, n), sample

    def author_outcome(self, post_id, author_id):
        label = self.standing.get((author_id, post_id, "label", "author"))
        removed = (author_id, post_id, "removal", "author") in self.standing
        return label, removed


class Walk:
    def __init__(self, seed, pipeline_cfg):
        pipeline_cfg(report_threshold=2)
        self.rng = random.Random(seed)
        self.sim = Simulator()
        old = timezone.now() - timedelta(days=3)  # old enough for their reports to count
        self.authors = [VerifiedUserFactory(created_at=old) for _ in range(2)]
        first, second = self.authors
        expires = timezone.now() + timedelta(hours=24)
        self.posts = [
            PostFactory(author=first, post_type=PostType.FACT, status=PostStatus.PENDING),
            PostFactory(
                author=first,
                post_type=PostType.FACT,
                status=PostStatus.PENDING,
                is_emergency=True,
                emergency_expires_at=expires,
            ),
            PostFactory(author=second, post_type=PostType.FACT, status=PostStatus.PENDING),
            PostFactory(author=second, post_type=PostType.OPINION, status=PostStatus.PUBLISHED),
        ]
        self.people = [VerifiedUserFactory(created_at=old) for _ in range(4)]
        # Two of them already hold credits from last week (3 and 4), so the cap is reached and
        # then refuses within a walk.
        for person, held in zip(self.people, (3, 4), strict=False):
            self._earlier_credits(person, held)
        self.moderators = [moderator_user(created_at=old) for _ in range(3)]
        self.moderators.append(senior_user(created_at=old))
        self.log = []

    def _earlier_credits(self, person, count):
        start = timezone.now() - timedelta(days=7)
        for i in range(count):
            EventFactory(
                user=person,
                kind=K.REPORT_UPHELD,
                score_after=score(Decimal("0.25") * (i + 1), 0),
                created_at=start + timedelta(minutes=i),
            )
            self.sim.standing[(person.pk, f"earlier-{i}", "earlier", "reporter")] = K.REPORT_UPHELD
        call_command("recompute_reputation", "--user", person.username, stdout=StringIO())

    def post(self):
        return Post.objects.get(pk=self.rng.choice(self.posts).pk)

    def reposts(self, post):
        return list(Repost.objects.filter(post=post).values_list("user_id", "status_at_repost"))

    # ---- steps ----

    def pipeline(self):
        post = self.post()
        Post.objects.filter(pk=post.pk).update(
            pipeline_attempts=F("pipeline_attempts") + 1,
            pipeline_next_attempt_at=timezone.now() + timedelta(minutes=5),
        )
        attempts = Post.objects.values_list("pipeline_attempts", flat=True).get(pk=post.pk)
        result = self.rng.choice([TRUE_95, FALSE_95, LOW_40])
        outcome = post_services.record_pipeline_result(
            post.pk, result, claimed_attempts=attempts, now=timezone.now()
        )
        self.log.append(("pipeline", post.content, result.verdict, outcome))
        return post, {}

    def report(self):
        post = self.post()
        reporter = self.rng.choice(self.people + self.moderators)
        try:
            report_services.file_report(
                reporter=reporter, post_id=post.pk, reason="inaccurate", details=""
            )
        except (
            report_services.PostNotFound,
            report_services.CannotReportOwn,
            report_services.AlreadyReported,
        ):
            return post, {}
        self.log.append(("report", post.content, reporter.username))
        return post, {}

    def repost(self):
        post = self.post()
        person = self.rng.choice(self.people + self.moderators)
        try:
            social_services.repost(user=person, post_id=post.pk)
        except (
            social_services.PostNotFound,
            social_services.CannotRepostOwn,
            social_services.CannotRepostFalse,
        ):
            return post, {}
        self.log.append(("repost", post.content, person.username))
        return post, {}

    def unrepost(self):
        post = self.post()
        person = self.rng.choice(self.people + self.moderators)
        social_services.unrepost(user=person, post_id=post.pk)
        self.log.append(("unrepost", post.content, person.username))
        return post, {}

    def act(self):
        post = self.post()
        moderator = self.rng.choice(self.moderators)
        appeal = moderation.open_appeal(post)
        allowed = [
            name
            for name, act in ACTS.items()
            if rules.refusal(act, post, moderator, appeal=appeal) is None
        ]
        # Mostly something the rules allow (or the walk would hardly ever decide anything), and
        # sometimes anything at all, which the service must refuse without writing.
        if allowed and self.rng.random() < 0.85:
            name = self.rng.choice(allowed)
        else:
            name = self.rng.choice(list(ACTS))
        reporters = set(
            Report.objects.filter(post=post, status=ReportStatus.OPEN).values_list(
                "reporter_id", flat=True
            )
        )
        was = post.pre_review_status
        try:
            getattr(moderation, name)(post.pk, moderator=moderator)
        except moderation.ActionRefused:
            return post, {}
        self.log.append((name, post.content, moderator.username))
        # Written from the rules' text (user decisions 5 and 8).
        if name == "remove_post" or (name == "mark_false" and was != PostStatus.VERIFIED_FALSE):
            action = "removed" if name == "remove_post" else "marked_false"
            return post, {"credited": reporters - {moderator.pk}, "action": action}
        return post, {}

    def appeal(self):
        post = self.post()
        try:
            moderation.file_appeal(author=post.author, post_id=post.pk)
        except (
            moderation.AlreadyAppealed,
            moderation.NotAppealable,
            post_services.PostNotFound,
        ):
            return post, {}
        self.log.append(("appeal", post.content))
        return post, {}

    def delete(self):
        post = self.post()
        try:
            post_services.delete_post(post_id=post.pk, user=post.author)
        except post_services.PostNotFound:
            return post, {}
        self.log.append(("delete", post.content))
        return post, {}

    STEP_WEIGHTS = {
        "pipeline": 4,
        "report": 6,
        "repost": 7,
        "unrepost": 2,
        "act": 9,
        "appeal": 3,
        "delete": 0.3,
    }

    def run(self, steps):
        names = list(self.STEP_WEIGHTS)
        weights = list(self.STEP_WEIGHTS.values())
        for _ in range(steps):
            step = self.rng.choices(names, weights)[0]
            post, extra = getattr(self, step)()
            post = Post.objects.get(pk=post.pk)
            self.sim.settle(post, self.reposts(post), **extra)
            for each in Post.objects.filter(pk__in=[p.pk for p in self.posts]):
                assert not services.pending_changes(each), (self.log, each.content)

    def everyone(self):
        return [*self.authors, *self.people, *self.moderators]


def control_for(author, posts, sim):
    """A fresh author whose posts went straight to the walk's final (label, removal) pair."""
    control = VerifiedUserFactory()
    for post in posts:
        label, removed = sim.author_outcome(post.pk, author.pk)
        copy = PostFactory(
            author=control,
            post_type=post.post_type,
            status=PostStatus.PENDING if post.post_type == PostType.FACT else PostStatus.PUBLISHED,
            is_emergency=post.is_emergency,
            emergency_expires_at=post.emergency_expires_at,
        )
        if label is not None:
            label_by_pipeline(copy, TRUE_95 if label == K.FACT_TRUE else FALSE_95)
        if removed:
            moderation.remove_post(copy.pk, moderator=moderator_user())
    return control


@pytest.mark.parametrize("seed", SEEDS)
def test_a_random_walk_keeps_the_ledger_exact(seed, pipeline_cfg):
    walk = Walk(seed, pipeline_cfg)
    walk.run(STEPS)

    call_command("recompute_reputation", "--check", stdout=StringIO())
    for person in walk.everyone():
        assert stored(person) == walk.sim.expected(person.pk), (person.username, walk.log)
    for author in walk.authors:
        mine = [post for post in walk.posts if post.author_id == author.pk]
        control = control_for(author, mine, walk.sim)
        assert stored(control) == stored(author), walk.log


def test_the_walks_reach_every_kind_of_event_and_the_cap(pipeline_cfg):
    """The walks are only worth something if they go everywhere: every event kind is written
    (reversals included), and the cap both gives a fourth credit and refuses a fifth."""
    from apps.reputation.models import ReputationEvent

    seen = set()
    refused = 0
    for seed in COVERAGE_SEEDS:
        walk = Walk(seed, pipeline_cfg)
        walk.run(STEPS)
        seen |= set(ReputationEvent.objects.values_list("kind", flat=True))
        refused += walk.sim.refused_by_cap
    assert seen == set(K)
    assert refused > 0
