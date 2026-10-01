# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** 0C (App shell, API relay, API client, CI). Parts 0A (2026-09-30), 0B and 0D (2026-10-01)
  are done and committed.
- **Owner:** none (idle until the user starts implementation)
- **Phase:** plan approved; implementation not started (no code, setup command or `task.md` change yet)
- **Last approved plan:** [`docs/agents/plans/part-0C-app-shell-relay-ci.md`](plans/part-0C-app-shell-relay-ci.md)
  (status: approved 2026-10-01, not implemented)
- **Last updated:** 2026-10-01 by Claude (Opus 5.5), Part 0C planning

## Completed checkpoints

- Dual-agent setup, the pre-0A correction pass, Parts 0A, 0B and 0D (0D = `b695f09`), and the
  multi-source spec change (`bd05636`), all committed by the user.
- 2026-10-01 (Claude, Opus 5.5): **Part 0C planned and approved.**
  - It checked that every dependency (0A, 0B, 0D) is Done.
  - It saved the plan in `docs/agents/plans/part-0C-app-shell-relay-ci.md`.
  - The approved deviations from task.md / ANALYSIS d are listed in the plan, for example buffered
    request bodies, `skipTrailingSlashRedirect`, the Location rewrite, and one OpenNext build step in
    CI. They are recorded in ARCHITECTURE/ANALYSIS during implementation, not yet.
- 2026-10-01 (Claude, Opus 5.5): **spec change, up to 5 sources per fact post** (user decision; was
  one). Docs only, uncommitted: `AGENTS.md`, `docs/{ARCHITECTURE,ANALYSIS,STRUCTURE}.md`, `task.md`,
  new `docs/agents/plans/spec-multi-source-posts.md`. `Post.source` + `source_kind` became one
  `sources varchar(500)[]` column (kind derived), API output `sources: [{value, kind}]`, pipeline
  `sources: tuple[str, ...]`, composer source list, card "first source +N more", b3 registry →
  `SourceList` (Part 5). Part 4 must build this design (ARCHITECTURE §2, §4c, §9).
- 2026-10-01 (Claude, Sonnet 5.5): **Part 0D implemented.**
  - `frontend/scripts/brand/`: `build-brand-assets.mjs` (`npm run brand:build`), `svg.mjs` (safety
    check, tokenizer, fill inlining, bounds measured from a 4x render, wordmark crop, mark extraction),
    `ico.mjs`, `png.mjs`, `contrast.mjs`, `brand.config.json`, and five test files
    (`svg`, `ico`, `contrast`, `assets`, `build`).
  - Generated and committed-to-be: `frontend/public/brand/{logo.svg,mark.svg,icon-192.png,icon-512.png,
    icon-maskable-512.png,email-logo.png,google-oauth-logo.png}`, `frontend/src/app/{favicon.ico,icon.svg,
    apple-icon.png,opengraph-image.png,twitter-image.png,opengraph-image.alt.txt,twitter-image.alt.txt}`,
    `frontend/src/lib/brand-assets.json`, `backend/apps/core/static/core/brand/logo-admin.png`.
  - `src/components/ui/Logo.tsx` (+ test), `src/app/manifest.ts` (+ test), `src/lib/brand-guard.test.ts`,
    `src/features/dev/LogoSection.tsx` (gallery section `#logo`), `layout.tsx` metadata
    (`metadataBase` from `NEXT_PUBLIC_SITE_URL`, application name, Open Graph and Twitter fields).
  - `lint:tokens` allowlist is `src/lib/brand-assets.json`; it now scans `.json` too. `sharp` 0.35.5 is a
    pinned devDependency. `.prettierignore` lists the generated JSON.
  - Docs updated: `task.md` (both status locations, criteria, deviations), `ARCHITECTURE.md` §14 (plate
    details), `STRUCTURE.md` (✅ markers), `SETUP.md` B3, the plan's status line, `docs/test-command.md`
    (Part 0D section). `MEMORY.md` needed nothing new.
  - User decision recorded: rounded-square plate for favicon.ico, icon.svg, icon-192, icon-512.
  - No new env variable (`NEXT_PUBLIC_SITE_URL` already existed), so `.env.example` and ENV_GUIDE are unchanged.

## Current workspace state

- The tree was clean at `bd05636` before planning.
- Uncommitted now (planning only):
  - new `docs/agents/plans/part-0C-app-shell-relay-ci.md`
  - modified `docs/agents/HANDOFF.md`
- No code, test, dependency, env file or `task.md` changed, and no tests were run (docs only).
- Read-only checks made while planning (2026-10-01):
  - `npm view`: `@opennextjs/cloudflare` 1.20.7, `wrangler` 4.145.0, `@playwright/test` 1.63.0.
  - Next 16.3.8 source: the `/:path+/` 308 redirect, `x-forwarded-for ??=`, `request.url` built with
    `new URL()`, and the patched fetch keeping `duplex`.

## Validation of Part 0D (all in `frontend/`, 2026-10-01)

- Passed: `npm run lint` → exit 0, no findings.
- Passed: `npm run lint:tokens` → "lint:tokens OK".
- Passed: `npm run typecheck` → exit 0.
- Passed: `npm run format:check` → "All matched files use Prettier code style!".
- Passed: `npm test` → **40 test files, 329 tests passed** (was 32 / 251 in 0B).
- Passed: `npm run build` → compiled, 10 static pages; routes now include `/apple-icon.png`, `/icon.svg`,
  `/manifest.webmanifest`, `/opengraph-image.png`, `/twitter-image.png`. `.next/server/app/index.html` holds
  `rel="manifest"`, two `rel="icon"` (ico 48x48, svg), `rel="apple-touch-icon"` 180x180, `og:image`,
  `og:image:alt` ("Rumor Zero", no newline), `twitter:card` and `twitter:image` (absolute URLs).
