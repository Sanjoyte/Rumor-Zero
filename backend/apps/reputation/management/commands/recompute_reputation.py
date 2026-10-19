"""`python manage.py recompute_reputation [--user <username>] [--check]` (ARCHITECTURE §4a).

The ledger is the truth; `users.reputation_score` and `reputation_sample` are a copy of what it
adds up to. Without `--check` this rebuilds the copy for every account (or one) and says how many
changed. With `--check` it writes nothing and fails on any difference, and it also audits the
ledger itself: each row's `score_after` must follow from the rows before it, a person's rows must
have strictly increasing times, and every reversal must exactly cancel a row of the same person
that isn't a reversal itself.

It works in chunks of 500 accounts, each in a transaction that locks the chunk (`FOR NO KEY
UPDATE`, sorted, as the service does) in both modes, so a write that lands meanwhile can't show up
as a false difference.
"""

from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.reputation import scoring
from apps.reputation.models import EventKind, ReputationEvent
from apps.reputation.services import Totals, totals_for
from apps.social.services import lookup_name

CHUNK = 500


def _plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def _ledger_problems(users):
    """What is wrong inside these users' ledgers (the `--check` audit), as readable lines."""
    by_id = {user.pk: user for user in users}
    rows = (
        ReputationEvent.objects.filter(user_id__in=list(by_id))
        .order_by("user_id", "created_at", "id")
        .values(
            "id",
            "user_id",
            "kind",
            "positive",
            "negative",
            "reverses_id",
            "score_after",
            "created_at",
        )
    )
    rows = list(rows)
    known = {row["id"]: row for row in rows}
    wanted = {row["reverses_id"] for row in rows if row["reverses_id"] not in (None, *known)}
    if wanted:
        others = ReputationEvent.objects.filter(pk__in=wanted).values(
            "id", "user_id", "kind", "positive", "negative"
        )
        known.update({row["id"]: row for row in others})

    problems = []
    running = defaultdict(lambda: [Decimal("0"), Decimal("0"), None])
    for row in rows:
        name = by_id[row["user_id"]].username
        state = running[row["user_id"]]
        state[0] += row["positive"]
        state[1] += row["negative"]
        try:
            expected = scoring.score(state[0], state[1])
        except ValueError:
            expected = None
        if row["score_after"] != expected:
            problems.append(
                f"{name}: row {row['id']} has score_after {row['score_after']}, "
                f"the rows up to it give {expected}"
            )
        if state[2] is not None and row["created_at"] <= state[2]:
            problems.append(f"{name}: row {row['id']} is not later than the row before it")
        state[2] = row["created_at"]
        if row["kind"] != EventKind.REVERSAL:
            continue
        original = known.get(row["reverses_id"])
        if original is None:
            problems.append(f"{name}: reversal {row['id']} cancels a row that doesn't exist")
        elif original["user_id"] != row["user_id"]:
            problems.append(f"{name}: reversal {row['id']} cancels someone else's row")
        elif original["kind"] == EventKind.REVERSAL:
            problems.append(f"{name}: reversal {row['id']} cancels another reversal")
        elif (row["positive"], row["negative"]) != (-original["positive"], -original["negative"]):
            problems.append(f"{name}: reversal {row['id']} doesn't exactly cancel its row")
    return problems


class Command(BaseCommand):
    help = "Rebuild the stored credibility scores from the ledger, or check them (--check)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="only this account (its username)")
        parser.add_argument(
            "--check",
            action="store_true",
            help="write nothing; fail if a stored score or the ledger itself is wrong",
        )

    def handle(self, *args, user=None, check=False, **options):
        if user is not None:
            username = lookup_name(user)
            ids = list(User.objects.filter(username=username).values_list("pk", flat=True))
            if username is None or not ids:
                raise CommandError(f"No account is called {user!r}.")
        else:
            ids = list(User.objects.order_by("pk").values_list("pk", flat=True))

        problems, changed = [], 0
        for start in range(0, len(ids), CHUNK):
            with transaction.atomic():
                users = list(
                    User.objects.select_for_update(no_key=True)
                    .filter(pk__in=ids[start : start + CHUNK])
                    .order_by("pk")
                    .only("pk", "username", "reputation_score", "reputation_sample")
                )
                totals = totals_for([u.pk for u in users])
                stale = []
                for person in users:
                    mine = totals.get(person.pk, Totals())
                    try:
                        expected = (mine.score, mine.sample)
                    except ValueError:
                        # Sums no ledger can reach (a negative total, a weight that isn't a
                        # quarter): nothing sensible to store.
                        problems.append(f"{person.username}: the ledger's sums are impossible")
                        if not check:
                            raise CommandError(problems[-1]) from None
                        continue
                    found = (person.reputation_score, person.reputation_sample)
                    if found != expected:
                        problems.append(
                            f"{person.username}: stored score {found[0]} from {found[1]} counted "
                            f"events, the ledger gives {expected[0]} from {expected[1]}"
                        )
                        person.reputation_score, person.reputation_sample = expected
                        stale.append(person)
                if check:
                    problems.extend(_ledger_problems(users))
                else:
                    User.objects.bulk_update(
                        stale, ["reputation_score", "reputation_sample"], batch_size=CHUNK
                    )
                    changed += len(stale)

        if check:
            if problems:
                raise CommandError(
                    f"{_plural(len(problems), 'problem')} found:\n"
                    + "\n".join(f"  {line}" for line in problems)
                )
            self.stdout.write(
                f"Checked {_plural(len(ids), 'account')}: every stored score matches the ledger."
            )
            return
        self.stdout.write(f"Recomputed {_plural(len(ids), 'account')}: {changed} changed.")
