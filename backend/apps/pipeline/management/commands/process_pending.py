"""`python manage.py process_pending [--limit N] [--loop] [--interval S]` (ARCHITECTURE §6).

The local-dev sweeper: the same queue the inline kick and the hourly tick use. One run checks every
fact post that is due (in batches of `--limit`) and stops; `--loop` keeps doing that every
`--interval` seconds until Ctrl+C.
"""

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from apps.pipeline.processor import BATCH_SIZE, process_pending


def _plural(count):
    return f"Processed {count} fact post{'' if count == 1 else 's'}."


class Command(BaseCommand):
    help = "Check the fact posts that are waiting for the fact-check pipeline."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=BATCH_SIZE,
            help=f"posts per batch, 1 to 100 (default {BATCH_SIZE})",
        )
        parser.add_argument(
            "--loop", action="store_true", help="keep checking until Ctrl+C instead of stopping"
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=5,
            help="seconds between two runs with --loop, at least 1 (default 5)",
        )

    def handle(self, *args, limit, loop, interval, **options):
        if not 1 <= limit <= 100:
            raise CommandError("--limit must be between 1 and 100")
        if interval < 1:
            raise CommandError("--interval must be at least 1 second")
        if not loop:
            self.stdout.write(_plural(self._drain(limit)))
            return
        self.stdout.write(f"Checking fact posts every {interval} s. Press Ctrl+C to stop.")
        try:
            while True:
                handled = self._drain(limit)
                if handled:
                    self.stdout.write(_plural(handled))
                # A long-running process gets no request cycle to tidy its connection.
                close_old_connections()
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("Stopped.")

    @staticmethod
    def _drain(limit):
        """Batches until one comes back short: everything that was due has been handled (a post
        that failed waits for its backoff, so this always ends)."""
        total = 0
        while True:
            handled = process_pending(limit=limit)
            total += handled
            if handled < limit:
                return total