- Passed: `npm run brand:build` → 16 files; the printed contrast table equals ARCHITECTURE §14 (3.45/2.42,
  3.28/2.30, 3.81/5.43, 4.97/7.09). A second run gives byte-identical files (15 hashed, 0 differences),
  `git status --short design` is empty.
- Passed (CLI negative runs, exit code 1, nothing written): a master with `<script>` + `<text>`, one with an
  external `href`, one without a `viewBox`.
- Passed (guard): temporary `tmp-wordmark.tsx` and `tmp-logo-ref.ts` made `brand-guard.test.ts` fail 3 tests;
  removed, 6 pass.
- Passed (real `next dev`): the 13 generated URLs return 200 with the right content types; the manifest
  lists 192, 512 and maskable 512 with `#283044`; `/brand/nope.png` is 404.
- Passed (headless Edge, `/dev/ui#logo`): all 21 Logo images render at 24/36/48 px with their ratio widths;
  alt is "Rumor Zero", empty for the decorative ones; screenshots reviewed on all three surfaces. The generated
  PNGs were also viewed (share image, 512 icon, maskable, email, admin).
- Not run: a real browser tab (the tab icon was not looked at; headless Edge has no tab strip), Playwright
  (arrives in 0C), `opennextjs-cloudflare build` (Linux only, 0C/CI).

## Next exact action

**Implement Part 0C from the approved plan**
([`docs/agents/plans/part-0C-app-shell-relay-ci.md`](plans/part-0C-app-shell-relay-ci.md)).

- Model: Sonnet 5.5 · high (task.md).
- Prompt: `Implement only the approved Part 0C plan, validate it, update task.md and HANDOFF.md, then stop.`
- Start at the plan's step 0: set task.md 0C to `[~] In progress` in both places and update this file.
- The last acceptance criterion (CI green on GitHub) needs the user to push. The agent then reads the
  result with `gh run list/view` (read-only; `gh api` is denied).

## Blockers or user decisions

- None open.
- User decisions for 0C (2026-10-01), detailed in the plan:
  - logged-out shell = reduced nav (Home, Search, Log in / Sign up)
  - phones = top bar plus a 5-tab bottom bar (Home, Search, New post, Notifications, Profile), with the
    avatar opening an account sheet (Bookmarks, Settings, Moderation)
  - marketing links only to existing pages (About, Community Guidelines, Press and Contact dropped)

## Follow-ups noted during 0D (not done, per the part's scope)

- Part 2: email templates use `FRONTEND_ORIGIN/brand/email-logo.png` (320 px wide, shown at 160).
- Part 10: `templates/admin/base_site.html` uses the static `core/brand/logo-admin.png` (158x64). `collectstatic`
  must pick it up (Part 17 already lists collectstatic in the build).
- Part 15: 404/500 pages use `<Logo/>`.
- Risk for 0C/CI: the wordmark and mark viewBoxes come from a pixel measurement (0.25 unit steps). Another librsvg build could in theory measure one step differently, which would make `build.test.ts` ("nothing is stale") fail on Linux. If that happens, fix the measurement rather than loosening the test.
- The `theme_color` of the web manifest is the dark plate colour; revisit if a light toolbar is preferred.
- If the logo is re-exported, check `markSelector` in `scripts/brand/brand.config.json` (the build fails when
  it does not match exactly one shape) and compare the printed contrast table with ARCHITECTURE §14.

## Follow-ups noted during 0B (still open)

- Part 16: subset the 4 MB Material Symbols font to the glyphs actually used.
- Toasts render below an open `<dialog>` (top layer). If a toast must appear over a modal, move the
  toast region into a popover. Background scroll is also not locked while a modal is open.
- Part 1: revisit `scorePassword` against the final allauth/Django validators.
- 0C: CI should run `lint:tokens` and `format:check`; Playwright takes over the visual smoke test.
  `Card` with `interactive` and the shell do not exist yet; the Stitch app shell is 0C.
- `PostCard` has no action bar or source line yet (Parts 4, 7, 7B) and no skeleton variant.

## Follow-ups noted during 0A (still open)

- Part 10: log old → new values for every PlatformSettings change; seniors-only editing; the senior
  group's extra permissions (the role → groups mapping is cumulative).
- Part 1/2: a CLI superuser has `is_email_verified=False` and no allauth `EmailAddress`; decide
  whether it needs app writes. `DEFAULT_AUTHENTICATION_CLASSES` is `[]` until Part 1, so an
  unauthenticated request currently returns 403 rather than 401.
- Part 17: fail deploys when `PROXY_SHARED_SECRET`/`INTERNAL_CRON_SECRET` is short or a
  `local-dev-only` placeholder; verify Render's health-check Host header against `ALLOWED_HOSTS`;
  `collectstatic` must run in the build (the manifest storage needs it when DEBUG is False).
- Part 0C: CI builds its env file from `backend/.env.example`; the tests read it only through
  process env/`.env`, and `test_settings.py` passes every variable explicitly to its subprocesses.

## Handoff checklist (outgoing agent)

- [x] Stop editing before the incoming agent starts.
- [x] Record current owner, phase and approved plan.
- [x] Record files changed and any unrelated pre-existing modifications.
- [x] Record every validation command and its exact pass/fail result.
- [x] Record blockers, user decisions and the next exact action.
- [x] Promote only durable, non-duplicated knowledge to `MEMORY.md`.
