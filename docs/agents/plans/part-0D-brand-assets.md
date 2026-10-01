# Plan: Part 0D, Brand assets & Logo component

- **Status:** IMPLEMENTED 2026-10-01 by Claude (Sonnet 5.5). Deviations are listed under Part 0D in `task.md`. The steps below are kept as the record of what was approved.
- **Drafted:** 2026-10-01 by Claude (Sonnet 5.5). **Implement with:** Sonnet 5.5 · medium (task.md).
- **Part:** 0D (task.md). **Depends on:** 0B only, which is `[x] Done (2026-10-01)`. Git tree was clean
  at planning time (0B committed).
- **Not touched while saving this plan:** `task.md` (its status changes happen in step 0 of the
  implementation), code, dependencies.

## Context

D9: one logo everywhere. `design/logo.svg` is the single master; `npm run brand:build` derives every
favicon, icon, share image and email/admin logo from it; `<Logo/>` is the only way the UI shows the
brand. Part 0C (shell) needs `<Logo/>`, so 0D comes first.

Verified before planning:
- `design/logo.svg` matches ARCHITECTURE §14: viewBox 1000², paths R/u/m/r in class `cls-2` (grey
  `#898a8d`), one `<path class="cls-1">` (the "0", cyan `#23b5d8`) and a `<rect class="cls-1">` underline,
  all outlines, one `<style>` block.
- The §14 contrast table recomputes exactly (3.45/2.42, 3.28/2.30, 3.81/5.43, 4.97/7.09) from the
  surface hexes in `globals.css` (`#ffffff`, `#faf8ff`, `#283044`, `#131b2e`).
- `sharp` 0.35.5 is already in `node_modules` as Next's optional dependency (works on this Windows
  machine). `npm view` lists 0.35.3–0.35.5.
- `.gitattributes` already marks `*.png` and `*.ico` binary. SVG, JSON and `.alt.txt` are text (LF).
  **No new binary type is needed**, so HANDOFF's "add each new binary type" step is a no-op.
