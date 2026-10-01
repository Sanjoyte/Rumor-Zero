# Plan: spec change, up to 5 sources (URL or DOI) per fact post

- **Status:** IMPLEMENTED 2026-10-01 by Claude (Opus 5.5). Docs only; no code existed for posts yet.
- **Approved:** 2026-10-01 by the user (Sanjoyte). **Part:** none (a spec change that Parts 4, 5,
  9 and 16 build on). **Depends on:** nothing; Part 4 had not started.
- **Not touched:** code, migrations, tests, env files, `design/**`, `MEMORY.md`
  (ARCHITECTURE §4c is the canonical home).

## Context

The user wants fact posts to carry **multiple** sources/DOIs. The spec allowed exactly one
(`ARCHITECTURE §4c`, `Post.source` + `source_kind`), and the Stitch "Triangulated primary sources"
registry on b3 had been dropped (`ANALYSIS.md` b-3, `task.md` Part 5). No post code existed
(Part 4 not started; only 0A/0B/0D done), so this was a docs-only change: the sources of truth
were updated so Parts 4/5/9 build multi-source from the start.

User decisions (2026-10-01): change the spec; **max 5 sources per post**.

## Design (what the docs now say)

- **Scope:** optional, fact posts only, 0–5 per post, kept in the order entered, immutable. Each is
  an http(s) URL or a DOI, validated per §4c (≤ 500 chars each, never fetched). Duplicates after
  normalisation are refused (`doi:10.1/x` and `https://doi.org/10.1/x` are the same source).
- **Storage:** one column `sources varchar(500)[]` (Django `ArrayField(CharField(500))`,
  default `[]`, not null) replaces `source` + `source_kind`. An array rather than a child table:
  sources are immutable and always read with the post, so the feed needs no extra query
  (query-count tests stay flat) and "opinion has no sources" stays a plain DB check.
- **DB checks:** `sources__len <= 5`; `post_type='fact' OR sources__len = 0`; no empty element
  (`~Q(sources__contains=[""])`). Django's `__len` maps an empty array to 0, not NULL.
- **Kind is derived, not stored:** a stored DOI is bare and starts with `10.`; a stored URL always
  starts with `http://`/`https://`. `posts.validators.source_kind(value)` decides it.
- **API input:** `POST /api/v1/posts/` takes `sources: ["…", …]` (optional, ≤ 5 strings). Errors
  per index (`{"sources": {"1": ["…"]}}`), plus `too_many_sources` / `duplicate_source`.
- **API output (§9 Post object):** `"sources": [{"value": "10.1038/…", "kind": "doi"}]`, `[]` when none.
- **Pipeline (§6):** `PipelineRequest(post_id, content, sources: tuple[str, ...])`; the HTTP client
  sends `{post_id, content, sources}`; the stub ignores it.
- **UI:**
  - Composer (b2): the source field becomes a list. One field to start, "Add another source"
    up to 5, a remove button on extra rows, inline validation per row (including duplicates),
    empty rows dropped before submit, "DOI preferred" hint kept.
  - PostCard (b1): one line, the first source (host or `doi.org/…`), then "+N more". From Part 5,
    "+N more" links to the detail page.
  - PostDetail (b3): the "primary sources" registry becomes `SourceList`, a numbered list
    (01, 02 …) with each full value and an open-in-new link under "Sources (N)". Its sample
    titles, org-type chips, "% match" and archive/hash lines are dropped.
- Part 4 adds `django.contrib.postgres` to `INSTALLED_APPS` (part of Django; psycopg is already
  installed, so no new dependency).

## Files changed

1. `docs/ARCHITECTURE.md`: §2 posts table (`sources` row), the note under the indexes, limits
   table, §4c rewritten, §6 contract and HTTP body, §9 Post object + `sources` bullet, frontend
   source-links line, §12 security row.
2. `docs/ANALYSIS.md`: D5 row, b1/b2/b3 rows, `SourceLink` + new `SourceList` component rows,
   feature row in b-3, f-3 rewritten.
3. `task.md`: Part 4 (goal, Stitch notes, backend/frontend scope, acceptance criteria, required
   tests), Part 5 (Stitch notes, `SourceList`), Part 9 (contract, client, acceptance criterion),
   Part 16 (wording).
4. `AGENTS.md`: the product summary line.
5. `docs/STRUCTURE.md`: `validators.py (sources/DOI)`.
6. This plan and `docs/agents/HANDOFF.md`.

## Verification

- Grep the docs for `source_kind`, `"source"`, `source: str`, "one per post" and "multi-source
  registry": no single-source wording should survive, apart from the "changed from one" notes.
- ARCHITECTURE §2, §4c, §6, §9, ANALYSIS f-3 and task.md Parts 4/5/9 agree on the name
  `sources`, the limit 5 and the `{value, kind}` output shape.
- `git status --short design` is empty; `git diff --stat` lists only the docs above.
- No tests to run (no code changed).
