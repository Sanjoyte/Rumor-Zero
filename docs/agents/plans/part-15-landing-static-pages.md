# Part 15: Landing & static pages — approved plan

## Context
The public face of Rumor Zero is still placeholders: `/` is a stub, `/how-it-works`, `/privacy` and `/terms` use `Placeholder`, and
`not-found`/`error` are basic. Parts 11B/11D/11C already link to `/how-it-works#credibility` and the composer words the emergency rules, so the
page must exist. Google OAuth and guide §16 need Privacy/Terms. **Frontend only, no backend, no new API.**

**Dependency check (done):** Part 4 `[x]` (2026-10-09), 11B `[x]` (2026-10-19), 11C `[x]` (2026-10-20). HEAD `159411c` (Part 14B committed), tree clean.
Parts 14/14B also done. All three dependencies are met.

**User decisions (2026-10-21):** (1) drop a1's hero pill; (2) hard-code the settings defaults in the FAQ, pinned by a test against ARCHITECTURE §3;
(3) Lighthouse via `@lhci/cli` as a **devDependency + CI step** (explicit approval of a new dev dependency; no new external service).

## Scope / files
- `frontend/src/app/(marketing)/page.tsx` (`/`, static): hero (headline from a1, subtext rewritten in plain words, no pill, "Create account" /
  "I already have an account"), 3 feature cards (author-declared label · fact checking before you rely on it · the verdict colour means the verdict; copy rewritten, no
  "zero-bias", "epistemic", "protocol"), preview section. Logged-in visitors see "Go to your feed" (→ `/home`) in place of the two buttons via `useAuth`
  (anonymous markup is what prerenders; no flash for the common case).
- `frontend/src/features/landing/` (new): `LandingHero`, `FeatureCards`, `RecentPreview` (client: `GET /api/v1/posts/` through `src/lib/api/client.ts`, `page_size=4`;
  reuse `PostCard` + `toPostCardProps` read-only, no action bar for anonymous; skeleton = `PostCardSkeleton`; empty/error states = `EmptyState`/`Alert`, never a broken page),
  link "See more posts" → `/home`. No Stitch sample names, orgs or taglines.
- `frontend/src/features/info/` (new, static content components, one file per page + shared `InfoPage`/`Section`/`Faq` built on `<details>`-free headings so anchors work):
  - `HowItWorks`: status table rendered with the **real** `StatusBadge` rows (all 9 of ARCHITECTURE §4 badge table, EMERGENCY included) + the lifecycle
    (pending → verified/FALSE/under review → appeal/removal); FAQ: why opinions aren't checked, reports (5 in 24 h from accounts ≥ 24 h old; 2 during an active emergency),
    appeals (FALSE labels and removals), the pipeline (confidence 85, human review below it), emergency posts (six §4b rules and reasons, 24 h pin, checked first,
    FALSE costs N+3, blocks emergency posting 30 days, block lifts if the FALSE is overturned), why reposts keep the original's label.
  - `#credibility` section (id on the heading, `scroll-mt` under the sticky nav): plain-words formula (starts at 50, 10 imaginary events, public after 3, half up), **every event
    of the §4a table** (fact_true, fact_false, emergency_false, post_removed, report_upheld (cap 4 / 30 days), repost_* four kinds, reversal), what changes nothing, when it's shown
    ("New"), the appeal path; marked **"needs legal review"**.
  - `/privacy`, `/terms`: placeholder text with a visible "needs legal review" notice; Terms has explicit sections on verification labels and the credibility score.
    Privacy mentions what exists (account data, profile photo, export and deletion in settings, Sentry/Turnstile/Google as processors) without inventing a company or contact address.
