# Plan: pre-Part-0A fixes for five reported issues

- **Status:** APPROVED, **done** 2026-09-30 (steps 1–7 executed; results in `docs/agents/HANDOFF.md`).
- **Drafted:** 2026-09-30 by Claude (Opus 5.5). **Approved:** 2026-09-30 by the user (Sanjoyte).
- **Part:** none. This is a correction pass on the Part 0A/0C specs and shared docs, plus one repo file
  (`.gitattributes`) and a byte repair of one working-tree file. Part 0A itself is **not** implemented.
- **Depends on:** nothing.

## Verification results (2026-09-30, read-only)

| # | Issue | Verdict | Evidence |
|---|---|---|---|
| 1 | PDF corrupted by line-ending conversion | **Real, but reversed.** The committed blob is intact; the **working copy** is corrupted. | Blob 554,315 B, LF only, `startxref 548654` points at `xref`. Working copy 556,226 B = 1,911 CRLF, 0 lone LF/CR, `startxref` points into stream data. `git ls-files --eol` → `i/lf w/crlf attr/`. Cause: `C:\Program Files\Git\etc\gitconfig` sets `core.autocrlf = true`, and this ReportLab PDF (ASCII85 + Flate, no NULs, all printable) passes git's text heuristic, so checkout inserted CRs. |
| 1b | Would `* text=auto eol=lf` repeat it? | **Not for this file, but yes in general.** | `eol=lf` writes LF on checkout, which happens to be this PDF's correct bytes. But `text=auto` uses the same heuristic, which calls this PDF text, so any text-looking binary that contains CRLF would be altered at `git add`. Marking binary types removes the dependence on the heuristic. |
| 2 | `is_staff = role != user` locks out the superuser | **Real.** | `docs/ARCHITECTURE.md:74`, `docs/ANALYSIS.md:334`. `createsuperuser` leaves `role = user`, so a literal on-save sync sets `is_staff = False`, and Django Admin requires `is_staff`. `ENV_GUIDE.md:320` has the user log in to Admin right after `createsuperuser`. |
| 3 | X-RZ headers sent to Sentry | **Real, plus two more leaks.** | sentry-python tag 2.71.0 (latest on PyPI): `SENSITIVE_ENV_KEYS` strips only Authorization, Proxy-Authorization, Cookie, Set-Cookie, X-Forwarded-For, X-Real-IP, X-Api-Key. `EventScrubber` matches **exact** lowercase keys, so `x-rz-proxy-secret`, `x-rz-cron-secret` and `x-rz-client-ip` get through. The substring-matching `data_collection` path runs only if that option is passed explicitly. By default, request bodies ≤ 10 KB (`max_request_body_size="medium"`) and frame locals (`include_local_variables=True`) are also sent, so allauth's `key` and `email` body fields get through. `ENV_GUIDE.md:263` currently says the code "never sends passwords or tokens". |
| 4 | Generated code fails `ruff format --check` | **Real.** The cause is mostly quote style, not only line length. | Django 5.2 `settings.py-tpl` and `apps.py-tpl` use single quotes. `MigrationWriter` output is single-quoted with lines over 100 characters. `django/core/management/utils.py` `run_formatters` runs **black only**, and black isn't a dependency (SETUP B2). Checked against the source; the commands themselves were not run, because nothing is scaffolded yet. |
| 5 | `startapp core apps/core` needs the folder and `name = "apps.core"` | **Real.** | Django 5.2 `TemplateCommand.handle` raises "Destination directory … does not exist, please create it first." The `apps.py-tpl` writes `name = '{{ app_name }}'`, i.e. `core`. |
| 5b | Tests depending on the real `backend/.env` fail in CI | **Real gap.** | Part 0A depends on `backend/.env` existing (`task.md:132`). The CI env file is mentioned only for E2E (`task.md:334`), not for the backend job (`task.md:337`). |

## User decisions (2026-09-30)

- #1: create `.gitattributes` now, and Claude repairs the working-copy PDF with a hash check against HEAD
  (no git commands).
- #4: format generated code with ruff straight after generation. Migrations stay in ruff's scope.
- #3: besides the header denylist, also set `max_request_body_size="never"` and
  `include_local_variables=False`.

## Files to change

- `.gitattributes` (new, repo root)
- `docs/fact-based-social-platform-architecture-guide.pdf` (working-copy bytes only; the git content stays the same)
- `task.md`: Part 0A setup, files, settings, acceptance and tests; Part 0C backend scope and CI
- `docs/ARCHITECTURE.md`: §2 role row, §11 testing, §12 security table
- `docs/ANALYSIS.md`: c-10
- `docs/ENV_GUIDE.md`: §2.5 gotcha
- `docs/STRUCTURE.md`: `.gitattributes` row, `apps/` row
- `AGENTS.md`: Commands block and Backend conventions (the generated-code rule)
- `docs/agents/MEMORY.md`: two entries
- `docs/agents/HANDOFF.md`

## Ordered steps

