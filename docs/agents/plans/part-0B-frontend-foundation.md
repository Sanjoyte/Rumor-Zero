# Plan: Part 0B, Frontend foundation & design system

- **Status:** APPROVED 2026-10-01 by the user (Sanjoyte); implementation in progress (Claude, Sonnet 5.5).
- **Drafted:** 2026-09-30 by Claude (Opus 5.5). **Implement with:** Sonnet 5.5 · high (task.md).
- **On approval:** save this file as `docs/agents/plans/part-0B-frontend-foundation.md` and link it
  from `docs/agents/HANDOFF.md` before running any command.
- **Part:** 0B (task.md). **Depends on:** SETUP.md Part A only. Its Node step was verified read-only on
  2026-09-30: Node v24.19.0, npm 11.17.0. 0B needs no task.md part (0A is `[x] Done` anyway). Git tree is
  clean at `a845236`.

## Context

`frontend/` holds only `.env.example` (tracked) and the user's real `.env.local` (git-ignored, never
read). 0B creates the Next.js 16 app, whose Tailwind v4 `@theme` **is** the Stitch design system,
plus the tested primitive kit that every later screen is built from. Every later frontend part
(0D logo, 0C shell/relay/CI, 1+ screens) depends on these tokens and components. Outcome:
- a scaffolded, pinned frontend;
- `globals.css` holding every DESIGN.md token, with the defaults reset;
- fonts and icons;
- about 27 primitives, a presentational PostCard and a dev-only `/dev/ui` gallery;
- green lint, lint:tokens, typecheck, vitest and build.

## Verified facts (2026-09-30, read-only registry and tarball checks)

- `create-next-app@16.3.8` / `next@16.3.8` are the latest 16.3.x (the floor is ≥ 16.3.7).
  - The template pins React **19.2.8**, as SETUP says. React 19.3.0 exists, but we keep the template's
    19.2.8.
  - `typescript` stays `^5` (5.9.3). **Not** 7.0.2.
- create-next-app 16.3.8 flags:
  - `--turbopack` is **no longer an option**. Turbopack is the default and unknown flags are ignored,
    so we drop the flag.
  - `--empty` exists: no demo page, SVGs or favicon.
  - `--yes` defaults to React Compiler **off** and AGENTS.md **on**, so `--no-agents-md` is required.
  - `--skip-install` exists.
- create-next-app's empty-folder allow-list does **not** include `.env.example` or `.env.local`, so a
  scaffold straight into `frontend/` fails.
- Current versions:
  - tailwindcss / @tailwindcss/postcss 4.3.3, @tailwindcss/forms 0.5.11, material-symbols 0.47.5
  - vitest **5.0.3** (SETUP says 5.0.2; engines `^24`), @vitejs/plugin-react 6.1.1, vite 8.3.1, jsdom 30.1.1
  - @testing-library/react 16.3.3, /dom 10.4.2, /user-event 14.6.7, /jest-dom **7.0.1**
  - prettier 3.9.9, prettier-plugin-tailwindcss 0.8.1, vite-tsconfig-paths 6.1.1, @types/node 24.19.0