- `NEXT_PUBLIC_SITE_URL` already exists in `frontend/.env.example` and ENV_GUIDE ("canonical origin,
  Open Graph"), so no new env variable.
- `vitest.config.mts` already includes `scripts/**/*.test.{ts,mjs}`; `.prettierignore` already lists
  `public/brand`; `frontend/.gitignore` does not ignore any output path.

User decision (asked 2026-10-01): **rounded-square plate** (~22% corner radius, transparent corners)
for `favicon.ico`, `icon.svg`, `icon-192.png`, `icon-512.png`. Full-bleed squares for `apple-icon.png`,
`icon-maskable-512.png` and the wide plates (share, email, Google, admin).

## Scope

Frontend only (plus one generated file under `backend/apps/core/static/core/brand/`). No API, no
env variable, no UI change besides `/dev/ui`. Nothing under `design/` is ever written.

## Design decisions (not stated in the docs; resolved here)

- **No new XML dependency.** `scripts/brand/svg.mjs` has a small tag tokenizer (enough for our own
  outlined SVG). The mark selector supports `tag.class` only (documented in the config comment).
- **Derived SVGs have no `<style>`.** Class fills are resolved from the master's `<style>` and inlined as
  `fill="…"` attributes, so nesting the mark/wordmark inside plate SVGs cannot clash on class names and
  librsvg needs no CSS.
- **Artwork bounds come from rasterising, not from parsing path data:** render at 4× with sharp, scan
  the alpha channel for the bounding box (precision 0.25 unit), convert back to viewBox units. A test
  asserts the result is within 0.5 unit of the §14 numbers (x 121.4–878.6, y 413.0–625.7; "0" x 664.4–779.2,
  y 413.0–584.9). This handles Bézier extrema without a path parser.
- **Wordmark crop** = artwork bounds + 12 units padding on every side (config `wordmarkPadding`).
  **Mark viewBox** = square of side `max(w,h)` of the "0" + 2 × `markPadding` (config, 12), centred.
- **Plates** (all colours from config, `plateColor` = `inverse-surface` `#283044`; a test asserts it
  equals `--color-inverse-surface` in `globals.css`, so the token stays the single source):
  - icons / apple / maskable: mark centred; mark height 56 % of the plate (rounded variants), 50 % for
    maskable so its half-diagonal stays inside the 40 % radius safe circle;
  - share 1200×630, email 320 wide, Google 120×120, admin 64 tall: full wordmark centred, widths 60 % /
    ~85 % / 90 % / ~90 % of the plate, no text (the master forbids `<text>`, and sharp has no fonts);
  - exact fractions live in `brand.config.json`; the tests, not the numbers, are the contract.
- **Shape of generated JSON** `src/lib/brand-assets.json`: `{ master, plateColor, logoColors, wordmark:
  {src,width,height}, mark:{src,width,height}, favicon, icons[], appleIcon, share, email, google, admin }`.
  `Logo` derives width from height × intrinsic ratio, so there is no layout shift.
- **`manifest.ts`** takes `theme_color`/`background_color` and icon paths from `brand-assets.json`, so it
  contains no hex and no `/brand/` literal itself. Task.md says both files go on the `lint:tokens`
  allowlist; only `brand-assets.json` needs it. Deviation to record: allowlist `brand-assets.json` only,
  and make `lint:tokens` scan `.json` under `src/` so the allowlist entry is real.
- **No CI "regenerate and diff" check** (PNG bytes may differ across libvips builds/OSes). Tests check
  dimensions/structure instead. Mention as a 0C note in HANDOFF.
- Extra safety checks beyond the task list (same spirit): `@import` or `url(` pointing outside the file
  inside `<style>` also fails the build.

## Files

New:
- `frontend/scripts/brand/build-brand-assets.mjs`: CLI + exported `buildAll({masterPath, frontendDir, adminDir})`.
  Writes only to those dirs; refuses any output path inside `design/`.
- `frontend/scripts/brand/{svg,ico,contrast}.mjs`: `checkSafety`, `parse`, `resolveFills`, `cropToArtwork`,
  `extractMark`, `measureBounds` / PNG-in-ICO writer / WCAG contrast + printed table.
- `frontend/scripts/brand/brand.config.json`: `master`, `markSelector: "path.cls-1"`, `plateColor`,
  paddings, fractions, `contrastSurfaces` (the four §14 surfaces) and `expectedContrast` (the §14 numbers).
- `frontend/scripts/brand/*.test.ts` (each `// @vitest-environment node`).
- `frontend/src/components/ui/Logo.tsx` + `Logo.test.tsx`.
- `frontend/src/app/manifest.ts` (+ small test).
- `frontend/src/lib/brand-guard.test.ts`.
- Generated, committed, never hand-edited:
  `frontend/public/brand/{logo.svg,mark.svg,icon-192.png,icon-512.png,icon-maskable-512.png,email-logo.png,google-oauth-logo.png}`,
  `frontend/src/app/{favicon.ico,icon.svg,apple-icon.png,opengraph-image.png,opengraph-image.alt.txt,twitter-image.png,twitter-image.alt.txt}`,
  `frontend/src/lib/brand-assets.json`,
  `backend/apps/core/static/core/brand/logo-admin.png` (folder created).

Edited:
- `frontend/package.json` (+ lockfile): `sharp` exact `0.35.5` in devDependencies (the repo pins exact
  versions); script `"brand:build": "node scripts/brand/build-brand-assets.mjs"`.
- `frontend/src/app/layout.tsx`: `metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000")`,
  `applicationName`, `openGraph.siteName`; icons/manifest/OG images come from the file conventions.
- `frontend/scripts/lint-tokens.mjs` + `lint-tokens.test.ts`: allowlist, `.json` scanning.
- `frontend/.prettierignore`: `src/lib/brand-assets.json` (generated).
- `frontend/src/features/dev/{DisplaySections,UiGallery}.tsx`: "Logo" section + nav link.
- Docs: `task.md` (both status spots, criteria, deviations), `HANDOFF.md`, `ARCHITECTURE.md` §14 (record
  the paddings/shape if they differ), `STRUCTURE.md` (✅ markers), `SETUP.md` B3 (sharp installed),
  `MEMORY.md` only if something durable turns up (e.g. a sharp/librsvg quirk).

Reuse: `cn` (`src/lib/cn.ts`), the `Section`/`Specimen` gallery helpers, Avatar's plain-`<img>` pattern
(+ its eslint-disable comment), `lint-tokens.mjs` exports, existing Vitest setup.

## Ordered steps

0. Set task.md 0D to `[~] In progress` (both locations); update HANDOFF "Active work". (This plan file is
   already saved and linked.)
1. `npm install -D -E sharp@0.35.5`, add the script; confirm lockfile changes are only `sharp` metadata.
2. `svg.mjs` + tests first: safety check (each forbidden construct and a missing viewBox), tokenizer,
   fill resolution, selector must match exactly one `<path>`, bounds measurement, wordmark crop, mark.
3. `ico.mjs` + test (header, 3 entries 16/32/48, PNG signatures, offsets/sizes consistent).
4. `contrast.mjs` + test: output equals the §14 numbers, `plateColor` equals the CSS token.
5. `brand.config.json` and `build-brand-assets.mjs`; run `npm run brand:build`; open the PNGs with Read
   to eyeball them; run it twice and confirm the second run changes nothing (deterministic on this machine).
6. `Logo.tsx` + test (accessible name "Rumor Zero", `decorative` → `alt=""`, 24/36/48 heights, width from
   ratio, mark square, no `next/image`, no inline SVG), `manifest.ts`, layout metadata.
7. `lint-tokens` allowlist + `.json`; `brand-guard.test.ts` (only `Logo.tsx`, `brand-assets.json`,
   `manifest.ts` reference `/brand/` or import `brand-assets`; JSX text exactly "Rumor Zero"/"RUMOR ZERO"
   or "Fact Social" outside tests fails).
8. `/dev/ui` Logo section: wordmark + mark × sm/md/lg on `surface`, `surface-container-lowest`,
   `inverse-surface`, plus decorative variants.
9. Validate (below), update docs, stop.

## Tests (required list, mapped)

SVG safety (each construct); mark extraction + viewBox cropping; ICO writer; PNG-header dimension tests
for every PNG (apple 180×180 colour type 2 = opaque; icons 192/512/512; maskable mark within the 80 %
circle by pixel scan; share/twitter 1200×630; Google 120×120 and < 1 MB; email 320 wide; admin 64 tall);
`brand-assets.json` shape; Logo render/sizes/name; guard test; contrast table; plus a build-into-temp-dir
test asserting `design/logo.svg` is byte-identical before and after.

## Verification (in `frontend/`, PowerShell)

```powershell
npm run brand:build            # prints the contrast table; compare with ARCHITECTURE §14
git status --short design      # must print nothing
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check ; npm test
npm run build                  # then inspect .next/server/app/index.html for: rel="icon" (ico + svg),
                               # apple-touch-icon, rel="manifest", og:image, twitter:image
git check-ignore frontend/src/app/favicon.ico frontend/public/brand/logo.svg   # prints nothing
```

Then a headless-Edge screenshot of `/dev/ui#logo` (MEMORY recipe; scripts/images in the scratchpad),
and a negative test: temporarily point the build at a scratch SVG with `<script>`, with an external
`href`, and with `<text>` and confirm the failure message (the unit tests cover the same, this proves the CLI path).
Record exact commands and results in HANDOFF.

## Stop conditions

Stop and report (do not work around) if: `sharp` won't install or render on this machine; the printed
contrast table differs from §14; any file under `design/` shows as changed; the selector matches ≠ 1 path
on the current master; a generated size can't meet its exact acceptance dimension. Out of scope and left
for later parts: shell placements (0C), email templates (Part 2), admin header template (Part 10),
subsetting the 4 MB icon font (Part 16), CI regenerate-and-diff.
