# Rumor Zero: live handoff

Update this file at meaningful checkpoints and before switching between Claude Code and Codex.
Keep it concise and factual. The incoming agent must verify it against the current files and
read-only git output.

## Active work

- **Part:** none active. **Part 0B (Frontend foundation & design system) is done** (2026-10-01).
  Part 0A is done (2026-09-30).
- **Owner:** none (idle until the user starts the next part)
- **Phase:** 0B implemented and validated; awaiting the user's review and git commit
- **Last approved plan:** `docs/agents/plans/part-0B-frontend-foundation.md` (status: implemented)
- **Last updated:** 2026-10-01 by Claude (Sonnet 5.5), Part 0B implementation

## Completed checkpoints

- Dual-agent setup (`dbe02e6`), the pre-0A correction pass (`c25d479`), Part 0A (`a845236`) and the
  0B plan (`1cb11f1`), all committed by the user. `1cb11f1` also captured the scaffold files that
  existed at that moment (`frontend/package.json`, `tsconfig.json`, `next.config.ts`, ... in their
  untouched scaffold form); the diff below is relative to that.
- 2026-10-01 (Claude, Sonnet 5.5): **Part 0B implemented.**
  - `frontend/`: Next 16.3.8 + React 19.2.8 + Tailwind 4.3.3, scaffolded in a scratch folder (the real
    `.env.local` and `.env.example` blocked `create-next-app`) and copied in; nothing touched either
    env file. `agentRules: false` in `next.config.ts` (Next otherwise writes `frontend/AGENTS.md` and
    `CLAUDE.md` on every `next dev`).
  - `src/app/globals.css`: the 49 DESIGN.md colours, 13 type tokens, spacing, widths, `rounded-lg`,
    v3-strength `shadow-sm`, defaults reset, forms plugin (`strategy: class`), icon font imported into
    `@layer components`, focus ring, reduced motion.
  - 27 primitives in `src/components/ui/`, `PostCard` in `src/features/posts/`, helpers in `src/lib/`
    (`cn`, `format`, `password-strength`, `post-display`), `lint:tokens` (`scripts/lint-tokens.mjs`),
    and the dev-only gallery at `/dev/ui` (`src/features/dev/`, 404 in production builds).
  - Docs updated: `task.md` (both status locations, criteria, deviations), `SETUP.md` B3,
    `STRUCTURE.md`, `ARCHITECTURE.md` §10, `ANALYSIS.md` (49 colours, forms and meter decided),
    `MEMORY.md` (two tooling entries).
  - No new env variable, so `frontend/.env.example` and ENV_GUIDE are unchanged.

## Current workspace state

- Everything below is uncommitted. Modified tracked files: `docs/{ANALYSIS,ARCHITECTURE,SETUP,STRUCTURE}.md`,
  `docs/agents/MEMORY.md`, `task.md`, `docs/agents/plans/part-0B-frontend-foundation.md` (status line),
  `frontend/{eslint.config.mjs,next.config.ts,package.json}`, `frontend/src/app/{globals.css,layout.tsx,page.tsx}`.
- New: `frontend/{package-lock.json,vitest.config.mts,.prettierrc.json,.prettierignore}`,
  `frontend/scripts/` (lint-tokens + test), `frontend/src/{components,features,lib,test}/`,
  `frontend/src/app/{providers.tsx,dev/}`.
- Not for commit (ignored): `frontend/node_modules/`, `.next/`, `next-env.d.ts`.
- `frontend/.env.local` (2224 bytes, dated 2026-09-29) and `backend/.env` were **not read or edited**.
  Next loads `.env.local` itself during `build`/`dev`; no value was printed.
- No `frontend/AGENTS.md` or `CLAUDE.md` exists (verified after build and after a dev start).
- The local Postgres/Redis containers from 0A were not needed for 0B and were not touched.

## Validation (all in `frontend/`, 2026-10-01)

- Passed: `npm run lint` → exit 0, no findings.
- Passed: `npm run lint:tokens` → "lint:tokens OK".
- Passed: `npm run typecheck` → exit 0, also with `next-env.d.ts` and `.next/` removed (clean-clone case).
- Passed: `npm run format:check` → "All matched files use Prettier code style!".
- Passed: `npm test` → **32 test files, 251 tests passed** (Vitest 5.0.3, jsdom).
- Passed: `npm run build` → compiled, 4 static pages (`/`, `/_not-found`, `/dev/ui`).
- Passed (real servers): `next start` → `/` 200, `/dev/ui` **404**; `next dev` → `/dev/ui` 200.
- Passed (compiled CSS inspected): the icon rule sits inside `@layer components`; `rounded-lg`,
  `shadow-sm`, `max-w-reading`, `max-w-modal`, `px-space-md`, `font-claim-headline`,
  `text-claim-headline` resolve; no `bg-blue-500`; all three fonts and the icon font are emitted.
- Passed (headless Edge, 1280 px): gallery screenshots reviewed; Stitch b1, b2, d1 and a2 rendered the
  same way and compared with the PostCards, composer modal, report modal and sign-up fields. The
  differences are what the docs removed or deferred: copy changes (ANALYSIS b-5), affiliation line,
  evidence drawer and action bar (Parts 4, 7, 7B), no strike-through on FALSE claims, and Stitch's app
  shell behind the modals (0C).
- Passed (headless Edge via DevTools protocol): both modals open centred, initial focus correct,
  Tab never reaches the page behind, Esc closes, focus returns to the opener.
- Passed: `git check-ignore frontend/.env.example` prints nothing; no nested AGENTS.md/CLAUDE.md.
- Not run: Playwright (arrives in 0C); `opennextjs-cloudflare build` (Linux only, 0C/CI).

## Next exact action

1. The user reviews the diff and commits (all git operations are theirs).
2. Start a fresh session for the next part in `task.md`'s order. Per the table that is **Part 0D**
   (Brand assets & Logo component; depends on 0B, now done). Then 0C (needs 0A, 0B, 0D).
3. Prompt for planning: `Plan Part 0D from task.md. Do not implement yet.`
   - 0D will add `sharp` and the `brand:build` script. Add each new binary type to `.gitattributes`.
   - `lint:tokens` has an empty `ALLOWLIST` in `scripts/lint-tokens.mjs`; 0D's generated
     `src/lib/brand-assets.json` and `src/app/manifest.ts` (brand hex) must be added to it.

## Blockers or user decisions

- None open.

## Follow-ups noted during 0B (not done, per the part's scope)

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