- Tailwind v3 → v4 difference that affects fidelity: v4's `shadow-sm` is `0 1px 3px 0 rgb(0 0 0 / 0.1),
  0 1px 2px -1px rgb(0 0 0 / 0.1)`. The Stitch CDN (v3) `shadow-sm` is `0 1px 2px 0 rgb(0 0 0 / 0.05)`
  (v4 calls it `shadow-xs`). v4 supports `--text-<name>--font-weight`.
- The material-symbols Outlined woff2 is 4.0 MB with every axis, including FILL. That's fine for Workers
  static assets (well under 25 MiB); subsetting is a Part 16 follow-up.
- The Stitch HTML never uses `form-*` classes. It relies on the forms plugin's global (base) reset.
  With the chosen class strategy, each primitive adds `form-input`, `form-checkbox`, `form-radio` or
  `form-select` itself.

## Decisions

**User decisions (2026-09-30):**
1. **Temp-dir scaffold.** create-next-app runs with `--skip-install` in the session scratchpad; the
   generated files are copied into `frontend/`, then `npm install` runs there. Neither env file is
   moved, read or touched. (Deviation from task.md's "move `.env.example` aside" step.)
2. **`@tailwindcss/forms` 0.5.11 with `strategy: "class"`**, applied inside our primitives.
3. **Password meter:** 4 segments = Weak / Fair / Good / Strong, scored by a dependency-free
   `scorePassword()`. It is advisory; the Django validators stay authoritative.
4. **PostCard** lives in `src/features/posts/PostCard.tsx`, presentational (props only). Part 4 adds
   data and the source line; Parts 7/7B add the action bar.

**Planner decisions** (conventional defaults; recorded in docs during implementation):
- **Canonical Stitch variants** where the files disagree:
  - Inputs: a2 (`h-11`; a6's hover fill is not used). PasswordField: a2 `tracking-wider`.
  - Divider: a2 style (body-sm, `relative`).
  - Ghost/cancel: d1 (`py-space-sm`, hover `surface-container-low`, focus ring).
  - Modal footer: b2's `bg-surface-container-low` by default; `footer="plain"` gives d1's white.
  - Tabs: b4 (optional count). The underline is rendered inside the active tab, so it moves (this
    fixes the b1 bug).
  - Every interactive element gets a focus-visible ring. c2 lacks them.
- **Doc rules that override Stitch:**
  - FALSE claims are **not** struck through (ANALYSIS b-2).
  - Labels say FALSE, never "debunked".
  - Initials avatars use `inverse-surface` everywhere (DESIGN.md).
  - Badge glyphs are outlined, as in b1.
- **Theme resets** so only tokens exist:
  - `--color-*: initial`, `--font-*: initial`, `--text-*: initial`, `--radius-*: initial`,
    `--shadow-*: initial`.
  - Then `--radius-lg: 0.25rem` and `--shadow-sm` = the v3 value above. `rounded-full` is static and
    still works.
  - Container, tracking, leading, weight and spacing defaults are kept, because Stitch uses `max-w-md`,
    `tracking-wider`, `leading-snug`, `p-0.5` and similar.
  - `--default-font-family` is set to the Inter variable.
- **v4 preflight parity:** base `button:not(:disabled), [role="button"]:not(:disabled) { cursor: pointer }`
  (v3 had it). Borders are always given a colour class in components (v4 defaults to `currentColor`).
- **Focus:** a global `:focus-visible` 2px `secondary` outline with a 2px offset. Inputs keep Stitch's
  `focus:ring-2 focus:ring-secondary/20 focus:border-secondary` and `outline-none`.
- **Modal** uses the native `<dialog>` with `showModal()`, so it sits in the top layer and needs no
  `z-[60]`.
  - Scrim: `backdrop:bg-inverse-surface/40 backdrop:backdrop-blur-[2px]`.
  - Esc: an `onKeyDown` Escape handler plus a `cancel` event with `preventDefault` → `onClose`, so
    React state stays the source of truth.
  - Focus: the element that opened it gets focus back on close.
- **Dev gallery:** `src/app/dev/ui/page.tsx` calls `notFound()` when
  `process.env.NODE_ENV === "production"`. The gallery body is a client component in
  `src/features/dev/UiGallery.tsx`.
- **Toast:** `ToastProvider` + `useToast()`, an `inverse-surface` toast, bottom-centre, 4 s,
  `role="status"`. It is mounted in `src/app/providers.tsx`, which `layout.tsx` uses.
- **StatusBadge** is driven by a pure `statusBadgeSpec()` in the same file. `EmergencyBadge` and
  `AppealPendingBadge` are exported there too; the 11C `EmergencyChip` reuses `EmergencyBadge`.
- **DangerZone and Divider:** task.md names both as c2/a2 sources, so they are built as `ui/`
  primitives. Part 14's settings feature composes DangerZone.
- **ESLint:** add `react/no-danger: "error"`. Prettier uses `tailwindStylesheet: "./src/app/globals.css"`.
- **Exact pins** (`--save-exact`) for every added package.

## Files

- **Scaffold output (template):** `package.json`, `package-lock.json`, `tsconfig.json`, `next.config.ts`,
  `eslint.config.mjs`, `postcss.config.mjs`, `next-env.d.ts`, `.gitignore`, `README.md`, `src/app/*`.
- **New in `frontend/`:** `.nvmrc`, `.prettierrc.json`, `.prettierignore`, `vitest.config.mts`,
  `scripts/lint-tokens.mjs` (+ its test).
- **`src/app/`:**
  - `layout.tsx`: fonts, `<html lang="en">`, providers
  - `providers.tsx`
  - `globals.css`
  - `page.tsx`: a plain placeholder, no brand mark
  - `dev/ui/page.tsx` (+ test)
- **`src/components/ui/`**, each with `*.test.tsx`: `Icon`, `Button` (+ exported `buttonClasses()` for
  links), `TextField`, `PasswordField`, `Textarea`, `Checkbox`, `RadioCard` (+ `RadioCardGroup`),
  `Select`, `Toggle`, `Tabs` (+ `TabPanel`), `SegmentedControl`, `FilterChips`, `Card`, `VerdictStripe`,
  `StatusBadge`, `CategoryChip`, `Avatar`, `Modal`, `Alert`, `Toast`, `Skeleton`, `EmptyState`,
  `LoadMore`, `ProgressBar`, `PasswordStrengthMeter`, `Divider`, `DangerZone`.
- **Features:** `src/features/posts/PostCard.tsx` (+ test), `src/features/dev/UiGallery.tsx`.
- **`src/lib/`:** `cn.ts`, `format.ts`, `password-strength.ts`, `post-display.ts` (stripe tone and badge
  mapping shared by StatusBadge, VerdictStripe and PostCard), each with a test. `src/test/setup.ts`.
- **Docs:**
  - `task.md`: both status spots, criteria, deviations
  - `docs/SETUP.md` B3: versions, forms decision, create-next-app flags
  - `docs/STRUCTURE.md`: frontend tree and the scaffold note
  - `docs/ARCHITECTURE.md` §10: forms class strategy, the shadow-sm value, the meter scale, the
    StatusBadge spec
  - `docs/ANALYSIS.md` a.3/a.5: forms and meter now decided
  - `docs/agents/HANDOFF.md`; `docs/agents/MEMORY.md` (only verified durable gotchas, e.g. jsdom
    `<dialog>`)
- **Not touched:** `backend/`, `design/`, `frontend/.env.local`, `frontend/.env.example` (content
  unchanged), root `.gitignore` / `.gitattributes` (no new committed binary types).

## Steps (PowerShell unless noted; `$S` = the session scratchpad path)

1. **Pre-flight (read-only).**
   - `git status` is clean, and `frontend/` contains only the two env files. Don't read `.env.local`.
   - `npm view next@16.3 version` shows the latest patch. Use it if it's still 16.3.x ≥ 16.3.8.
2. **Scaffold in the scratchpad.**
   - Command: `npx create-next-app@16.3.8 "$S\rumor-zero-frontend" --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm --empty --no-react-compiler --no-agents-md --disable-git --skip-install --yes`
   - Using the folder name `rumor-zero-frontend` makes it the package name.
   - Confirm there is no `AGENTS.md` or `CLAUDE.md`, and that `globals.css` uses `@import "tailwindcss"` (v4).
3. **Copy it into `frontend/`**, including dotfiles:
   - `Copy-Item -Recurse "$S\rumor-zero-frontend\*" frontend\ ` and `Copy-Item "$S\rumor-zero-frontend\.gitignore" frontend\ `.
   - First confirm the template contains no `.env*` file, so nothing collides.
   - Append `!.env.example` to `frontend/.gitignore`. Add `.nvmrc` (`24`).
4. **Install.** In `frontend/`:
   - `npm install`
   - `npm install --save-exact @tailwindcss/forms@0.5.11 material-symbols@0.47.5`
   - `npm install -D --save-exact @types/node@24.19.0 vitest@5.0.3 @vitejs/plugin-react@6.1.1 jsdom@30.1.1 @testing-library/react@16.3.3 @testing-library/dom@10.4.2 @testing-library/user-event@14.6.7 @testing-library/jest-dom@7.0.1 prettier@3.9.9 prettier-plugin-tailwindcss@0.8.1`
   - Add `vite-tsconfig-paths@6.1.1` **only if** Vite 8's native `resolve.tsconfigPaths` doesn't resolve
     `@/` in Vitest.
   - Scripts: `dev`, `build`, `start`, `lint` (`eslint`), `lint:tokens` (`node scripts/lint-tokens.mjs`),
     `typecheck` (`tsc --noEmit`), `test` (`vitest run`), `test:watch`, `format`, `format:check`.
5. **Test tooling.**
   - `vitest.config.mts`: react plugin, `environment: "jsdom"`, `setupFiles: ["src/test/setup.ts"]`,
     `@/` alias. `src/test/setup.ts` loads jest-dom (`@testing-library/jest-dom/vitest`) and RTL cleanup.
   - If jsdom lacks `HTMLDialogElement.showModal/close`, polyfill it there by toggling `open` and
     dispatching `close`.
   - Add `react/no-danger` to `eslint.config.mjs`. Add the Prettier config, then run `npm run format` once.
6. **Theme: `globals.css`.**
   - `@import "tailwindcss"; @plugin "@tailwindcss/forms" { strategy: class; }`
   - `@theme` holds the resets above, then:
     - all 48 colour tokens (`--color-<name>`, exact hex)
     - 13 `--text-<name>` tokens with `--line-height`, `--letter-spacing` and `--font-weight`
     - 13 `--font-<name>` family tokens pointing at the next/font variables (in `@theme inline`), named
       exactly as Stitch's `fontFamily` keys
     - `--radius-lg`, `--shadow-sm`
     - `--spacing-space-{xs,sm,md,lg,xl}`, `--spacing-gutter`, `--spacing-gutter-mobile`,
       `--spacing-margin`, `--spacing-margin-mobile`
     - `--container-{reading,wide,form,modal}`
   - Base layer:
     - `body { bg-surface text-on-surface font-body-md text-body-md }`, antialiased
     - the global focus-visible outline and button cursor
     - `@media (prefers-reduced-motion: reduce)` disabling animations and transitions
     - No scrollbar hiding.
7. **Fonts and icons: `layout.tsx`.**
   - `next/font/google`, each with `display: "swap"` and `subsets: ["latin"]`:
     - Inter → `--font-inter`
     - JetBrains_Mono → `--font-jetbrains-mono`
     - Newsreader with `style: ["normal","italic"]`, `axes: ["opsz"]` → `--font-newsreader`
   - Put the variables on `<html>`. `import "material-symbols/outlined.css"`.
   - `Icon`: `name`, `size` (xs .75 · sm .875 · md 1 · lg 1.125 · xl 1.25 · 2xl 1.5 · 3xl 2rem, as
     DESIGN-sanctioned `text-[…]` classes), `filled` (`[font-variation-settings:'FILL'_1]`), and
     `label` (→ `role="img"`, `aria-label`; otherwise `aria-hidden`).
8. **lib helpers.**
   - `cn(...)` joins truthy class strings (no dependency; no tailwind-merge).
   - `format.ts`:
     - `formatRelativeTime(iso, now)`: `now`, `5m`, `3h`, `2d`, then `Sep 30` or `Sep 30, 2025`, UTC.
     - `formatCompactNumber(n)`: `Intl` en-US compact, e.g. 1.2K.
     - `formatConfidence("94.00")` → `94%`.
   - `password-strength.ts` returns `0 | 1 | 2 | 3 | 4`:
     - 0: empty
     - 1 Weak: fewer than 8 characters, or only one character class
     - 2 Fair: 8+ characters and 2+ classes
     - 3 Good: 12+ characters and 2+ classes, or 8+ and 3+ classes
     - 4 Strong: 16+ characters, or 12+ and 3+ classes
     - The classes are lower, upper, digit and symbol.
   - `post-display.ts`: `stripeTone({postType, status, emergencyActive})` and `statusBadgeSpec(...)`,
     implementing the ARCHITECTURE §4 badge table (below).
9. **Primitives** (verbatim Stitch classes from the files named in task.md, using the canonical
   variants above):
   - **Button:** primary, secondary, ghost, destructive and icon, plus sizes `md` and `block` (`w-full h-11`).
     `loading` shows a spinner, sets `aria-busy` and disables the button. `buttonClasses()` is exported.
   - **Form fields:**
     - TextField / Textarea / Select: bound `<label htmlFor>`, a `hint` or `error` (`aria-invalid`,
       `aria-describedby`, `text-error`), optional leading/trailing adornments.
     - Textarea: variants `bare` (b2 composer) and `filled` (c2), plus a `current / max characters`
       counter that turns `text-error` over the limit.
     - PasswordField: TextField plus a toggle with `aria-pressed` and "Show password" / "Hide password".
       It swaps the `visibility_off`/`visibility` icon and colours it `text-secondary` while shown.
   - **Choice controls:**
     - Checkbox: `form-checkbox` a3/c2 classes, label and description.
     - RadioCardGroup: `fieldset`/`legend`, `form-radio` d1 classes, checked card via
       `has-checked:border-secondary has-checked:bg-secondary/5`.
     - Toggle: b2 switch wrapped in a `<label>`, input `role="switch"`, a visible
       `peer-focus-visible` ring, `tone` secondary (default) or tertiary (emergency).
   - **Navigation-style controls:**
     - Tabs: ARIA tablist, roving tabindex, ←/→/Home/End, automatic activation, optional counts.
     - SegmentedControl: `radiogroup` with `role="radio"`, arrow keys; `value` may be `null` (no
       pre-selection, ANALYSIS b-2).
     - FilterChips: `aria-pressed` buttons, single or multi select, optional dot tone and count.
   - **Post display:**
     - Card: `interactive` → `hover:border-outline/50 transition-all`.
     - VerdictStripe: `absolute left-0 top-0 bottom-0 w-1 bg-<tone>`.
     - CategoryChip: FACT or OPINION.
     - Avatar:
       - `name`, optional `src`, sizes 6/8/10/14/20 (Tailwind units, i.e. 24–80 px), `decorative`.
       - A photo is an `<img>` with width/height and `rounded-full object-cover border-outline-variant/40`.
       - Initials (first letters of the first two words, else the first two characters) on
         `inverse-surface`.
       - Falls back on error, and resets when `src` changes.
   - **Modal:** props `open`, `onClose`, `title` (→ `aria-labelledby`), optional icon, `footer`. Uses the
     b2 header, body and footer classes and `max-w-modal`.
   - **Feedback:**
     - Alert: `info` (secondary), `error` (`role="alert"`), `warning` (verdict-review, ink
       `on-verdict-review`), `success` (primary), `neutral` (a5); optional dismiss.
     - Toast; Skeleton (`bg-surface-container rounded-lg animate-pulse motion-reduce:animate-none`).
     - EmptyState: b1 "caught up" layout, taking a glyph, title, text and action.
   - **Progress and lists:**
     - LoadMore: b4 button, loading state, end note.
     - ProgressBar: c2 track and fill, `role="progressbar"` with `aria-valuenow`, tone prop.
     - PasswordStrengthMeter: a2 layout, 4 segments. Colours: Weak = error, Fair = verdict-review,
       Good/Strong = primary. The label sits in a polite live region and the bar is `aria-hidden`.
   - **Containers:** Divider (optional label), DangerZone (c2 card shell).
10. **StatusBadge**, following the ARCHITECTURE §4 table. The base is `inline-flex items-center gap-space-xs
    px-space-sm py-0.5 rounded-lg font-label-code text-label-code font-bold uppercase border`:
    | Row | Label | Glyph | Tone |
    |---|---|---|---|
    | pending | CHECKING FACTS… | `progress_activity` spinning (`motion-reduce:animate-none`) | dashed neutral |
    | published opinion | no badge (the OPINION CategoryChip only) | none | none |
    | verified_true, pipeline | VERIFIED 94% | `check_circle` | primary |
    | verified_true, moderator | VERIFIED · REVIEWED | `check_circle` | primary |
    | verified_false, pipeline | FALSE 88% | `cancel` | error |
    | verified_false, moderator | FALSE · REVIEWED | `cancel` | error |
    | under_review | UNDER REVIEW (optional `AppealPendingBadge`) | `hourglass_top` | verdict-review |
    | removed | REMOVED | `block` | `text-outline bg-surface-container border-outline-variant` |
    | active emergency | `EmergencyBadge` EMERGENCY | `bolt` | tertiary |

    A % appears only when `verdict_source=pipeline` and a score is present.
11. **PostCard** (`features/posts`, b1 structure):
    - Props mirror the §9 Post object in camelCase (`author`, `content`, `postType`, `status`,
      `confidenceScore`, `verdictSource`, `emergencyActive`, `createdAt`) plus `now?`.
    - Structure: Card + VerdictStripe (tertiary when an emergency is active and the post isn't
      removed) + header (Avatar, name, @handle · relative time) + right-hand group (CategoryChip +
      StatusBadge + EmergencyBadge).
    - Claim text:
      - facts: `<blockquote>` with “…” and `font-claim-headline text-claim-headline`
      - opinions: `font-claim-opinion text-claim-opinion italic`
      - both: `whitespace-pre-wrap break-words`
    - `removed` renders a c1-style tombstone, "This post was removed by a moderator.", with no stripe.
    - No action bar and no source line yet.
12. **`/dev/ui` gallery.** Show every primitive in every state (sizes, variants, disabled, error,
    loading), plus four "Stitch fidelity" sections: the b1 PostCards (all 9 badge rows and the
    emergency card), the a2 sign-up fields, the d1 radio list, and the b2 modal (open button).
13. **`scripts/lint-tokens.mjs`** (Node, no dependencies).
    - It scans `src/**/*.{ts,tsx,css,mjs}` and exits 1 with `file:line` for any of:
      - raw hex outside the `@theme` block in `globals.css`
      - default-palette colour utilities, including `white`/`black`, with any variant prefix and with
        `bg`, `text`, `border`, `ring`, `fill`, `stroke`, `divide`, `outline`, `decoration`, `from`,
        `via`, `to`, `placeholder`, `accent`, `caret` or `shadow`
      - arbitrary colours (`-[#…]`, `-[rgb(…)]`)
      - radius utilities other than `rounded-lg` / `rounded-full`
      - shadows other than `shadow-sm`
      - generic sizes (`text-xs` … `text-9xl`) and families (`font-sans`, `font-serif`, `font-mono`)
      - `dangerouslySetInnerHTML`
    - An allowlist, empty for now, is kept for the 0D generated files (`src/lib/brand-assets.json`,
      `src/app/manifest.ts`).
    - A Vitest test runs it against good and bad fixture strings.
14. **Validate** (see Verification), then update the docs listed above. Record deviations in task.md:
    - the temp-dir scaffold
    - the dropped `--turbopack` flag, plus `--empty` and `--no-react-compiler`
    - the forms class strategy
    - the meter scale
    - PostCard's placement
    - `ui/` DangerZone and Divider
    - the shadow-sm override
    - the version bumps
    Tick the criteria and set the status in both places, then write HANDOFF and stop.

## Required tests (Vitest + RTL, next to the code)

- **Every primitive:** a render test plus a test per variant or state.
- **Modal:** `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, focus moves inside on open, Esc
  calls `onClose`, focus goes back to the trigger.
- **Keyboard:** Tabs and SegmentedControl arrows, Home/End and roving tabindex.
- **PasswordField:** the show/hide toggle flips `type`, `aria-pressed` and the label.
- **StatusBadge:** a table-driven test over all 9 rows (glyph, label, % only where applicable, the
  emergency row), plus an assertion that no rendered output contains /debunk/i.
- **Avatar:** initials with no `src`; initials after the `<img>` fires `error`; a photo when it loads.
- **PostCard:** the violet stripe and EMERGENCY chip when an emergency is active; the status stripe
  otherwise; the removed tombstone.
- **Unit:** `cn`, `format` (with a fixed `now`), `scorePassword` boundaries, `post-display`, lint-tokens
  fixtures.
- **`/dev/ui` page:** calls `notFound()` under `vi.stubEnv("NODE_ENV", "production")`.

## Verification (in `frontend/`)

1. `npm run lint`, `npm run lint:tokens`, `npm run typecheck`, `npm test`, `npm run format:check`,
   `npm run build`: all pass.
2. `npm run dev` → `/dev/ui` returns 200. `npm run build ; npm start` → `/dev/ui` returns **404** and `/`
   returns 200 (`Invoke-WebRequest … -SkipHttpErrorCheck` isn't in PS 5.1, so use try/catch on the
   status code).
3. From the repo root:
   - `git check-ignore frontend/.env.example` prints nothing.
   - `Test-Path frontend/AGENTS.md, frontend/CLAUDE.md` → False, False.
   - `git status` shows only the expected new and edited files; `frontend/.env.local` is still ignored
     and untouched.
4. **Visual check at 1280 px:** open each Stitch `code.html` (b1, a2, d1, b2) next to
   `http://localhost:3000/dev/ui`. The agent records it in HANDOFF as done, or as left for the user if
   no browser is available.

## Stop conditions (stop, record in HANDOFF, ask the user)

- create-next-app 16.3.x output differs materially: it writes AGENTS.md/CLAUDE.md, it isn't Tailwind v4,
  or it generates `.env*` files.
- A pinned package is missing, or its peer ranges conflict (vitest ↔ vite ↔ plugin-react, jest-dom 7).
- Any step would need to read, move or edit `frontend/.env.local` or `backend/.env`.
- A dependency beyond the list above is needed (beyond vite-tsconfig-paths as a fallback).
- A Stitch class can't be expressed with the tokens and DESIGN.md-sanctioned arbitrary values.

## Follow-ups (not in 0B)

- Part 16: subset the 4 MB Material Symbols font to the glyphs used.
- Part 1: revisit `scorePassword` against the final allauth/Django validators.
- 0C: CI runs `lint:tokens` and `format:check`; Playwright takes over the visual smoke test.
