# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** none active. **Part 0D (Brand assets & Logo component) is done** (2026-10-01). Parts 0A
  (2026-09-30) and 0B (2026-10-01) are done too.
- **Owner:** none (idle until the user starts the next part)
- **Phase:** 0D implemented and validated; awaiting the user's review and git commit
- **Last approved plan:** `docs/agents/plans/part-0D-brand-assets.md` (status: implemented)
- **Last updated:** 2026-10-01 by Claude (Sonnet 5.5), Part 0D implementation

## Completed checkpoints

- Dual-agent setup, the pre-0A correction pass, Part 0A, Part 0B and the 0D plan (`920cf0b`), all
  committed by the user. The 0D implementation below is uncommitted.
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

- Everything below is uncommitted. Modified tracked files: `task.md`, `docs/{ARCHITECTURE,SETUP,STRUCTURE}.md`,
  `docs/test-command.md`, `docs/agents/HANDOFF.md`, `docs/agents/plans/part-0D-brand-assets.md` (status line),
  `frontend/{package.json,package-lock.json,.prettierignore}`, `frontend/scripts/lint-tokens.{mjs,test.ts}`,
  `frontend/src/app/layout.tsx`, `frontend/src/features/dev/UiGallery.tsx`.
- New: `frontend/scripts/brand/`, `frontend/public/brand/`, the generated files under `frontend/src/app/`
  and `frontend/src/lib/brand-assets.json`, `frontend/src/app/manifest.{ts,test.ts}`,
  `frontend/src/components/ui/Logo.{tsx,test.tsx}`, `frontend/src/features/dev/LogoSection.tsx`,
  `frontend/src/lib/brand-guard.test.ts`, `backend/apps/core/static/`.
- `git status --short design` prints nothing; `design/logo.svg` was only read.
- `.gitattributes` needed no change (`*.png`, `*.ico` already binary). `git check-ignore` prints nothing for
  any generated file. No `frontend/AGENTS.md` or `CLAUDE.md` exists (checked after build and dev start).
- `frontend/.env.local` and `backend/.env` were **not read or edited**. No dev server is left running.
- The local Postgres/Redis containers were not needed and were not touched.

## Validation (all in `frontend/`, 2026-10-01)

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

1. The user reviews the diff and commits (all git operations are theirs).
2. Start a fresh session for the next part in `task.md`'s order: **Part 0C** (App shell, API relay, API
   client, CI; needs 0A, 0B, 0D, all done).
3. Prompt for planning: `Plan Part 0C from task.md. Do not implement yet.`
   - 0C places `<Logo/>` everywhere listed in ARCHITECTURE §14 (sidebar `md`, tablet dock `mark`, mobile top
     bar `sm`, auth card `lg`, marketing nav/footer, 404/500) and extends the guard test's expectations if it
     adds files that legitimately know about the brand (it should not: use `<Logo/>`).
   - CI: run `lint:tokens`, `format:check` and `npm test` (the brand tests need `sharp`, which `npm ci` installs
     with prebuilt binaries on Linux). Do **not** add a "regenerate and diff" check for PNGs: bytes can differ
     across OS/libvips builds (`build.test.ts` already fails on stale SVG/JSON/txt outputs).

## Blockers or user decisions

- None open.

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