- `not-found.tsx` / `error.tsx` / `global-error.tsx`: polish with `<Logo/>` (via `AuthLayout` already; verify), clear text, links to `/` and `/home`. Keep `error` text free of the error itself.
- Titles: every `page.tsx` exports `metadata.title` (or `generateMetadata`); landing keeps the root default "Rumor Zero". Page-level `openGraph` replaces the root object (ARCH §10), so static pages set none.
- `MarketingNav`/`MarketingFooter`: unchanged (links already point at these pages).
- Docs: ARCHITECTURE §10 (static pages, `#credibility` anchor, §4a "arrive with Part 15" → built), `docs/test-command.md`, `task.md` (Part 15 status, criteria, summary table), `HANDOFF.md`.
- Lighthouse: `frontend/package.json` devDependency `@lhci/cli` (pinned), `frontend/lighthouserc.json` (accessibility ≥ 0.95 on `/`, static server), a step in the existing
  frontend job of `.github/workflows/ci.yml` after `build`. Add `docs/ENV_GUIDE.md` note only if it needs an env var (expected: none). No Chrome install beyond what Playwright already fetches
  (confirm the runner's Chrome; else `CHROME_PATH` to Playwright's chromium).

## Ordered steps
0. Save this plan as `docs/agents/plans/part-15-landing-static-pages.md`; update `HANDOFF.md`; read `design/stitch/stitch_website_sitemap_grid_builder/a1_logged_out_home/code.html` and `design/stitch/code.html` (taxonomy table, confidence ramp, FAQ) for class names.
1. Shared info components + `/privacy`, `/terms` (+ tests).
2. `/how-it-works`: status table, lifecycle, FAQ, `#credibility` (+ tests, including the number-pinning test).
3. Landing page + `RecentPreview` (+ tests).
4. Error / not-found polish; titles audit test.
5. `@lhci/cli`, config, CI step; run it locally against `npm run build && npm start`.
6. Docs, `task.md`, `HANDOFF.md`.

## Tests (required: render test per page; E2E landing → how it works → sign up)
- Vitest + RTL: each page renders its h1/sections; how-it-works lists all 9 badge rows with the word FALSE (never "debunked"); `#credibility` id exists and lists every §4a event kind;
  a **numbers test** reads the FAQ constants and asserts the defaults (5, 24, 85, 2, 7, 40, 30, 3, 50, 10, 4) against a single `INFO_NUMBERS` object that cites ARCHITECTURE §3;
  Terms has the labels and score sections; all three legal pages show "needs legal review"; landing: anonymous → two buttons, signed in → "Go to your feed", preview loading/empty/error/4 cards,
  no Stitch sample strings (guard test: "Epistemic", "Network Inc.", "Calibration Edition", "guaranteed"); titles audit (every `page.tsx` has a title); not-found/error show the logo.
- Playwright `frontend/e2e/marketing.spec.ts`: `/` → "How verification works" → `#credibility` visible → "Sign up" → `/signup`.
- Lighthouse CI: accessibility ≥ 0.95 on `/`.
- Commands: `npm run lint ; npm run typecheck ; npm test ; npm run test:e2e ; npm run build` (static `○` for `/`, `/how-it-works`, `/privacy`, `/terms`); backend untouched, `pytest` need not rerun but run `ruff` no-op check skipped.

## Non-goals / stop conditions
- No backend, no new endpoint, no new env var, no chart library, no images other than the logo, no About/Contact pages, no cookie banner.
- No legal claims: texts say "needs legal review". Stop and ask if copy would need a company name, contact address or governing law.
- Stop if `@lhci/cli` cannot run in CI without a paid service (it uses temporary public storage only if asked; we use none) or needs a second new dependency.
- `design/` stays read-only. No git commands that change state.

## Acceptance (from task.md)
Landing matches a1 layout with no Stitch sample names/orgs/taglines · `#credibility` explains every §4a event and the appeal path · `next build` marks the four pages static ·
every route has a proper title · Lighthouse accessibility ≥ 95 on `/`.

## Approval
Approved by the user (Sanjoy Rozario) on 2026-10-21 in plan mode, with the three decisions above. Planned by Claude (Sonnet 5.5).