1. **`.gitattributes`** (root):
   ```gitattributes
   * text=auto eol=lf
   *.pdf   binary
   *.png   binary
   *.jpg   binary
   *.jpeg  binary
   *.gif   binary
   *.webp  binary
   *.ico   binary
   *.woff  binary
   *.woff2 binary
   ```
   Every text file in the index is already LF (verified), so this creates no index changes. The 25
   working-tree text files that currently have CRLF are left alone.
2. **Repair the PDF working copy.** Using a Python one-off, first assert exactly 1,911 `\r\n`, 0 lone
   `\n` and 0 lone `\r`. Then replace `\r\n` with `\n` and write the file back. Verify that
   `git hash-object --no-filters <pdf>` equals `git rev-parse HEAD:<pdf>`, that the size is 554,315,
   and that `startxref` lands on `xref`. **Stop condition:** if any assertion fails, don't write the
   file; report it and suggest `git restore <pdf>` for the user to run.
3. **Issue 2 (is_staff):**
   - ARCHITECTURE §2 role row: `is_staff = is_superuser or role != user`. Add that `createsuperuser`
     leaves `role = user` and the superuser keeps Admin access through `is_superuser`.
   - ANALYSIS c-10: same rule.
   - `task.md` 0A acceptance: `createsuperuser` works **and that account can log into Django Admin**,
     and a superuser never loses `is_staff`.
   - Required tests: add "superuser keeps `is_staff` with `role = user` and after role changes".
4. **Issue 3 (Sentry):**
   - `task.md` 0A settings bullet: Sentry initialised only if `SENTRY_DSN` is set, with
     `send_default_pii=False`, `max_request_body_size="never"`, `include_local_variables=False` and
     `event_scrubber=EventScrubber(denylist=DEFAULT_DENYLIST + ["x-rz-proxy-secret",
     "x-rz-cron-secret", "x-rz-client-ip"])`.
   - Required test: a Sentry-shaped event whose headers are `X-Rz-Proxy-Secret`, `X-Rz-Cron-Secret`
     and `X-Rz-Client-Ip` comes out scrubbed, and the init options are set. No DSN or network needed.
   - ARCHITECTURE §12: add an "Error reports (Sentry)" row with the same rules.
   - ENV_GUIDE §2.5: replace the "never sends passwords or tokens (`send_default_pii=False`)" line
     with an accurate one that points to §12.
5. **Issue 4 (generated code):**
   - AGENTS.md backend conventions: after `startproject`, `startapp` and every `makemigrations`, run
     `ruff check --fix . ; ruff format .`, then commit the formatted files. Django only runs black,
     which we don't install. Don't exclude migrations from ruff.
   - Add the same step as a comment in the AGENTS Commands block, and in the `task.md` 0A setup
     commands.
6. **Issue 5 (startapp, env):**
   - `task.md` 0A setup and STRUCTURE `apps/` row: create `apps/__init__.py` and the empty
     `apps\<name>` folder first, run `python manage.py startapp <name> apps/<name>`, then set
     `name = "apps.<name>"` in its `apps.py`. This applies to every later app too.
   - `task.md` 0A settings: `backend/.env` is optional. It is loaded only if present (process env
     wins), and a missing required variable fails by **name** (never its value). Tests never depend
     on the developer's real `.env`; they set what they need through the `settings` fixture or
     `monkeypatch`.
   - ARCHITECTURE §11: a one-line "tests are hermetic" rule.
   - `task.md` 0C backend CI job: build `backend/.env` from `backend/.env.example` (test values
     only), with the Postgres service using the example's user, password and database.
7. **Records:**
   - MEMORY.md: (a) Git for Windows `autocrlf=true` combined with text-looking binaries, and the rule
     that every new binary type goes into `.gitattributes`; (b) sentry-sdk 2.71.0's default scrubbing
     facts, to re-check on any upgrade (Part 17).
   - HANDOFF.md: changed files, validation results, next action.

## Validation

- `git ls-files --eol docs/fact-based-social-platform-architecture-guide.pdf` shows
  `i/-text w/-text attr/-text`.
- `git status --short` doesn't list the PDF. It shows `?? .gitattributes` plus the doc edits.
- `git diff --check` is clean.
- Grep: no `role != user` without the superuser clause; ENV_GUIDE no longer relies on
  `send_default_pii` alone.
- Application tests, ruff and pytest: not applicable, because nothing is scaffolded yet. The
  new rules are exercised by Part 0A's acceptance criteria.

## Non-goals and stop conditions

- No Part 0A implementation: no `settings.py`, `pyproject.toml`, apps or requirements.
- No git commands; the user commits.
- Don't renormalize other files or touch `design/`.
- Stop and report if the PDF assertions or the hash check fail.

## Follow-ups for the Part 0A planner (not done here)

- Test folders need `__init__.py`, because apps share test module names (`test_models.py`).
- If the ruff rule set enables E501, add `per-file-ignores` for `**/migrations/*.py`.
- Name local variables that hold secrets so the scrubber would also catch them (defence in depth
  alongside `include_local_variables=False`).
