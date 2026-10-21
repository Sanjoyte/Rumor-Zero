# Rumor Zero: Pre-Build Analysis

**Product:** Rumor Zero · **slug:** `rumor-zero` (use `rumor_zero` only where Python or Postgres requires it)
**Inputs read:** `docs/fact-based-social-platform-architecture-guide.pdf` (all 32 pages, including Figures 1–2), every file in `design/stitch/` (17 `code.html`, 17 `screen.png`, and 2 byte-identical `DESIGN.md` files), and the logo files `design/logo.svg` and `design/logo.png` (added 2026-09-29).
**Verified on:** 2026-09-29. Versions, prices and free-tier limits below were re-checked on the web that day. Sources are listed in `docs/SETUP.md` and `docs/ENV_GUIDE.md`.
**Changed on 2026-09-29:** you changed D4, D5 and D9. The whole doc set now follows your decisions; the details are in section f.

### Machine detected (all install steps target this machine)

| Item | Value |
|---|---|
| OS | Windows 11 Pro 10.0.26100, x64 (AMD64) |
| Shell | Windows PowerShell 5.1 (no PowerShell 7). Git Bash is also present. |
| Package manager | `winget` available |
| Already installed | Git 2.56, Docker Desktop (CLI 29.7.2), VS Code |
| **Not** installed | Python (only the Microsoft Store alias stub), Node.js / npm |

---

## Decisions you need to make

Each decision has a default. The rest of the docs (ARCHITECTURE, task.md) already assume the default, so you only need to act if you want something different. Rows marked **Changed by you** are no longer defaults: they record your decision.

| # | Decision | Default I used | Section |
|---|---|---|---|
| D1 | Auth library. simplejwt's maintainer organisation (Jazzband) is shutting down. django-allauth now has its own JWT support. | **allauth headless + its JWT strategy**, with a thin adapter that puts the refresh token in an httpOnly cookie. simplejwt is dropped. Fallback: simplejwt + custom views. | c-17, d |
| D2 | Transactional email. **Resend needs a domain you own** before it will send to anyone but you, and Render's free tier **blocks SMTP**. | Local: console backend (free). Production: **Brevo** HTTP API (300/day) with a verified single-sender address. Brevo may rewrite a Gmail "From" to its own shared domain, which hurts deliverability. Switch to Resend if you ever buy a domain (~US$10/yr). | c-22, ENV_GUIDE |
| D3 | Where the keep-alive and scheduled jobs run. GitHub Actions every 10 min exceeds a private repo's free minutes and is arguably outside GitHub's Actions terms. | **UptimeRobot** (free) pings `/api/health/` every 5 min, which also gives uptime alerts. **cron-job.org** (free) calls the hourly pipeline sweeper. A **daily** GitHub Actions workflow does the "deep" ping (DB + Redis). Works for public or private repos. | c-20 |
| D10 | Next.js on Cloudflare adapter. Cloudflare's docs now recommend **vinext** (1.0 released 2026-09-28, a Vite re-implementation). OpenNext is the mature path. | **OpenNext (`@opennextjs/cloudflare`) on Workers.** It runs the real Next.js build. Keep the code vinext-portable (no `'use cache'`, no `proxy.ts`/middleware, no R2) so switching later is cheap. | c-23 |
| D4 | Wording of the "false" badge | **Changed by you (2026-09-29): FALSE everywhere.** The backend enum values stay `verified_false` / `false` (already FALSE-based). Every human-readable label says FALSE: badges ("FALSE 88%", "FALSE · REVIEWED"), profile counters, the admin action "Mark FALSE", notifications and emails. Stitch's "DEBUNKED" is never used. (The guide says "Unverified / False".) | b-2, f |
| D5 | Stitch features the guide does not have (emergency mode, sources/DOI field, bookmarks, reposts, reputation scores, charts, photo avatars) | **Changed by you (2026-09-29): build them all, backend included.** Emergency posts (11C), source/DOI field (4–5), bookmarks and reposts (7B), credibility score (11B), charts (11D), photo avatars (14B). What is still dropped is listed in b-3. **Changed by you (2026-10-01):** up to 5 sources per fact post instead of one (f-3). | b-3, f |
| D6 | Can authors delete their own posts? | Yes, as a **soft delete**: hidden everywhere, but kept for the moderation audit trail. No editing. | b-2 |
| D7 | Daily limit on fact posts (shown in Stitch composer "3/10 remaining") | **Adopt it** as a config value: `FACT_POSTS_PER_DAY = 10`. **Changed by you (2026-10-08, Part 4):** it is a **rolling 24-hour** window, not a calendar day (no midnight burst, no time-zone question); every fact post made in the window counts, **including deleted and removed ones**, so deleting and reposting can't get around it. The composer says "7/10 fact posts left" and, at 0, when the next slot frees up | b-3 |
| D8 | Copy tone. Stitch uses jargon ("cryptographic ledger", "epistemic", "dispatch"). | Rewrite in **plain language**, keeping the layout and visual design | b-5 |
| D9 | Logo | **Changed by you (2026-09-29): use the real logo**, `design/logo.svg` (the master; `design/logo.png` is an earlier raster version, kept untouched and unused). It replaces the styled-text wordmark and all six emblem tiles (four in code, two in screenshots). One `<Logo/>` component everywhere; every derived asset is generated by Part 0D. | e, f-8 |

---

## a) Stitch inventory

### a.1 What the Stitch HTML is built with

- **Tailwind Play CDN**: `<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries">`. It compiles in the browser at runtime and is not for production.
- **One inline `<script id="tailwind-config">`**, byte-identical in all 17 files. It has `darkMode:"class"` but there are no dark tokens and no `dark:` classes anywhere, so the design is light-only.
- **Fonts via Google Fonts `<link>` tags:** Inter (400/500/600/700), JetBrains Mono (400/600/700), Newsreader (roman 400/500/600, italic 400, opsz axis). Material Symbols Outlined is loaded **twice**, from two different axis URLs.
- **One identical `<style>` block:** a margin reset, `overscroll-behavior:none`, and `::-webkit-scrollbar{display:none}`. That last rule hides scrollbars globally, which is an accessibility problem, so we won't port it.
- **Small inline JS:**
  - a3 and a6: show/hide password.
  - a4: resend countdown, plus a "state switcher" design artifact.
  - b1: tab colour swap. It has a bug: the underline indicator never moves.
  - Inline `onclick` / `onsubmit="event.preventDefault()"` handlers in a2, a3, a5 and b1.
- **Inline `style="width:%"`** in b3 (lines 239, 279) and c2 (line 246), for progress bars.
- **Arbitrary Tailwind values:** icon sizes `text-[0.75rem…2rem]`, `z-[60]`, `h-[2px]`, `-bottom-[15px]`, `[font-variation-settings:'FILL'_1]` and `calc()` offsets. d1 uses `animate-in fade-in zoom-in-95`, which needs the `tailwindcss-animate` plugin. That plugin is not loaded, so those classes do nothing.
- **No default Tailwind palette** (`slate-*`, `gray-*`, `white`, `black`) is used anywhere. Every colour is a token, as DESIGN.md requires.
- **Desktop-only app shell:** fixed `w-64` sidebar and `pl-64` content, with no mobile variant. Only a1 is really responsive.
- **Images:** all `<img>` tags point at `lh3.googleusercontent.com/aida-public/...` (Stitch placeholder photos, never shipped). Stitch has no logo image; the real logo is `design/logo.svg` (D9, e.1).
- **Screenshots vs code:** several `screen.png` files show an older iteration.
  - a1, a2, b2 and d1 have brighter blue buttons and a violet toggle.
  - The root and b3 screenshots show emblem tiles ("RZ" monogram, checkmark) that are not in the code.
  - b3's screenshot has a different sidebar ("Feed" instead of "Home").
  - **`code.html` + `DESIGN.md` are authoritative; screenshots are only a visual reference.**

### a.2 Screens

"Shell" means the logged-in app shell (sidebar + top bar).

| ID | Folder | Screen | Shell | MVP plan |
|---|---|---|---|---|
| — | `code.html` (root) | "The Epistemic Charter & Color Architecture": design spec, status taxonomy, lifecycle, FAQ | yes | **Reference only.** Its taxonomy table and FAQ layout get reused for a plain "How verification works" page. |
| a1 | `a1_logged_out_home` | Logged-out landing: hero, 3 feature cards, 4 sample post cards, footer | no (own navbar/footer) | Convert (simplified), fed by the real public feed |
| a2 | `a2_sign_up` | Sign-up card: Google button, email, username (+availability), password (+strength), Turnstile note | no | Convert |
| a3 | `a3_log_in` | Log-in card: error banner, Google, email, password, remember-me, forgot link | no | Convert (drop remember-me and the attempt counter) |
| a4 | `a4_verify_email` | "Check your inbox": resend with countdown, browse read-only | no | Convert, plus the link-landing states it lacks |
| a5 | `a5_forgot_password` | Request reset link (success banner shown together with the form) | no | Convert (separate idle and success states) |
| a6 | `a6_reset_password` | New password + confirm, strength meter | no | Convert |
| b1 | `b1_home_feed` | Home feed: tabs Following / Recent, inline composer, 5 post cards (verified, FALSE, emergency, under review, opinion), "You're caught up" | yes | Convert, including the emergency card and "emergency active" banner (11C), the repost and bookmark actions (7B), and a one-line source under fact claims in the evidence-drawer style: the first source, then "+N more" (4). Drop the drawers' ledger/telemetry content. |
| b2 | `b2_post_composer_modal` | Composer modal: text + 500-char counter, Opinion/Fact segmented control, emergency toggle, source URL, daily quota | yes (inert) | Convert all of it: the optional source URL/DOI field, turned into a list of up to 5 fields with "Add another source" (4), and the emergency toggle for fact posts (11C, copy rewritten). Keep the counter and quota. |
| b3 | `b3_post_detail_forensic_proof` | Post detail: claim, author, chart, "Verification Ledger" evidence section, appeal button, comments | yes | Convert the claim, verdict block, appeal button, flat comments, the primary-sources registry as a numbered source list (5; only the user's URLs/DOIs, no titles, org chips, "% match" or archive lines), repost/bookmark (7B), and the gauge, tiles and bar chart re-purposed as real check stats (11D). Drop the ledger and hashes. |
| b4 | `b4_search_results` | Search: tabs (Claims / Contributors / Sources), status filter chips, result cards, contributor spotlight, load more | yes | Convert posts tab, a people tab (with credibility score, 11B), type/status filter chips, and load more. Its sparkline is reused for the credibility trend (11D). Drop the claim-data box and contributor spotlight. |
| c1 | `c1_user_profile` | Own profile: header + counts, tabs, pending/verified/emergency/removed cards, 4 side widgets | yes | Convert header, counts, post list (with reposts), removed tombstone, emergency card, and the "Epistemic Standing" widget as the Credibility widget (11B/11D). Drop the other three side widgets. |
| c2 | `c2_account_settings` | Settings: identity/ORCID, security (SSO, 2FA, sessions), GDPR export, delete account | yes | Convert a subset: profile fields, profile photo (14B), email, change password, Google status, credibility history (14/11D), export, delete |
| c3 | `c3_following_list` | Followers / Following tabs, category chips, user rows with trust metrics | yes | Convert tabs and user rows with a Follow/Following button; the trust metric becomes the credibility score + verified count (11B). Drop chips. |
| c4 | `c4_notifications` | Notification list: unread chip, mark all read, filter tabs, 7 item types | yes | Convert the list and mark-all-read. Types rebuilt for the MVP (including repost and emergency priority removed). |
| d1 | `d1_report_post_modal` | Report modal: post preview, 5 reason radios, info callout | yes (inert) | Convert. Plain reason labels; add details textarea and already-reported/success states. |
| d2 | `d2_moderator_peer_review_queue` | Custom moderation queue with bulk actions, votes, SLA timers | yes | **Do not build.** The guide makes Django Admin the moderation panel. Used as a reference for admin list filters and actions, including "Retract Emergency Status" (→ Demote emergency, 11C). |

`epistemic_ledger/DESIGN.md` is a duplicate of `design/stitch/DESIGN.md`. Both describe the design system, whose name is "Epistemic Ledger".

### a.3 Reusable components (to become Part 0B/0C components)

| Component | Seen in | Notes for conversion |
|---|---|---|
| `AppShell` = `Sidebar` + `TopBar` (+ `UserCard`, `SearchInput`) | root, b1–d2 | Add tablet icon-dock and mobile bottom-nav variants (DESIGN.md "intended behavior"). Remove the "Verification Ledger" pill. Show "Moderation" only to moderators, linking to Django Admin. |
| `AuthCard` (`max-w-form`) + `Logo` | a2–a6 | The per-file emblem tiles (check, layers, diamond, lock) are all replaced by `<Logo/>` (D9, e.2). |
| `Logo` (wordmark / mark) | every brand-mark spot | The only brand mark in the UI (Part 0D; ARCHITECTURE §14) |
| `MarketingNav` / `MarketingFooter` | a1 | Links only to pages that exist (0C, user decision 2026-10-01): nav How it works, Log in, Sign up; footer How verification works, Privacy, Terms. About, Community Guidelines, Press and Contact are dropped (no part builds them) |
| `Button` (primary / secondary / ghost / destructive / icon) | everywhere | Primary = `bg-secondary`. There's one radius (`rounded-lg` = 4px) and one shadow (`shadow-sm`). |
| `TextField`, `PasswordField` (visibility toggle), `Textarea` (+ counter), `Checkbox`, `RadioCard` list, `Select` | a2, a3, a5, a6, b2, b3, c2, d1, d2 | Bind labels to inputs (`htmlFor`). c2 lacks this. |
| `PasswordStrengthMeter` (4 segments) | a2, a6 | Stitch is inconsistent: 3/4 means "Strong" in a2 but "Fair" in a6. Decided in Part 0B: one scale, Weak / Fair / Good / Strong (advisory). |
| `GoogleButton` + "or" `Divider` | a2, a3 | **Changed in Part 3:** Google's own rendered button (a Google Identity Services iframe) above the form, then the shared `Divider`; the inline "G" SVG and `data-rz-keep` are not used, because Google returns an ID token only from its own button. a3's uppercase code-font rule becomes a2's plain one. Hidden when `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is empty. `design/` is untouched. |
| `Alert` / `Callout` (info, success, warning, error) | a3, a4, a5, a6, c1, c2, d1 | Tints from verdict families: `secondary/10` info, `error/10` error, `verdict-review/10` warning |
| `PostCard` with 4px `VerdictStripe` | root, a1, b1, b3, b4, c1, d2 | Core component. Variants: opinion, pending, verified, false, under review, removed (tombstone) |
| `StatusBadge` (glyph + label + optional %) | root, a1, b1, b3, b4, c1, c4, d2 | See the status table in b-2 |
| `CategoryChip` (FACT / OPINION) | a1, b1, b3, b4, c1 | Neutral chip |
| `ActionBar` (like, comment, repost, bookmark, report, copy link) | a1, b1, b3 | Stitch never shows a real like toggle (b1 uses `fact_check` for the first counter). Define the liked state as a filled glyph in `secondary`. Repost = `cached` + count; bookmark = `bookmark_border`, filled `bookmark` when saved (7B). |
| `RepostButton`, `BookmarkButton`, `RepostHeader`, `UnavailablePostCard` | a1, b1, b3, c1 | ✅ Part 7B (c-39: no Stitch screen for the header, the stub or `/bookmarks`) |
| `ReportButton` (the flag), `ReportModal` | b1, b3, d1 | ✅ Part 8 (c-40: a flag button, not an overflow menu; no reason preselected) |
| `AppealButton`, `AppealModal`, `AppealOutcome`, `RemovedPostCard` | b3, c1, d1 | ✅ Part 11 (c-43: the button is b3's, the modal d1's pattern, the tombstone c1's with our `block` glyph) |
| `EmergencyChip` + violet stripe, `PinnedEmergencies` (banner) | b1, b2, c1 | ✅ Part 11C (c-45: the chip is Part 0B's `EmergencyBadge`; b1's dispatch banner became the pinned section's header with the copy rewritten; b2's toggle and warning box in the composer; `EmergencyNote` on the post page, neutral) |
| `SourceLink` | b1, b2, b3 | Part 4: one line with the first source's host or DOI, then "+N more" |
| `SourceList` | b3 | Part 5: numbered list of every source (01, 02 …), full value, open-in-new link |
| `CredibilityBadge`, `CredibilityWidget`, `CredibilityPanel` | c1, c2, c3, b4 | ✅ `CredibilityBadge` Part 11B (c-44: c1's meta row and c3's row metric, both neutral); the widget and panel 11D |
| Chart primitives `MeterBar`, `StatTile`, `BarChart`, `RingGauge`, `Sparkline` | b3, c1, b4, c2 | Part 11D; token-built HTML/SVG, no chart library |
| `AvatarUploader` | c2 | Part 14B |
| `Tabs` (underline + count), `SegmentedControl`, `FilterChips` | b1, b4, c1, c3, c4, d2, b2 | Fix the b1 underline bug |
| `Toggle` switch | b2 | Used by the composer's emergency toggle (11C); also available for settings. |
| `Modal` + scrim (`max-w-modal`, `z-[60]`) | b2, d1 | Use the native `<dialog>` for focus trap, Esc and `aria-modal` (d1 lacks `role="dialog"`) |
| `Avatar` (photo, or initials on `inverse-surface`) | everywhere | The user's profile photo when set (14B), initials otherwise and on load error. Stitch's placeholder `<img>` photos are never shipped. |
| `CommentItem`, `CommentComposer` | b3 | Flat list, no "Reply" |
| `UserRow` (+ Follow button) | c3, b4 | |
| `NotificationItem` | c4 | |
| `EmptyState` / end-of-list | b1, b4, c4 | Stitch has only "caught up" states. The rest are defined in b-2. |
| `LoadMore` button | b4 | Cursor pagination |
| `DangerZone` card | c2 | |
| `StatTile`, `DataTable`, `Accordion` | root, d2, b3 | The "How verification works" page; `StatTile` also for the post check stats (11D) |
| Missing everywhere: `Toast`, `Tooltip`, `Skeleton`, `DropdownMenu` | — | Designed from the tokens in Part 0B |

### a.4 Design tokens (from DESIGN.md frontmatter = the coded `tailwind.config`)

**Colors (49 tokens).** Only the verdict families carry chroma. Everything else is neutral.

| Role | Token → hex |
|---|---|
| Canvas / surfaces | `surface` / `background` / `surface-bright` #faf8ff · `surface-dim` #d2d9f4 · `surface-container-lowest` #ffffff · `surface-container-low` #f2f3ff · `surface-container` #eaedff · `surface-container-high` #e2e7ff · `surface-container-highest` / `surface-variant` #dae2fd |
| Text | `on-surface` / `on-background` #131b2e · `on-surface-variant` #3c4946 · `outline` #6c7a76 · `outline-variant` #bbcac5 |
| Inverse | `inverse-surface` #283044 · `inverse-on-surface` #eef0ff · `inverse-primary` #59dbc7 |
| **Verified (Fact Teal)** | `primary` / `surface-tint` #006b5f · `on-primary` #ffffff · `primary-container` #00a896 · `on-primary-container` #00352e · `primary-fixed` #79f7e3 · `primary-fixed-dim` #59dbc7 · `on-primary-fixed` #00201c · `on-primary-fixed-variant` #005047 |
| **Actions (Protocol Blue)** | `secondary` #006398 · `on-secondary` #ffffff · `secondary-container` #5bb8fe · `on-secondary-container` #00476e (hover) · `secondary-fixed` #cce5ff · `secondary-fixed-dim` #93ccff · `on-secondary-fixed` #001d31 · `on-secondary-fixed-variant` #004b73 |
| Emergency Violet (active emergency posts, 11C) | `tertiary` #732ee4 · `on-tertiary` #ffffff · `tertiary-container` #a87dff · `on-tertiary-container` #3c0088 · `tertiary-fixed` #eaddff · `tertiary-fixed-dim` #d2bbff · `on-tertiary-fixed` #25005a · `on-tertiary-fixed-variant` #5a00c6 |
| **False (Alert Red)** | `error` #ba1a1a · `on-error` #ffffff · `error-container` #ffdad6 · `on-error-container` #93000a |
| **Under review (Amber)** | `verdict-review` #F4A261 (fills, stripes, borders only; ~1.9:1 on white) · `on-verdict-review` #9a4a12 (all amber text and icons) |

**Typography.** Every size token also sets its weight, line height and tracking.

| Token | Family | Size / line-height | Weight | Tracking | Use |
|---|---|---|---|---|---|
| `display-hero` | Newsreader | 3.5rem / 4rem | 600 | -0.03em | marketing hero |
| `display-hero-mobile` | Newsreader | 2.25rem / 2.75rem | 600 | -0.02em | hero < md |
| `headline-lg` | Newsreader | 2.25rem / 2.75rem | 500 | -0.02em | page H1 |
| `headline-md` | Newsreader | 1.75rem / 2.25rem | 500 | -0.01em | auth titles, sections |
| `headline-sm` | Newsreader | 1.25rem / 1.75rem | 600 | -0.01em | card/modal titles, wordmark |
| `claim-headline` | Newsreader | 1.375rem / 1.875rem | 500 | -0.01em | **fact** post text (upright) |
| `claim-opinion` | Newsreader | 1.375rem / 1.875rem | 400 | -0.005em | **opinion** post text (+ `italic`) |
| `body-lg` | Inter | 1.125rem / 1.75rem | 400 | — | lead paragraphs |
| `body-md` | Inter | 0.9375rem / 1.5rem | 400 | — | default copy, inputs, buttons |
| `body-sm` | Inter | 0.8125rem / 1.25rem | 400 | — | secondary copy, helper text |
| `label-badge` | Inter | 0.6875rem / 0.875rem | 600 | 0.03em | tiny chips |
| `label-code` | JetBrains Mono | 0.75rem / 1rem | 600 | 0.06em | uppercase system labels, tabs |
| `label-metric` | JetBrains Mono | 0.875rem / 1.25rem | 700 | — | numbers, confidence % |

**Radii:** `DEFAULT` 0.125rem · `lg` **0.25rem (4px)**, used for every card/button/input/badge · `xl` 0.5rem · `full` 9999px (avatars, dots, toggles, pills). Only `rounded-lg` and `rounded-full` are used.
**Spacing (named):** `space-xs` 0.25rem · `space-sm` 0.5rem · `space-md` 0.875rem · `space-lg` 1.25rem · `space-xl` 2rem · `gutter` 1.25rem · `gutter-mobile` 0.75rem · `margin` 2rem · `margin-mobile` 1rem.
**Max widths:** `reading` 760px · `wide` 1240px · `form` 480px · `modal` 620px.
**Elevation:** 1px hairlines (`outline-variant/30`). `shadow-sm` is the only shadow. Modal scrim is `inverse-surface/40`.
**Icons:** Material Symbols Outlined, one glyph per concept (list in DESIGN.md › Iconography). Sizes are 0.75–2rem.

### a.5 Converting Stitch to the guide's frontend stack

Target stack: Next.js (App Router, TypeScript, `src/`), Tailwind CSS v4, React components. Exact versions are pinned in SETUP.md.

1. **Tokens → Tailwind v4 `@theme`** in `frontend/src/app/globals.css`. v4 is CSS-first, so no `tailwind.config.js` is needed.
   - `colors` → `--color-<name>`
   - `fontFamily` → `--font-<name>`
   - `fontSize` tuples → `--text-<name>` plus `--text-<name>--line-height` / `--letter-spacing` / `--font-weight`
   - `borderRadius` → `--radius-lg: 0.25rem` etc.
   - named spacing → `--spacing-space-md` etc.
   - `maxWidth` → `--container-reading` etc., which v4's `max-w-*` reads
   
   Then **class names from the Stitch HTML keep working as written** (`bg-surface-container-low`, `font-claim-headline text-claim-headline`, `px-space-md`, `max-w-reading`). This is the single biggest conversion saving. Reset the default palette (`--color-*: initial`) so it can't creep back in.
2. **Plugins:**
   - `container-queries` is built into v4.
   - `forms`: decided in Part 0B: the `@tailwindcss/forms` plugin via `@plugin` with `strategy: "class"`, applied inside the primitives (Stitch used its global reset).
   - The CDN script and inline config are deleted.
3. **Fonts:** load Inter, JetBrains Mono and Newsreader with `next/font/google`. It self-hosts them at build time, so there are no runtime Google requests, no layout shift, and it's free. Material Symbols get self-hosted too (method in SETUP.md Part B), with a small `<Icon name="…"/>` component.
4. **HTML → JSX:**
   - `class` → `className`, `for` → `htmlFor`, self-close void tags.
   - Inline `onclick` scripts → React state.
   - Inline `style=width%` → a `ProgressBar` component (or a CSS variable).
   - Repeated markup (sidebar, cards, badges) → components with props, so each screen becomes composition, not copy-paste.
5. **Remove:** the scrollbar-hiding CSS, all Stitch placeholder `<img>` avatars (→ `Avatar`: the user's photo from 14B, or initials), the text wordmark and emblem tiles (→ `<Logo/>`), sample data, design artifacts (a4 state switcher, d1 "Governance preview" toggle, "Simulate link click"), and the dead `animate-in` classes.
6. **Add what Stitch lacks:**
   - responsive shell
   - loading skeletons, toasts, empty/error states
   - focus-visible styles
   - `<dialog>` accessibility
   - `prefers-reduced-motion` for spinners
7. **Where it lives:** `frontend/src/components/ui/` for primitives, `frontend/src/components/shell/` for layout, `frontend/src/features/<domain>/` for screen-specific components (see STRUCTURE.md). `design/stitch/` stays read-only as the visual source of truth.

---

## b) Gap report

### b-1 Stitch screens the guide doesn't cover

| Screen | Proposed default (you can override) |
|---|---|
| a1 logged-out landing | Build it. Hero + 3 feature cards + a live preview of the public "Recent" feed (4 cards) + footer. |
| Root "Epistemic Charter" page | Don't build as-is: its content describes features we don't have (cryptography, ledgers, trust tokens). Build **"How verification works"** (`/how-it-works`) reusing its taxonomy-table and FAQ layout, with copy rewritten for the real lifecycle, including emergency posts, reposts and how the credibility score is calculated (f). |
| a5 / a6 password reset | Build them. The guide mentions resets only in passing (4.3); allauth provides the flow. |
| b1 "Recent wire" tab | Add a public global feed (`GET /api/v1/posts/`, all non-removed posts, newest first). New users with zero follows would otherwise see an empty home feed, and a1 needs it too. |
| b4 search tabs/filters | Keep a Posts tab (Postgres full-text search) and a People tab (username/display-name prefix match, showing the credibility score), with filter chips for type (fact/opinion) and status. Drop Primary Sources, certainty sort, the claim-data box, and the contributor spotlight (ranking people by score adds legal risk, guide §16). |
| c2 settings | Keep display name, username, bio (280 chars), **profile photo** (14B), email (read-only), change password (email accounts only), "Signed in with Google" status, **your credibility history** (11D), **download my data (JSON)** and **delete account** (the guide's §16 GDPR/CCPA note). Drop ORCID, affiliation, 2FA, sessions list, and privacy toggles. |
| c3 following list | Build Followers and Following tabs with user rows and Follow/Following buttons; the "Audit Trust" metric becomes the credibility score + verified count (11B). Drop category chips, in-list filter, tier labels, and the directory banner. |
| c4 notifications | Build it. Types: new follower, like, comment, repost, verdict reached, post under review, post removed, emergency priority removed, appeal resolved. "Mark all as read" and per-item read on click. Drop the filter tabs and "Mentions" (no mentions feature). |
| d2 moderator queue | **Don't build** (Django Admin per guide §8). Borrow its ideas for the admin: list filters by reason (pipeline / reports / appeal), sort by report count or time in queue, bulk actions (Mark verified, Mark FALSE, Dismiss reports, Remove, Demote emergency, Restore post). |

### b-2 Guide features with no (or incomplete) Stitch design

| Feature | What Stitch has | Proposed default |
|---|---|---|
| Fact/opinion selector | b2 segmented control (good) | Keep it. Require an explicit choice (no pre-selection), then submit. Labels: "Opinion" / "Fact". The button reads "Post opinion" or "Post fact — will be checked". |
| **Pending badge** ("Checking facts…") | Only c1's "Verifying with Ledger Nodes" and the charter's "Verifying" row | Neutral chip with a dashed `outline-variant` border, spinning `progress_activity` glyph (static if reduced-motion), label **CHECKING FACTS…**. Stripe: `outline-variant`. |
| Verified badge | Yes (`check_circle`, primary) | **VERIFIED 94%**. When a moderator decided it: **VERIFIED · REVIEWED**, no %. |
| False badge | "DEBUNKED" (`cancel`, error) | **FALSE 88%** (D4, decided by you: FALSE everywhere, never "debunked"). Moderator-decided: **FALSE · REVIEWED**, no %. The claim is **not** struck through (b1 does this), because readers still need to read it. |
| Under-review badge | Yes (`hourglass_top`, amber) | **UNDER REVIEW**, no % (guide §5.3) |
| Opinion | Category chip only | **OPINION** chip, no status badge, italic serif text (DESIGN.md) |
| Removed | c1 tombstone card | Public: the post drops out of feeds and search. Its URL shows "This post was removed by a moderator." Author: same card, plus their text and the reason. **Built in Part 5 (user decision 2026-10-09):** the public gets the same keys with the text, sources, note, confidence and verdict source blanked (author name and date stay). **Built in Part 11 (c-43):** the author sees their text marked "Only you can see this text.", the reason (`removal_reason`), their own profile lists the post, and the appeal button or chip and outcome are on the card and the post page (`RemovedPostCard`). |
| Status updates while pending | "POLLING T+18M" in b1 | Poll `GET /api/v1/posts/status/?ids=…` for visible pending posts every 10 s, backing off to 60 s and stopping after 10 min |
| Report modal | d1 (good) | Plain-language reasons (b-5). Add an optional "details" textarea, required for "Other". Add states: submitting, success toast, **already reported** (disabled button "You reported this"), and "verify your email to report". **Built in Part 8 (c-40).** |
| **Appeal ("Request another look")** | Only a button in b3 and c1 | Small modal in the report-modal style with an optional "Why should we look again?" textarea (≤500 chars). The author sees an **APPEAL PENDING** chip (amber). Allowed on the author's own `verified_false` posts **and removed posts** (removals lower the public credibility score, f-2), one open appeal per post, and at most one appeal per post in total (MVP). **Built in Part 11 (c-43):** `AppealButton` (b3's label without "/ APPEAL VERDICT"), `AppealModal`, the chip, and a one-line outcome; a FALSE post's button sits at the bottom of the verdict card, a removed post's in its card. |
| Sign-up states | Only happy path + "username available" | Field errors (email taken, username taken/invalid, weak password), Turnstile failure, submit loading/disabled |
| Log-in states | Error banner | Keep the banner. Drop "Attempt 1 of 5" (the rate limiter answers generically). Add a rate-limited message and a loading state. Drop "Remember me": refresh tokens already last 14 days. |
| Email verification | a4 "check inbox" only | Add `/verify-email/[key]` landing states: verifying…, **verified** (CTA "Start posting"), **expired/invalid** (CTA "Send a new link"). Add an app-shell banner for unverified users: "Verify your email to post, comment and report" + Resend. |
| Google sign-in, new user | — | No extra step. **Changed 2026-10-07 (Part 3):** the username is generated from Google's **first name** (`ada`, `ada_4821`, or `member_xxxxxx`), never from the email address, because the handle is public and emails never are; it can be changed in Settings (Part 14). The display name stays blank: nothing from the Google profile becomes public until the user chooses it. |
| Password reset | a5/a6 | a5 split into idle and sent states. Add a6 states: mismatch, weak, expired link, success (→ logged in). |
| Like | Counts only | Toggle button with an outline glyph; liked = filled `favorite` glyph in `secondary`. Count next to it. |
| Comments | b3 list + composer | Flat list, newest last, 500-char limit, delete own. Drop Reply, comment IDs, comment likes and comment reports (not in the guide). Moderators can hide comments in the admin. |
| Follow button | c3 "Following" | Follow (primary) / Following (secondary; hover says "Unfollow") |
| Empty / loading / error | Almost none | Skeleton cards (`surface-container` blocks), `EmptyState` with a glyph + one line + CTA, and an error `Alert` with "Try again" |
| 404 / 500 pages | none | Centered auth-card-style message |
| Toasts | none | `inverse-surface` toast, bottom-center, 4 s |
| Privacy Policy, Terms | Footer links only | Plain reading-width pages. Placeholder text marked "needs legal review" (guide §16). |
| Responsive / mobile | Not implemented (DESIGN.md describes intent) | ≥1280px: full rail. 768–1279px: 64px icon dock. <768px: top bar + bottom nav (Home, Search, New post, Notifications, Profile). |
| Moderation panel | d2 | Django Admin, no design needed. Header text "Rumor Zero moderation". |

### b-3 Stitch features beyond the guide's MVP (D5 changed by you: now built)

The original default was "drop all". Since 2026-09-29 the seven features you named are built; the rest stays dropped.

| Feature (Stitch label) | Where | Decision |
|---|---|---|
| Emergency mode / "Unverified — Emergency" / violet status / fast-track | root, b1, b2, c1, c4, d2 | **Built (11C)**, redesigned: a flag on fact posts, pinned 24 h, still fact-checked, abuse safeguards (f-1). Stitch's "bypass verification", "trust tokens", "permanent emergency marker" and "request expedited audit" are not adopted. |
| Source URL / DOI field | b1, b2, b3, b4, c1 | **Built (4–5)**: up to 5 optional, validated sources per fact post, never fetched (f-3). b3's source registry becomes the plain numbered list. The CITATION / DATASET / SCOPE buttons, registry metadata (titles, org types, "% match", archive hashes) and "N sources" counts on profiles and search are dropped. |
| Avatar upload | c2 | **Built (14B)** as real profile photos (f-7) |
| File/PDF attachments, dataset uploads, data archive `.zip` | b1, b3, c1, c2, d2 | Still dropped: posts stay text-only. The data export is JSON. |
| Charts, sparklines, gauges, consensus metrics | b3, b4, c1, c2 | **Built (11D)**, re-purposed for data we really have (f-6). The claim-data telemetry boxes (b1, b4) are dropped: there is no claim dataset. |
| Hashes, "cryptographically sealed", Merkle, blocks, protocol versions, "Verification Ledger" | everywhere | Still dropped, including the top-bar pill |
| Affiliation, credentials, ORCID, role/tier badges, verified-author seal | b1, b3, b4, c1, c2, c3 | Still dropped. `display_name` + `bio` (+ photo) only. |
| Reputation ("Audit Trust", "Epistemic Standing", "Credibility Index") | b4, c1, c2, c3 | **Built (11B)** as the **Credibility score** (f-5) |
| Reposts / "Citations" count, bookmarks | a1, b1, b3 | **Built (7B)**; the counter is called "Reposts" (f-4). Share counts stay dropped; the client-side **"Copy link"** action stays (guide §1.1). |
| Contributor spotlight "Relevant Verified Contributors" | b4 | Still dropped: ranking people by score adds legal risk (guide §16) |
| Topic tags / "Discourse category" | a1, b1 | Still dropped |
| Peer votes, quorum, SLA timers, auditor notes | c1, d2 | Still dropped. The only "priority" is emergency priority in the admin queue (11C). |
| "Submit citation", "Counter-perspective", "Request expedited audit" buttons | b1 | Still dropped |
| Nested replies, comment likes/reports/IDs | b3 | Still dropped |
| "Pending visible only to author" | c1 | **Contradicts guide §5.2** (pending posts are public with a badge). Follow the guide. |
| "Public engagement disabled during review" | c1 | Dropped. Likes, comments and reposts are allowed on every visible post (reposts not on FALSE-labelled ones, f-4). |
| Daily fact quota "3/10 remaining" | b2 | **Adopt** (D7, changed 2026-10-08): `FACT_POSTS_PER_DAY = 10` per **rolling 24 h**, shown in the composer as "7/10 fact posts left"; deleted and removed fact posts still count; emergency posts count toward it |
| Login "Attempt 1 of 5", "Remember me 30 days" | a3 | Dropped |
| Notification filter tabs, "Mentions", preferences | c4 | Dropped |
| 2FA, sessions list, SSO disconnect | c2 | Dropped |

### b-4 Contradictions with "text-only"

"Text-only" now means: **posts and comments are text-only**. The only images are profile photos and the site logo.

- **Photo avatars:** `<img>` from `lh3.googleusercontent.com` in the sidebar of all 11 app-shell files, plus b1 (3 portraits, only `data-alt`, no `alt`), b3, c1 and c4 (2). → **Allowed since D5 changed**: real profile photos (14B), re-encoded on the server, initials as the fallback. Stitch's placeholder URLs are never shipped. The unused `users.avatar_url` column becomes `avatar_version` (ARCHITECTURE §2).
- **Charts and data visuals:** b3 bar chart, b4 sparkline SVG, c1 ring gauge, b3/c2 progress bars. → **Allowed** as UI built from our own numbers (11D), never user content.
- **Attachments and uploads:** c1 "Raw Telemetry Appendix (PDF, 4.2 MB)", d2 "…Refutation.pdf (2.4 MB)", b1 "DATASET", b3 "Attach data table", c2 ".zip" archive. → Still dropped. The only upload is the profile photo.
- **Brand SVG:** the Google "G" in a2/a3 is a third-party brand mark required on the Google button. It is **allowed**: it is UI, not user content. Our own logo (`design/logo.svg`, D9) is the other allowed brand image.

### b-5 Copy and terminology (D8)

| Stitch | Proposed |
|---|---|
| "Submit Claim", "BROADCAST CLAIM", "Compose dispatch" | "New post" (posts can be opinions too) |
| "Dispatches" (comments), "Remark" | "Comments", "Comment" |
| "Audit Queue" | "Moderation" (moderators only; opens Django Admin) |
| "Following dispatches" / "Recent wire" | "Following" / "Recent" |
| "Empirical Claim" / "Civic Opinion" | "Fact" / "Opinion" |
| Report reasons: "Empirical Inaccuracy / Factual Discrepancy", "Decontextualized Citation / Omission", "Harassment or Reputational Defamation", "Inauthentic Network / Coordinated Sybil Activity", "Other Governance Infraction" | "False or inaccurate" (`inaccurate`), "Missing context or misleading" (`misleading`), "Harassment or defamation" (`harassment`), "Spam or fake accounts" (`spam`), "Something else" (`other`, needs details) |
| "Submit Evidentiary" | "Submit report" |
| "Cryptographic …", "ledger", "protocol", "epistemic" | Remove |

---

## c) Inconsistencies in the guide, and how they're resolved

**Must fix before coding: data model and routing**

1. **`posts.status` lacks `published`** (§3.2), but §5.1 and §7.2 use it for opinions.
   → Final enum: `pending | published | verified_true | verified_false | under_review | removed`.
2. **The report threshold is time-windowed** ("5 reports within a 24-hour window", §6.2), but `report_count` is a lifetime counter (§3.2).
   → Keep `report_count` as the lifetime counter (display and admin sorting), updated in the same transaction as the insert, as the guide says. The **threshold check is a separate indexed count**:
   - it counts `reports` rows for that post that are `status='open'` and `counts_toward_threshold=true`, with `created_at >= now() - REPORT_WINDOW_HOURS`;
   - it runs inside the insert transaction after `SELECT … FOR UPDATE` on the post row, so two simultaneous reports can't both miss the threshold;
   - index `reports (post_id, created_at)`.
   
   It is a count over at most a handful of rows for one post, not a table scan, so the guide's performance concern doesn't apply. Redis is **not** used for correctness: a cache eviction must never lose a report.
3. **The §7.2 routing reads `flagged_reason` before it is set.** On the report path, the local variable `flagged_reason` was never assigned. The pseudo-code also has three logic bugs:
   - (a) `verdict='inconclusive'` with high confidence falls into the `else` of the ternary and becomes **`verified_false`**;
   - (b) a late pipeline result would **overwrite** `under_review` (reports), `removed`, or a moderator's decision;
   - (c) re-running routing on every report resets opinions to `published`.
   
   → Routing becomes a pure function `route(post, event) -> (status, flagged_reason)` that only reads and writes `post.*` fields. Rules:
   - opinions never enter the pipeline;
   - pipeline results are ignored for `removed` or moderator-decided posts (`verdict_source='moderator'`);
   - `inconclusive` → `under_review` (`pipeline`);
   - a low-confidence result on a post already under review for reports → `flagged_reason='both'`;
   - crossing the report threshold → `under_review`, with `flagged_reason` = `both` if it was `pipeline`, unchanged if it was `appeal`, otherwise `reports`; it never touches `removed`;
   - it is idempotent.
   
   Full table in ARCHITECTURE.md §4. This function gets exhaustive unit tests.
4. **Drafting artifact in §5.1 step 2:** "saved with status='verified_true'... actually, more precisely…".
   → Opinions are saved as `status='published'`. Nothing is ever created as `verified_true`.
5. **"Dismiss Reports (post stays as-is)" (§8.3)** is ambiguous, because reports have already moved the post to `under_review`.
   → Store `posts.pre_review_status` when a post enters review, and restore it on dismiss. Mark those reports `status='dismissed'` so they stop counting toward the threshold. If the flag was `both`, dismissing reports leaves the post under review with `flagged_reason='pipeline'`.
6. **The moderator verdict has no home in the schema.** Figure 2 says the moderator "sets a final label + confidence note", and §5.3 shows a % for every verdict.
   → Add `posts.verdict_source` (`pipeline | moderator`, nullable) and `posts.verdict_note` (public text, nullable). A moderator-set verdict shows "REVIEWED" with no %, because a pipeline score of 52% on a human-verified post would mislead.
7. **The appeal path (§8.4) has no schema.**
   → New table `appeals` (post, author, reason, status `open|upheld|overturned`, resolved_by/at, original_moderator). Add `flagged_reason` value `appeal`. `APPEAL_REQUIRE_DIFFERENT_MODERATOR = True` (senior moderators exempt).
8. **Missing tables:** notifications (§11), email-verification tokens (§4.3) and appeals are not in §3.
   → Added to the final schema. Email and reset tokens are handled by allauth (D1): its `EmailAddress` table plus signed, expiring keys.
9. **`moderation_actions.action = 'escalated'` has no defined flow.**
   → Admin action "Escalate to senior": sets `posts.escalated_at` and logs the action. Seniors get an "Escalated" list filter.
10. **`users.role` enum vs "implemented as two Django Groups" (§8.2)** is two sources of truth.
    → `role` is the source of truth. On save it syncs Group membership and `is_staff` (true for moderator/senior, and always for a superuser, whose role stays `user` after `createsuperuser`). Only seniors (and the superuser) can edit `role`.
11. **`users.password_hash` "null if OAuth-only"** vs Django, which stores `password` and marks OAuth-only accounts with an *unusable* password (never NULL).
    → Use Django's `password` field and `set_unusable_password()`.
12. **`users.oauth_provider` / `oauth_subject_id`** duplicate django-allauth's `SocialAccount (provider, uid)` table.
    → Don't add these columns. allauth's table is the record, with a unique `(provider, uid)` pair.
13. **Thresholds are "Django settings" (§6.2, §7.2) but also "adjusted by Senior Moderators" in the admin (§8.2).** Settings can't be edited at runtime.
    → Singleton model `PlatformSettings`, editable in the admin by seniors only. It is seeded from env defaults, read through a 60 s cache, and each change is logged.
14. **Figure 1 draws an arrow from the Next.js frontend to PostgreSQL**, contradicting §2 ("the frontend never touches them").
    → The frontend never connects to Postgres or Redis. Only via the API.
15. **Figure 1 draws Object storage → Fact-Check Pipeline.** R2 is Phase 2 and the §7.1 contract passes `content` directly.
    → No object storage in the MVP. Profile photos (D5) are small re-encoded WebP files stored in Postgres (f-7).
16. **§1.4 says Redis holds "sessions" and backs "the background-job queue"**, but §4.6 uses tokens and §5.4 decides on a DB queue.
    → Redis holds only the short feed cache and rate-limit counters. Admin sessions are DB-backed. The queue is the `posts` table.

**Must fix before coding: auth and security**

17. **Auth libraries.** The guide pairs simplejwt (tokens) with django-allauth (Google).
    - simplejwt: last release 5.5.1 (Jul 2025), no release supporting Django 6.x, and its home organisation Jazzband is winding down (announced 2026-03-14).
    - allauth 65.19.5: released 2026-09-28, supports Django 4.2–6.1, and since 65.13 ships **headless mode with a JWT token strategy**, covering signup, login, email verification, password reset, Google ID-token login and rate limits.
    
    → **D1 default:** allauth headless (`app` client) + `JWTTokenStrategy` (HS256). No simplejwt. It keeps the guide's design:
    - 15-min access token held in memory;
    - 14-day refresh token in an httpOnly cookie;
    - a thin adapter (~100 lines + tests) moves allauth's `refresh_token` from the JSON body into the cookie and back.
    
    Fallback if you want the guide's literal libraries: simplejwt + custom DRF views + `google-auth`.
18. **CSRF claim (§12):** "Django's CSRF protection still covers the refresh-token cookie endpoint." That's not automatic: DRF/allauth API views are CSRF-exempt.
    → Explicit protection, **widened in Part 1 to every unsafe request under `/api/auth/`** (login and signup too, not only the cookie-reading refresh and logout): allauth's app views parse any body as JSON whatever its Content-Type, so a cross-site `<form enctype="text/plain">` could post valid JSON to login (login CSRF).
    - `SameSite=Lax` + `Path=/api/auth/`;
    - `Origin` must equal `FRONTEND_ORIGIN`;
    - a required custom header `X-Requested-With: rumor-zero`, which a cross-site form cannot send.
    - Django's own CSRF check can't be used: through the relay `Host` is the backend and `Origin` the frontend. Details: ARCHITECTURE §7.
19. **Rate limiter (§4.5):** `django-ratelimit` is effectively unmaintained (last release 2023).
    → allauth's built-in `ACCOUNT_RATE_LIMITS` for auth endpoints. DRF scoped throttles, backed by the Redis cache, for posting, comments, likes, follows, reports and appeals.
    
    Client IP handling: the frontend proxy sends the real client IP in `X-RZ-Client-IP`, plus a shared secret. A small middleware trusts that header only when the secret matches and normalises `REMOTE_ADDR`, so allauth (`ALLAUTH_TRUSTED_PROXY_COUNT=0`) and DRF (`NUM_PROXIES=0`) both see the right IP. Without this, every user shares the proxy's IP and one abuser would rate-limit everyone.
20. **Keep-alive every 10 min via GitHub Actions (§15.3)** costs about 4,320 jobs/month. Each job is billed as at least 1 minute, and a private repo gets 2,000 free minutes, so it doesn't fit. GitHub also delays scheduled runs at peak times, and in public repos they auto-disable after 60 days without activity.
    - There's a hidden cost too: if the ping touched the database, Neon would never scale to zero and would burn its monthly compute allowance.
    
    - GitHub's terms also restrict Actions to work related to building, testing, deploying or publishing the project.
    
    → D3 default:
    - UptimeRobot (free: 50 monitors, 5-min interval, commercial use allowed) calls `GET /api/health/`, which **executes zero DB queries** (enforced by a test).
    - cron-job.org (free, custom headers) calls the secret-protected `POST /api/internal/tick/` **hourly**. That is about 24 Neon wake-ups/day, roughly 15 CU-h/month of the 100.
    - One GitHub Actions workflow runs **daily**, calling `/api/health/deep/` (DB + Redis) so Upstash (archived after 30 days idle) and Neon stay active. About 30 min/month.
21. **"A worker process run on a schedule" (§5.4):** Render's free tier has **no background workers and no cron jobs**. Those are paid-only; one web service is all you get.
    → Two ways to process a pending fact post:
    - (1) **inline kick:** after the post commits, a short background thread in the web process runs the pipeline for that post;
    - (2) **sweeper:** the secret-protected `POST /api/internal/tick/` processes any leftover `pending` rows with `SELECT … FOR UPDATE SKIP LOCKED` and retries with backoff; it is also available as `manage.py process_pending` for local dev and tests.
    
    Same §7.1 contract. No Celery.
22. **Resend (§4.3, §14)** only sends to your own address until you verify a domain you own. A free `*.onrender.com` or `*.workers.dev` subdomain can't be verified, because you don't control its DNS. **This is the one place the guide quietly assumes a paid domain.**
    SMTP is not a way around this: Render free web services block outbound ports 25/465/587 (since 2025-09-26), so Gmail SMTP won't work either.
    
    → D2 default: local dev uses Django's console email backend. Production uses **Brevo** (free, 300 emails/day, no card, HTTPS API) through `django-anymail`, with a single verified sender address. Swapping providers later is one env var.
    
    Alternatives, in order of preference:
    - (a) buy a domain → Resend (best deliverability);
    - (b) a free `is-a.dev` subdomain (allows MX/TXT records) → Resend. Its terms limit it to non-commercial, dev-related projects and it can be revoked;
    - (c) the Gmail API over HTTPS: excellent deliverability, 500/day, but needs a small custom email backend and a one-time OAuth setup.
23. **Cloudflare deployment (§14):** "Next.js needs the `@cloudflare/next-on-pages` adapter" is out of date. That adapter is deprecated and its repo was archived on 2025-09-29.
    - Cloudflare Pages is now for static sites only.
    - Full Next.js runs on **Cloudflare Workers**, via either OpenNext (`@opennextjs/cloudflare`) or Cloudflare's new vinext.
    - → D10: OpenNext. Free-plan limits that matter: 100,000 Worker requests/day, **10 ms CPU per request**, 50 subrequests per request. The old 3 MiB bundle limit was removed on 2026-09-04 (now 64 MiB).
    - OpenNext does not guarantee Windows support, so production builds run on Linux: Workers Builds, plus a CI check. Locally you use `next dev`.
24. **Frontend and backend on different free hosts + `SameSite=Lax` refresh cookie (§4.6, §14):** they are cross-site, so the cookie would never be sent. → Section d.

**Minor: resolved in the docs, no decision needed**

25. §5.1 step 5 says "Verified, Unverified/False": "unverified" is not "false". → Badge labels in b-2 (D4).
26. §9.2 caches the feed for 20–60 s, while §5.1 wants pending badges to update live. → Status polling uses the uncached `posts/status` endpoint. The feed cache TTL is 30 s.
27. §3.2 `confidence_score numeric(5,2)` vs the pipeline's "numeric 0–100". → The contract validates the range 0–100 and quantizes to 2 decimals.
28. §4.1 "username checked for uniqueness as the user types": allauth has no such endpoint. → Add `GET /api/v1/auth/username-available/` (throttled).
29. §4.4 Google sign-up collects no username, but usernames are required. → Auto-generate one (b-2), **from Google's first name, not the email local part** (user decision 2026-10-07, Part 3: a public handle must not reveal the inbox).
30. §12 lists DOMPurify: we never render user HTML (plain text only, React escapes it). → Not needed. Add it only if Markdown is ever supported.
31. §3.5 GIN index on `to_tsvector('english', content)`: Django's `SearchVector` wraps the column in `COALESCE`, so a query won't use that exact index. → A stored generated `search_vector` column (Django `GeneratedField`) with a GIN index on it.
32. §15.1 "If it passes, Render redeploys": Render deploys on every push unless told otherwise. → Set Render Auto-Deploy to **"After CI Checks Pass"**. Cloudflare Workers Builds deploys on push (acceptable; CI still runs on the PR).
33. §17 names Jest; the current Next.js docs list Jest and Vitest equally. → **Vitest** + React Testing Library (faster, ESM-native), plus Playwright for E2E as the guide says.
34. Numbers the guide cites that changed:
    - Neon now defaults to **Postgres 18** (still 0.5 GB and 100 CU-h/month, no card).
    - Render's default Python is 3.14. It has 500 build minutes and 5 GB outbound bandwidth per month, and wake-up takes about 1 min.
    - Upstash is 500K commands/month.
    - Sentry Developer is 5K errors/month, 1 user.
    - → Current values in SETUP.md and ENV_GUIDE.md.
35. **§1.1 wants server-rendered pages** for SEO and link previews, but on free Workers each request gets **10 ms of CPU**. Real OpenNext apps measure 17–21 ms per SSR render and get error 1102.
    → Rendering strategy:
    - Static pages (landing shell, how-it-works, privacy, terms) are **prerendered** at build time.
    - Post detail and profile pages do a **light SSR**: `generateMetadata` for OG tags + the claim text only; the rest hydrates on the client.
    - All personalised pages are client-rendered through `/api`.
    - Part 18 checks Workers observability for CPU-limit (1102) errors on `/p/[id]` (0C has no deploy).
36. **Next.js 16 renamed `middleware.ts` to `proxy.ts`.** Our "proxy" is **not** that file: it is a normal Route Handler we call the **API relay** (`src/app/api/[...path]/route.ts`). `proxy.ts`/middleware stays unused (only experimental on OpenNext).

37. **Part 6 decisions (user, 2026-10-09)** on points the guide and Stitch leave open:
    - **Home tabs:** Recent is the first and default tab; Following is the second, for signed-in users only (b1 lists Following first, but a new account with zero follows would land on an empty feed). Its empty state sends you to Recent.
    - **Following cache (guide §9.2):** only the ordered ids of the first page are cached for `FEED_CACHE_SECONDS`; the posts are read fresh on every request. Caching the whole serialized page would show a deleted or removed post's text for up to 30 s and, from Part 7, stale likes.
    - **Profile counters:** `verified` and `FALSE` include the author's deleted posts (a removed post is in neither); `posts` counts what the public can see. Deleting a post must not erase a FALSE label (same principle as ARCHITECTURE §4a: deleting undoes no events).
    - **Author links:** the avatar and name on post cards and the post page link to `/u/<username>` (otherwise profiles are reachable only by URL, the rail, and the follower lists until search in Part 12).
    - `task.md`'s "no self-follow check" was read as "no self-follow *is allowed*": a DB check constraint plus a 400, as ARCHITECTURE §2 and the acceptance criteria say.

38. **Part 7 decisions (user, 2026-10-10)** on points the guide, Stitch and `task.md` leave open:
    - **Hidden comments are Django Admin only:** the API and the page never return a hidden comment to anyone, staff included, and it doesn't count in `comment_count`. (`task.md`: "Hidden comments disappear for everyone but staff".)
    - **Deleting your own comment is a soft delete** (a new `comments.deleted_at` column, like posts in D6): the row stays for the audit trail and the admin, and the comment leaves every list and count. ARCHITECTURE §2 had no such column.
    - **CommentAdmin has Hide and Unhide** (`task.md` said only Hide): a wrongly hidden comment needs an undo. Unhide doesn't undelete what its author deleted.
    - Likes and comments are allowed on every post the public can see (pending and under review included, ANALYSIS c1); a removed or deleted post is a 404 for both, its author too. A like can still be taken back from a removed post.
    - **Icons:** the liked state is a filled `favorite` glyph in `secondary`, the comment count uses `chat_bubble`. DESIGN.md's "one glyph per concept" list names neither, and `design/` is read-only (the user supplies design changes); `lint-tokens` checks only icon *sizes*, so they are used and recorded here.
    - Stitch's comment row loses Reply, the `#C-xxx` id, the role chip and the per-comment `thumb_up`; the composer loses the attach buttons and gains a 500-character counter and Ctrl+Enter ("Dispatches", "Remark" and "Counter-Evidence" become "Comments" and "Comment", as in the naming table).

39. **Part 7B decisions (user, 2026-10-10)** on points the guide, Stitch and `task.md` leave open:
    - **`BookmarkAdmin` is superuser-only** (registered read-only, but `has_view_permission` is `is_superuser`, so no moderator permission, now or after Part 10, opens it). AGENTS.md says every model is registered in the admin; bookmarks are private (f-4), so the registration is the exception that stays out of reach. A superuser can already read the database, so it adds no reach.
    - **A repost of a deleted or removed original can always be taken back** (`DELETE …/repost/` is 204 whenever the post row exists): a profile's "This post is no longer available" card would otherwise be stuck there for good. The card gets an **Undo repost** button on your own reposts.
    - **A post shows once per list on the page.** The API promises "once per page" (`task.md`, ARCHITECTURE §9); the page also hides an older activity of a post that comes back on a later page (the original after its repost, a second reposter), which keeps the like, repost and bookmark buttons of one post from drifting apart.
    - **The Facts and Opinions chips filter a repost by its original's type**, a stub included (the original's type is still on the row).
    - **The cursor key** `(activity_at, kind, post id, reposter id)` replaces `task.md`'s "(activity_at, item id)": post ids are uuids and repost ids bigints, so no single id column exists, and the key is unique without the repost's own id. The token carries the time as an integer of microseconds, not ISO text.
    - **Repost checks run in this order:** not found, an existing repost (200, so a post that turned FALSE doesn't refuse someone who already reposted it), your own post, FALSE. `status_at_repost` is the status when the repost committed (the post row is locked with `FOR NO KEY UPDATE`).
    - **Icons and screens Stitch doesn't have:** the repost counter is `cached` (b1/b3, "Citations" renamed "Reposts", f-4) and the label reads "Repost" so the visible word is part of the button's name; the saved state is a filled `bookmark` in `secondary` (Stitch only draws `bookmark_border`, and DESIGN.md's glyph list names neither); there is no Stitch screen for the "Reposted by" line, the "no longer available" card or `/bookmarks`, so they borrow the card's label type, the removed-post tombstone's look and the profile page's container with c4's page heading.

40. **Part 8 decisions (user, 2026-10-10)** on points the guide, Stitch and `task.md` leave open:
    - **The report action is a flag button**, not an overflow menu. `task.md` said "in the PostCard overflow menu", but Stitch b1 draws a `flag` button in the card's right-hand group beside the bookmark and b3 a "REPORT" button in the detail row, so the page follows Stitch and no menu component is built. DESIGN.md's glyph list has `more_horiz` ("all overflow menus") but no `flag`; the flag joins `fingerprint` (the privacy line) as a glyph the list doesn't name, as Part 7 did for `favorite` and `chat_bubble`.
    - **What makes a young account's report count:** at least one post that isn't removed or one comment that isn't hidden. Posts and comments the reporter **deleted** still count (the principle used for posts and the fact quota: deleting undoes nothing); content a moderator took down earns no trust. Part 7 left this open for soft-deleted comments.
    - **FALSE posts follow the docs**: at the threshold a FALSE post goes to UNDER REVIEW with `pre_review_status = verified_false`, and Dismiss restores FALSE (§4). **A post under review after being FALSE can't be reposted** (409 `cannot_repost_false`), so a group of reporters can't reopen a FALSE label to reposts. One condition in `social.services.repost`; the page can't pre-disable it because `pre_review_status` is never public.
    - **No reason is preselected** in the report modal (d1 preselects the first): a default would bias what people report. The jargon in d1's header, callout and footer is replaced with plain copy (b-5, D8).
    - **Built the way the docs said, recorded here because it is easy to get wrong:** the report count is a windowed count over rows inside the insert's transaction under the post's `FOR NO KEY UPDATE` lock (c-2), with no upper bound on the window; `apps/pipeline` exists from this part (made with `startapp`, only `routing.py`), so Part 9 adds to it.

41. **Part 9 decisions (user, 2026-10-11)** on points the guide and the earlier docs leave open:
    - **A decisive FALSE that arrives while a post is already under review for reports goes to a moderator** (`flagged_reason` becomes `both`, `pre_review_status` stays `pending`); a late decisive TRUE still becomes `pre_review_status=verified_true`, which a dismissal restores. ARCHITECTURE §4 used to store the late FALSE as the label to restore; that let Part 8's repost refusal reveal a label that was never public (Part 8 plan, appendix A2), and let a moderator who dismissed the reports make the post FALSE without seeing it. The emergency rule of c-3 / §4 row "late result on an active emergency" was already this; it is now the rule for every post.
    - **The stub in production is a launch decision for Part 17**, not changed now: with the stub any author can write `#true` to get VERIFIED 95%, and about 15 % of untagged facts get a hash-chosen FALSE that would feed the public credibility score (f-5). Part 9 builds the stub as §6 specifies.
    - **Built from the plan's defaults, recorded because the guide's version gets them wrong** (c-21, guide §5.4): the processor never holds the post's row lock while the pipeline thinks (claim with a 5-minute lease, call, apply, with the claim's attempt count as a token, so a stale answer is dropped); reported pending facts are still checked (`under_review` + `reports` + `pre_review_status=pending`), because a check that ends any way changes one of the three; a post that already has a verdict ignores any result; `verdict_source` is public only with a `verified_*` status; the tick takes its first post always and another only if the worst case fits its 25 s budget; the inline kick's callback never raises after the commit. No new dependency (the HTTP client uses the standard library, like Turnstile) and no new variable.


42. **Part 10 decisions (user, 2026-10-11)** on points the guide, `task.md` and the earlier docs leave open:
    - **Moderators see moderation history only per post**: an inline on the post's page. The full `moderation_actions` list and Django's admin log are seniors-only (guide §8.2), and so are the History pages of accounts, settings, comments and posts, which would otherwise show the admin log to anyone who can view the object.
    - **Seniors may change `role`, suspend (`is_active`) and delete accounts, and nothing else**; never a superuser, never themselves. Email, password, profile fields and `is_superuser` stay superuser-only; the password page and the bulk delete are superuser-only (Django's own checks look only at change permission, or at no object at all). Deleting shows a summary, never the cascaded rows' text (bookmarks are private), and an account that **wrote admin log entries can't be deleted, only suspended** (`LogEntry.user` cascades, and an unchecked delete would erase a former senior's record).
    - **The removal reason for the author is `moderation_actions.public_note`** (the verdict actions copy their public note there too, so every public note is audited). Remove never touches `Post.verdict_note`, so Part 11's Restore needs no undo. This adds a column to the §2 table.
    - **Nobody acts on their own post, except a superuser**, and every action refuses a post its author deleted. Guide §8 says nothing about either.
    - **"Age in queue" is a column:** `posts.review_started_at`, set by `routing.enter_review` (a merge keeps it) and cleared when a moderator ends the review, with a database check that it is set exactly while the post is under review. The queue shows and sorts by it. It changes `routing.enter_review`'s signature (it takes `now`).
    - **"Mark email verified"** (deferred from Part 2) is built now, seniors only, as `accounts.services.verify_email_by_staff` (the name `mark_email_verified` was taken by Part 2's signal), logged in Django's admin log.
    - **Defaults approved with the plan:** the actions act on what is eligible and skip the rest (one transaction per post, at most 100 posts an action); **Escalate only works on a post under review** (§4 said "any"; an escalation outside review would stay on the post until a later review); leaving review clears `flagged_reason`, `pre_review_status`, `review_started_at` and `escalated_at`; account, settings and comment changes go to Django's `LogEntry` with old → new values (the ten `moderation_actions` kinds stay as §2 lists them); the queue's emergency column says Active / Ended / —; no E2E test (the admin is server-rendered).
    - **Built the way the docs said, recorded because it is easy to get wrong:** the confirmation page carries the evaluated ids and never `select_across` (Django would re-run the whole filtered queryset at the confirmation and could pick up a post that entered the queue meanwhile); the buttons on a post's page sit outside its `<form>` and post to `?queue=all`; `PostAdmin.has_change_permission` stays False for everyone, because moderators hold `posts.change_post` (it gates the actions) and a Save would otherwise write the whole row outside the services; a Dismiss or Remove with no valid `pre_review_status` is refused (`no_prior_status`) instead of failing a database check halfway through a batch; the groups' permissions come from a data migration with its own frozen lists, not from an import that later parts edit; a service stamps `created_at` after it holds the row lock, so the log's order is the order things happened.

43. **Part 11 decisions (user, 2026-10-13)** on points the guide, `task.md` and the earlier docs leave open:
    - **Restoring a fact the pipeline already checked sends it to the review queue.** When `pre_removal_status` is `pending` and the pipeline has had its say (`pipeline_checked_at` set, or `pipeline_attempts` at `MAX_ATTEMPTS`), Restore puts the post under review for the pipeline (`pre_review_status=pending`, the clock starts now) and a moderator gives the label; a fact it never finished goes back to `pending` and is checked as usual, and every other `pre_removal_status` is restored as it was. A finished check is never run again.
    - **"Keep removed" writes its own audit kind, `kept_removed`.** Part 10 meant its ten kinds to be final; this one was missing. Migration `moderation.0003` widens the database check (and can't be reversed once such a row exists).
    - **The removal reason reaches the author in a new key of the post object, `removal_reason`** (24 keys): the `public_note` of the post's latest `removed` row, for the author of a removed post only. `verdict_note` keeps meaning only the label's note.
    - **Your own profile lists your removed posts** (the author's tombstone with your text, the reason and the appeal state or button). Visitors, feeds, bookmarks and the profile counters are unchanged.
    - **Remove during an open label appeal is allowed and closes the appeal as `upheld`**, linked to the `removed` row; the different-moderator rule applies to it.
    - **Restore post and Keep removed take internal notes only.** The author is told the outcome in plain words (b-2) and sees the original removal reason.
    - **Defaults approved with the plan:** superusers are exempt from the different-moderator rule (as from the own-post rule) and Escalate is exempt from it; a deleted post can't be appealed (404, its author included) and its open appeal simply stays open; `pre_removal_status` and `escalated_at` are cleared by Restore; an appeal is linked on the resolving action's audit row only (not on Escalate); a FALSE post that reports sent to review is not appealable until that review ends; the 201 answer is the post object; 409 `already_appealed` wins over `not_appealable`; the `appeal` throttle (5 a day) applies to POST only; moderators can read appeals (`moderation.view_appeal`), seniors get nothing extra.
    - **Built the way the docs said, recorded because it is easy to get wrong:** `original_moderator` of a label appeal is the moderator of the latest `marked_false` row **only when a moderator gave the label** (a pipeline FALSE has none), never `post.moderated_by` (a later Dismiss of reports would make the dismisser the labeller); the removal appeal leaves `review_started_at` null (Part 10's check says set exactly while under review) and the queue shows it by the appeal's `created_at`; lock order is always post, then appeal.
44. **Part 11B decisions (user, 2026-10-13)** on points the guide, f-5, `task.md` and the earlier docs leave open:
    - **A removal adds to the label; it doesn't replace it.** The label's event (`fact_true` / `fact_false` / `emergency_false`) stays and `post_removed` (N + 2) is added, so a removed FALSE post costs N + 1 and N + 2. **Restore reverses only the removal's events** (the author's, the reposters' and the credits that removal earned).
    - **The public `recent` list shows own-post events only** (`fact_true`, `fact_false`, `emergency_false`, `post_removed`, each with `reversed`): repost rows, report credits and reversal rows never appear there.
    - **Moderators and up read the whole ledger** in Django Admin (`reputation.view_reputationevent`, migration `moderation.0005`).
    - **The badge is neutral:** grey text, "Credibility 72" or "Credibility: New", and in rows c3's neutral chip plus "· 84 verified"; no teal and no `verified` seal, which DESIGN.md keeps for a verified fact.
    - **A report earns credit only when the decision changed the post:** Remove always; Mark FALSE only when the post wasn't already FALSE before the review (reports on a pipeline-FALSE post, or filed during a label appeal, earn nothing).
    - **A reversed FALSE also reverses the reporters' credit** (it mirrors the restore rule).
    - **No backfill:** the ledger starts empty; a post labelled before Part 11B gets its missing events at its next moderator action, dated that day.
    - **No self-credit:** the deciding moderator's own report earns nothing from their decision.
    - **Defaults approved with the plan:** one reconciling writer (`settle_post`, two slots, LABEL and REMOVAL) instead of the task's four functions (every caller is one line, a re-label or a restore can't forget a reversal, re-running is a no-op by construction); reviews freeze the score and a late TRUE counts only once public; the repost timing rule is literal (`under_review` counts); every open report a credited action resolves is credited, up to 4 un-reversed credits per rolling 30 days, read after the users' lock; strictly increasing `created_at` per person and exact half-up rounding; the public endpoint never authenticates and its counts are status-based; the events row has 11 keys with an `appeal` block on your own negative rows; user rows gain `counts.verified`; the "How this is calculated" link is in the profile header only; Escalate never settles; the deciding moderator's own repost events still apply to them.
    - **Built the way the docs said, recorded because it is easy to get wrong:** the users are locked with `FOR NO KEY UPDATE`, not `FOR UPDATE` (a moderator's deferred foreign keys take `KEY SHARE` at commit, and two moderators deciding each other's posts deadlocked in a test with the plain lock); a full `User.save()` no longer writes the two score columns (allauth's `set_password` and the admin form save whole rows); Python's `round` is banker's rounding, so the score is computed in integer quarters.
45. **Part 11C decisions (user, 2026-10-19)** on points the guide, f-1, `task.md` and the earlier docs leave open:
    - **Block / Unblock emergency posting is for moderators and up** (`moderation.block_emergency_posting`, migration `moderation.0007`; seniors through the Moderators group). Nobody but a superuser blocks a superuser or themselves.
    - **How a block ends:** the automatic block from a FALSE emergency lifts by itself when that FALSE label is overturned, unless another block still stands (a manual one, or another FALSE emergency); a manual block lasts `emergency_false_cooldown_days` (as long as the automatic one); a logged Unblock lifts every block early. The column is always the latest end among the blocks still standing (`rules.standing_block_end`).
    - **The pinned section's × folds it to one line** ("2 emergency posts pinned" and Show), remembered per feed for the tab (sessionStorage) until a post that wasn't pinned before appears. Nothing becomes unreachable.
    - **The post object gains `emergency_demoted`** (25 keys): the post page says "Priority ended." or "Priority removed by a moderator."
    - **Defaults approved with the plan:** any FALSE label on an emergency blocks its author (a moderator's, or the pipeline's after expiry or demotion; the trigger is the ledger's new `emergency_false` row, so nothing blocks twice); Mark FALSE on an active emergency writes three audit rows 1 µs apart (`marked_false`, `emergency_demoted`, `emergency_blocked`); Demote is for moderators and up (`posts.change_post`), not on your own post, internal notes only; one refusal code for an ineligible emergency (403 `emergency_not_allowed` + `reason`), a full or paused fact quota included, a paused setting being its reason with a null time; the daily limit counts deleted and removed emergencies; no shared cache for Recent's pinned list; `block_days` in the quota's emergency block; Remove doesn't demote (a Restore inside the 24 hours pins the post again); the status poll is unchanged (a polled FALSE or removal ends the violet look by rule).
    - **Built differently from the docs, recorded:** the composer's button reads "Post emergency, will be checked" (with a comma, as the shipped "Post fact, will be checked"; `task.md` had a dash); the account's block history on UserAdmin is a read-only field, not an inline (an inline formset would make the account form's POST carry its management form); `create_post` locks the author with `FOR NO KEY UPDATE` (was `FOR UPDATE`, Part 11B's rule for user locks); the composer treats an allowance without the `emergency` block as "not allowed" (a frontend deployed before its backend doesn't crash).
46. **Part 12 decisions (user, 2026-10-20)** on points the guide, `task.md` and the earlier docs leave open:
    - **People search** matches the username **prefix** plus any **word of the display name** (the start, or after a space, hyphen or apostrophe); no extension and no new index (`users` is scanned for the name half; the username half uses the `varchar_pattern_ops` index). A trigram index is a Part 16 option. Order: exact username, prefix, name matches, A–Z inside each; never by credibility.
    - **Filter chips** are one row of six, pick one: All / Facts / Opinions / Verified / FALSE / Under review. The API still takes `post_type` and `status` together.
    - **Rate limit:** `search` is 60/min per client IP, counted by IP for signed-in users too (`IPScopedRateThrottle`).
    - **Pagination deviation (documented):** rank order has no timestamp, so search pages by a bounded offset (20 a page, 5 pages, `next_cursor` = the next page number) instead of a cursor (§9).
    - **Defaults approved with the plan:** submit-only search (no live search); `q` 1–200 characters; a negation-only or stop-word-only query is an empty 200; suspended authors' posts stay searchable (as in Recent), suspended people don't; tabs show no counts; a search page is `noindex, follow` with a fixed title; highlighting is client-side and approximate; pending facts are searchable and show "Checking facts…" with the usual polling.

47. **Part 13 decisions (user, 2026-10-20)** on points the guide, `task.md` and the earlier docs leave open:
    - **An action that closes an appeal sends two items:** `appeal_resolved` **plus** the verdict or removal that came with it (Mark verified, Mark FALSE, Remove on a label appeal). Restore and Keep removed send `appeal_resolved` only. Refinement found in review: a `verdict` item is sent only when the label **changes** (`pre_review_status` differs from the new status), so Mark FALSE on a post that was already FALSE (a report review, an upheld label appeal) repeats nothing.
    - **Mark FALSE on a pinned emergency sends the verdict and `emergency_demoted`;** Demote sends `emergency_demoted` only.
    - **Silent:** Dismiss reports, Escalate, filing an appeal, the automatic emergency block and its lift, bookmarks. Nine types, no tenth.
    - **The open `/notifications` page reloads itself:** when the 30 s poll sees the unread count rise, the first page is fetched again and the new items are put on top (nothing resets; loaded pages and scroll stay).
    - **Author only:** reposters are not told what happens to the original (follow-up). **Follow back:** the new-follower item has Stitch's button (`FollowButton` with its idle word "Follow back"; the API sends `actor.following` on follow items). **No retention job:** nothing is pruned (Part 16/17 follow-up).
    - **Defaults approved with the plan:** a new `outcome` column (`true` / `false` / `upheld` / `overturned`, §2) so an old item can't change meaning; moderation items carry **no actor** (the author is never told which moderator acted, a reporter is never revealed); dedupe is permanent and database-enforced for follow, like and repost with the **type in the key**; items vanish with their post or comment (`delete_post`, `delete_comment`, the admin's Hide); one action's items are stamped 1 µs apart; throttle scope `notifications` 120/min per user shared by the three endpoints; the unread count is exact (`99+` is only the badge's text); a suspended actor shows as "Someone"; the excerpt (140 code points) is made on the server; `notify()` raises outside a transaction and writes with `ON CONFLICT DO NOTHING`, so callers' `atomic(durable=True)` blocks stay valid.
    - **As built, two findings:** a link's accessible name must be one `aria-label` ("Notifications, 3 unread"): a separate `sr-only` span reads "Notifications , 3 unread" in Chrome (jsdom joins them without the space, so only the browser run caught it); and the page reload on an arrival prepends **every** item of the fresh first page (an already-shown item is replaced by its fresher copy), which made the "only unseen items" filter dead code.

48. **Part 14 decisions (user, 2026-10-20; planned 2026-10-21)** on points the guide, `task.md` and the earlier docs leave open:
    - **Staff can't delete themselves:** `DELETE /me` answers 403 `staff_account` for moderators, seniors and superusers, and for any account that wrote Django Admin log entries (`LogEntry.user` cascades, the admin's delete page already protects those). The UI says to ask an admin to remove the role first.
    - **The export includes the notifications you received** (type, outcome, post and comment ids, the actor's public username or null, read flag, time).
    - **Username changes are limited by a throttle only** (`profile_update` 30/h): no cooldown and no migration. The old `/u/<name>` becomes a 404 and the name is free for others.
    - **Two new emails:** "password changed" (after `POST /me/password/`) and "Continue with Google is now connected" (when a Google sign-in links to an existing account).
    - **Defaults approved with the plan:** `GET /me` gains `bio` and `public_score`; `PATCH /me` needs a verified email (password change, export and delete need only a login); four per-user throttle scopes (`profile_update` 30/h, `password_change`, `data_export`, `account_delete` 10/h); a password change keeps this device signed in and ends the others at their next refresh; a deletion deletes this device's session and expires the cookies; the admin's account delete runs the same routine (`accounts.deletion.delete_account`); after a deletion the browser goes to `/home` with a toast.
    - **c2 subset:** Profile, Account & Security (email, password, the Google link), the CredibilityPanel in place of the "Credibility Index" bar, and Privacy & Data (export, danger zone). Dropped as having no backend: the institutional-avatar card (14B), affiliation, ORCID and DOI provenance, the "Update address", "Disconnect" and "Manage sessions" buttons, notification settings and the three transparency checkboxes.

49. **Part 14B decisions (user, 2026-10-21; one more during the build)** on profile photos (f-7 as built):
    - **Pillow 13.0.0, not 12.3.x.** 12.3.0 never got a patch release; 13.0.0 (2026-10-16, cp313 wheels for Linux and Windows) fixes a critical JPEG decoder overflow, an unbounded Exif loop and decompression-bomb bypasses (SETUP B1 updated under AGENTS rule 10).
    - **Block photo uploads also removes the current photo** (logged `avatar_removed` and then `avatar_blocked`, 1 µs apart), and a new **Allow photo uploads** action (kind `avatar_unblocked`, migration `moderation.0008`) lifts the block, mirroring Block / Unblock emergency posting. Allow does not bring the photo back. Remove photo, Block and Allow need the new permission `moderation.moderate_profile_photos` (moderators and up, migration `0009`).
    - **The browser accepts originals up to 20 MB** and shrinks them first (centre square, at most 1024 px, JPEG 0.9 on white, so GPS never leaves the device). The server's 5 MB / 25 MP / 128 px limits still guard direct API uploads.
    - **A real upload percentage:** `apiFetch` gained `onUploadProgress`, which swaps only the transport to XMLHttpRequest (wrapped in a `Response`), so the token, the single 401 refresh-and-retry, `signal` and the error shape stay one code path.
    - **WebP is capped at 12 MP (decided during the build, after the spike).** Pillow 13's only WebP decoder is the animation decoder (two RGBA canvases, the frame bytes and the image: about 16 bytes a pixel), so a 25 MP WebP peaked at about 390 MB over the baseline on a 512 MB Render instance, against about 114 MB for a 25 MP PNG. JPEG and PNG keep 25 MP. The web uploader always sends a JPEG of at most 1024 px, so only direct API uploads can meet the cap. (ARCHITECTURE §3, §4e.)
    - **Defaults approved with the plan:** `/me` and the profile give the 256 px URL, every list the 96 px one; `/me` gains `avatar_uploads_blocked` (12 keys); refusals are `{detail, code}` (`photo_missing`, `photo_too_large`, `photo_unsupported`, `photo_too_small`, `photo_too_many_pixels`, `photo_busy`, `photo_uploads_blocked`, `email_unverified`) and the permission ones never count against `avatar_upload` (5/day); the original lives only in an in-memory upload handler capped at 5 MB; **one decode at a time site-wide** through a Postgres advisory lock (10 s wait, then 503 `photo_busy`); `avatar_version` and `avatar_uploads_blocked` join the fields a full `User.save()` never writes; a suspended account's photo is still served (Part 16 decides); nobody is notified of a removal or a block; `<Avatar>` images are lazy; the export carries the 256 px photo as base64.
    - **As built, one deviation from the plan's recipe:** the centre square is flattened and shrunk **in horizontal bands**, not with a whole-image `reduce()`: `reduce()` converts a whole RGBA image to premultiplied form first, which cost 194 MB on a 25 MP RGBA PNG and 314 MB on a 300 × 83,000 panorama (bands: 112 MB and 103 MB, no limit changed).

---

## d) Deployment topology (no owned domain)

### The problem

The frontend is served from `rumor-zero.<account>.workers.dev` and the API from `rumor-zero-api.onrender.com`.

- `workers.dev`, `pages.dev` and `onrender.com` are all on the **Public Suffix List** (checked in the list file on 2026-09-29), so each subdomain counts as its own "site".
- A refresh cookie set by the API with `SameSite=Lax` is **not sent** on `fetch()` calls from the frontend, which are cross-site.
- `SameSite=None; Secure` would be sent in some browsers, but Safari (and Firefox's partitioning) blocks or partitions third-party cookies. It would also force CORS-with-credentials and weaken CSRF protection.
- Only a domain you own could make them same-site, and that costs money.

### Options considered

| Option | Cost | Verdict |
|---|---|---|
| Buy a domain; `app.` + `api.` subdomains | ~$10/yr | Cleanest, but **not free** |
| Refresh token in `localStorage` | free | Rejected: the guide explicitly forbids it (XSS) |
| `SameSite=None` third-party cookie + CORS credentials | free | Rejected: broken in Safari/Firefox, weaker CSRF posture |
| **Proxy `/api/*` through the Next.js frontend ("API relay")** | free | **Chosen** |

### Chosen: single origin via an API relay

```
Browser ──► https://rumor-zero.<acct>.workers.dev   (Next.js on Cloudflare Workers, OpenNext)
              ├─ pages, static assets (free, don't invoke the Worker)
              └─ /api/*  ──(API relay Route Handler, server-side fetch)──► https://rumor-zero-api.onrender.com/api/*
                                                                              (Django + DRF + allauth, Render free)
Moderators ──► https://rumor-zero-api.onrender.com/<ADMIN_URL_PATH>   (Django Admin, direct, session login)
```

- **API relay:** a catch-all Route Handler, `frontend/src/app/api/[...path]/route.ts`. It is not Next 16's `proxy.ts`; see c-36.
  - It forwards the method, body and an **allow-list** of headers (`Authorization`, `Cookie`, `Content-Type`, `Accept`, `Origin`, `X-Requested-With`, plus `If-None-Match`, `If-Modified-Since` and `User-Agent`) to `BACKEND_ORIGIN`.
  - It uses `redirect: 'manual'`. Request bodies are **buffered** (≤ 6 MB), not streamed: Django can't read chunked bodies, and OpenNext buffers them on Workers anyway (changed in 0C; was `duplex: 'half'` streaming).
  - A redirect to the backend's own `/api/` comes back as a relative `Location`; any other `Location` is dropped. `next.config.ts` turns off Next's trailing-slash redirect for `/api/` (it would loop with Django's `APPEND_SLASH`). Full rules: ARCHITECTURE §1.
  - It copies back the status, body and **every** `Set-Cookie` via `headers.getSetCookie()`.
  - It adds `X-RZ-Proxy-Secret: <PROXY_SHARED_SECRET>` and `X-RZ-Client-IP` (from `cf-connecting-ip`, or `x-forwarded-for` locally).
  - It sets a ~70 s timeout for Render cold starts (~1 min) and returns a friendly `503 {"code":"backend_waking"}` on timeout.
  
  Why not `rewrites()`: they do work on OpenNext, but they drop `cf-connecting-ip` and give no header control. Worse, when a Worker calls another Cloudflare-fronted host (Render is behind Cloudflare), `CF-Connecting-IP` arrives as the **Worker's** IP. Without our own client-IP header, every user would look like one IP to the rate limiter. Waiting on `fetch()` doesn't count toward the 10 ms CPU limit, so the relay is cheap.
- **Cookie:**
  - The API sets `rz_refresh` with **no `Domain` attribute** and `HttpOnly; Secure; SameSite=Lax; Path=/api/auth/; Max-Age=1209600` (14 days, in seconds), plus a readable hint `rz_session=1` (`Path=/`, set and cleared with it; Part 1).
  - allauth puts the refresh token (and the raw session key) in its JSON bodies; the cookie middleware strips both and moves the refresh token into the cookie (ARCHITECTURE §7).
  - The browser received it from the frontend origin, so it is stored as a **first-party cookie of the frontend host** and sent only to `/api/auth/*` on that host.
  - Locally, `AUTH_COOKIE_SECURE=False` (plain http://localhost).
- **Access token:** kept in memory only (guide §4.6) and sent as `Authorization: Bearer …`. After a page reload the app calls `POST /api/auth/app/v1/tokens/refresh` once, but only when the `rz_session` hint cookie is present, so anonymous visitors cost no request (Part 1).
- **CSRF:** described in c-18. No CORS configuration is needed at all: the browser only ever talks to one origin. `django-cors-headers` is dropped.
- **SSR (see c-35 for the CPU limit):**
  - Static pages are prerendered.
  - Post detail `/p/[id]` and profile `/u/[username]` do a light server render (metadata + claim text), calling `BACKEND_ORIGIN` directly, server-to-server and **unauthenticated**, so link previews and SEO work (guide §1.1).
  - Personalised views (home feed, notifications, settings) render on the client after the token refresh.
- **Absolute URLs:**
  - The API never builds links from its own host. Email links use `FRONTEND_ORIGIN`.
  - Pagination returns an opaque `next_cursor` string instead of a URL. DRF's default `next` URL would point at `onrender.com` and bypass the proxy.
- **Cost of the choice:**
  - Every API call also counts as a Worker request (free plan: 100,000/day; static assets don't count).
  - The biggest consumer is polling. A tab polling notifications every 30 s makes ~2,880 calls/day if left open all day.
  - Mitigations:
    - poll only while the tab is visible (`document.visibilityState`);
    - back off when idle;
    - pending-status polling stops after 10 min.
  - Budget: roughly 50–100 daily active users before the cap matters. That is the guide's "early users" stage.
  - It also adds one network hop (~tens of ms). The backend URL is still public, which is fine since everything there is authenticated or rate-limited too.
- **Escape hatch when the cap gets close (no code rewrite):**
  - Bearer-authenticated calls don't need cookies, so the browser can call Render **directly** with CORS (`Authorization` header, no credentials).
  - Only `refresh` and `logout` must keep using the relay.
  - The API client takes a base URL per call type, so this is an env change (`NEXT_PUBLIC_API_DIRECT_ORIGIN`) plus `django-cors-headers`. Not used in the MVP.
- **If you later buy a domain:** point `app.` at Workers and `api.` at Render (custom domains are free on both). Keep the relay or drop it; no auth code changes either way.

### Effect on env vars

| Where | Variable | Why |
|---|---|---|
| frontend (server-only) | `BACKEND_ORIGIN` | proxy + SSR target |
| frontend (server-only, secret) | `PROXY_SHARED_SECRET` | proves requests came through our proxy |
| frontend (public) | `NEXT_PUBLIC_SITE_URL` | canonical URLs, OG tags |
| frontend (public) | — (no API URL) | the browser always calls relative `/api/...` |
| backend | `FRONTEND_ORIGIN` | email links + Origin check on refresh/logout |
| backend (secret) | `PROXY_SHARED_SECRET` | same value as the frontend |
| backend | `AUTH_COOKIE_SECURE` | `False` only on local http |
| backend | `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | the Render host (the admin is served there directly) |
| Google console | Authorized JavaScript origins | the **frontend** origin(s) only. The ID-token flow needs no redirect URI. |

---

## e) Product names and branding in `design/stitch/`

Searched every `.html` and `.md` file (text, `<title>`, logos, `alt`/`data-alt`, `<meta>`, comments, footers, email addresses).

- **"Veritas" (any case): 0 occurrences.**
- **"Stitch" / "Google Stitch": 0.**
- **`<meta>` tags:** only `charset` and `viewport`. No product names.
- **Logos in Stitch:** there is no image logo. The wordmark is **styled text**, "Rumor Zero" in Newsreader bold (`font-headline-sm`), and **"RUMOR ZERO" in capitals in a1** (lines 23, 371).
  - Emblem tiles differ per file: `check` (a3), `layers` (a4), `diamond` (a5), `lock` (a6).
  - The screenshots show two more marks (an "RZ" monogram tile in `design/stitch/screen.png`, a checkmark tile in b3's `screen.png`) that exist in no code.
  - **D9, changed by you on 2026-09-29: all of these are replaced by the real logo** (e.1, e.2). Colours, sizes and assets: ARCHITECTURE §14.

### e.1 The logo files (inspected 2026-09-29, read-only)

| File | What it is | Used? |
|---|---|---|
| `design/logo.svg` | **Master** (current version recoloured by you, inspected 2026-09-30). `viewBox="0 0 1000 1000"`, no width/height, transparent background, 2.2 KB. The wordmark "Rum0r": R, u, m, r in neutral grey `#898a8d`; the "0" and a full-width underline in cyan `#23b5d8`. All text is outlined paths: no fonts, scripts, links or bitmaps. The artwork spans x 121.4–878.6, y 413.0–625.7 (≈ 3.6 : 1); the rest of the square is empty. The "0" is the only `<path>` in the cyan class (currently `path.cls-1`). | Yes, by Part 0D |
| `design/logo.png` | Earlier raster version: 2048×2047 px, RGB with no transparency, white letters with a cyan `#19B6DA` "0" and underline on a navy `#182431` plate, plus a 1-px light-grey border at the edge. | No. Kept untouched. |

- The logo reads "Rum0r"; its accessible name everywhere is **"Rumor Zero"**.
- **Colour clash: resolved.**
  - The first SVG (2026-09-29, teal `#19aa96` + amber `#f4a361`) was practically Stitch's Verified and Under-review colours (ΔE 1.5 and 0.6), so it was flagged. You recoloured it.
  - The current grey is a neutral close to `outline` (ΔE 10).
  - The cyan is clearly distinct from every verdict colour (nearest: the blue action family at ΔE 22–23, Verified teal at ΔE 32).
  - Both colours still stay **inside the logo image only** and never become UI colours (ARCHITECTURE §14).
- **Contrast:**
  - grey letters 3.3–3.5 : 1 on the light surfaces (passes 3 : 1);
  - cyan "0" 2.3–2.4 : 1 on light surfaces (below 3 : 1, but logotypes are exempt, so this is recorded, not blocking);
  - on the dark `inverse-surface`, 3.8 : 1 and 5.4 : 1.
  - Every plate we generate (favicon, app icons, share image, email, admin) uses `inverse-surface` behind the logo.

### e.2 Brand marks to replace (applied in Parts 0C, 2, 10 and 0D)

| Where | Old mark | Replaced by |
|---|---|---|
| Sidebar of every app-shell file: root `code.html`:21, b1:16, b2:22, b3:16, b4:21, c1:17, c2:19, c3:20, c4:21, d1:20, d2:17 | text wordmark "Rumor Zero" | `<Logo size="md"/>`; tablet icon dock: `<Logo variant="mark"/>` (0C) |
| a1:23 (header), a1:371 (footer, with "Evidence-First Discourse Network") | text "RUMOR ZERO" | `<Logo/>` in MarketingNav / MarketingFooter; tagline removed (0C) |
| a3:23–29 | `check` emblem tile + wordmark + "Fact Social" | `<Logo size="lg"/>` in AuthLayout (0C) |
| a4:34–38 | `layers` emblem tile ("Rumor Zero Dark Emblem Badge") | AuthLayout logo |
| a5:22–24 | `diamond` emblem tile (`data-purpose="app-logo"`) | AuthLayout logo |
| a6:22–27 | `lock` light emblem tile + "Cryptographic Access Control" | AuthLayout logo; subtext removed |
| a2 | none | AuthLayout logo (every auth page shares it) |
| `design/stitch/screen.png`, `b3_…/screen.png` | "RZ" monogram and check tiles (screenshots only) | nothing to convert |
| DESIGN.md:243 | sidebar wordmark spec | overridden by ARCHITECTURE §14 (DESIGN.md stays read-only) |
| Not in Stitch | favicon, app icons, share image, email header, Django admin header | generated assets (0D), used in 0D, Part 2 and Part 10 |

Not brand marks, so kept: the b1 "You're caught up" `verified` tile, the header initials avatar, and the Google "G".

### Alternate or additional product names, taglines and version strings

| File:line | Text | Type | Suggested action |
|---|---|---|---|
| a1:386 | "© 2025 Rumor Zero Network Inc. Epistemic rigor and verified citations guaranteed." | fabricated legal entity + claim | → "© 2026 Rumor Zero" (no "Inc." unless one exists; drop "guaranteed") |
| a1:6 (`<title>`), a1:49 | "The Epistemic Social Protocol" | tagline | decide / replace |
| a1:373 | "Evidence-First Discourse Network" | tagline | remove (the footer shows the logo + "© 2026 Rumor Zero") |
| a1:387 | "Strict Hairline Calibration Edition" | design-edition label | remove |
| a3:28 | "Fact Social" | tagline next to the logo | remove (the logo stands alone, f-8) |
| a3:120, a5:100 | "Rumor Zero Cryptographic Ledger" | sub-brand | remove |
| a3:120, a5:98 | "Protocol standard 4.1" | version string | remove |
| b1:76 "PROTOCOL 4.2", b3:366 "Rumor Zero Protocol v4.2", root:75 "SPECIFICATION REV. 4.2", root:608 "PROTOCOL V4.2 PDF" | version strings (they conflict with 4.1) | remove |
| root:6, root:83, DESIGN.md:212/243 | "The Epistemic Charter" | page name | → "How verification works" |
| c1:473, d2:72 | "Rumor Zero charter (Section 1.10)" | document name | remove |
| DESIGN.md:2 (+ folder `epistemic_ledger/`) | "Epistemic Ledger" | design-system name | keep internally (not user-facing) |
| every shell file (root:61, b1:56, b2:62, b3:56 & 221, b4:61, c1:57, c2:59, c3:60, c4:61, d1:60, d2:57) | "Verification Ledger" | feature name | remove (b-3) |
| every shell file (root:37, b1:32, …, d2:33) | "Audit Queue" | nav label | → "Moderation" |
| a6:6 (`<title>`), a6:27 | "Reset Password - Cryptographic Access Control" | **no product name at all** | → "Reset password · Rumor Zero" |
| a4:6, a5:6 | "A4: Verify Email - Rumor Zero", "A5: Forgot Password — Rumor Zero" | screen codes in titles | → "Verify your email · Rumor Zero" etc. |
| d1:92 | "Evidentiary Integrity Protocol • D-1 Editorial Governance" | screen code + sub-brand | remove |
| b1, b3, c1, d2 | *(no `<title>`)* | missing | add "<Page> · Rumor Zero" |
| HTML comments in shell files, e.g. b1:12 | "RZ app sidebar/header" | internal abbreviation | harmless |
| b1:525 "#RZ-9984-CASCADIA", b3/c4/d2 "#RZ-2024-8841", a6:111 "#RZ-SEC-9941", d1:197 "#REP-84920", d2:427 "#MOD-TX-2024-L9", b2:75 "#ARC-88219" | "RZ-" record IDs | fake IDs | remove (we use UUIDs, not shown) |

### Domains and email addresses (they imply domains we don't own)

| File:line | Text | Action |
|---|---|---|
| a3:72, a4:46, c2:276, c2:295 | `elena.vance@rumorzero.org` | ⚠ implies we own `rumorzero.org`. Use `name@example.com` in placeholders. |
| a5:65 | `edward.vane@observer-dispatch.org` | replace with `name@example.com` |
| b2:199 | `https://climate-review.org/vol24/co2-capture` | remove (sample value; the source field itself is built, with an `https://example.org/…` placeholder) |
| c1:261–263 | `doi.org/10.1038/…`, `irena.org/cap23`, `ember-climate.org` | remove (sample content) |

### Third-party names

- **Legitimate UI:** "Continue with Google" + Google "G" (a2:32/38, a3:52), "Turnstile" (a2:99), "Google SSO" (c2:287/294).
- **Sample content, remove:** "Google Scholar" (c2:381), "ORCID" (c1:409, c2:151/380), with ORCID's published *example* iD 0000-0002-1825-0097; "macOS / Chrome" (c2:325).

### Organisations in sample content (all removed with the sample data)

- **Real:** IEA, IRENA, NOAA, Copernicus, USGS, PNSN, Canadian National Seismograph Network, Federal Reserve, EPA, Eurostat, Ember, Icelandic Met Office, European Commission, Mauna Loa Observatory, **Climeworks** (d2:217), and **"Oxford Institute for Energy Studies"** (b1:167, a real institute used as a fake affiliation).
- **Fabricated:** "CleanTech Ledger" (b4:257), "Oxford Energy Institute" (c1:108/408, c2:140/201/210), "Pacific Rim Geoscience Network", "Cascadia Rapid Observation Cluster", "Global Supply Indices", "Urban Ethics Quarterly", "Climatology Ring" (c1:205), "Senior Reviewer Board" (c4:231), "Storm Aelia" (root:389).

### Sample people (fictional; never ship as seed data)

- Archivist Ross @ross_verify (the logged-in user in every shell)
- Dr. Elena Vance @evance_md (also written as the page owner in c1/c2/c4)
- Dr. Elena Rostova
- Marcus Thorne @mthorne_geo
- Sarah Lin @slin_econ
- Julian Adams @jadams_phil
- Dr. Aris Carter @dr_carter (initials "AK" in c3, "AC" in d2)
- @auditor_kyle

---

## f) Decisions for the Stitch features (D4, D5, D9 changed by you; defaults approved 2026-09-29)

The full rules are in ARCHITECTURE (sections named below). This section records what was decided, why, and what was rejected.

### f-1 Emergency posts (ARCHITECTURE §4b; Part 11C)

- **A flag on fact posts only**, not a third post type. Opinions never enter the pipeline, so an emergency opinion would be pinned with no check at all.
- **Pinned for 24 h** at the top of feeds:
  - Recent pins every active emergency on the site.
  - Following pins those from people you follow, plus your own.
  - At most 3 are shown, with "Show all". Reposts never pin, and pinned posts aren't repeated in the list below.
- **Expiry is computed when a post is read** (`emergency_expires_at` is stored at creation). Nothing depends on a scheduler, so it works on free hosts that sleep.
- **Still fact-checked, and first.** A FALSE result while the post is active is not applied automatically:
  - the post goes to human review, where it also comes first;
  - it keeps its priority until it expires or a moderator marks it FALSE.
- **Safeguards** (a false emergency is high-harm):
  - the account is at least 7 days old and has a credibility score of at least 40;
  - 1 emergency per 24 h, which also counts toward the daily fact quota;
  - a report threshold of 2 instead of 5;
  - a 30-day emergency ban after one of your emergencies ends FALSE, plus the −3 score event;
  - moderator actions Demote emergency, Remove, and Block emergency posting;
  - a required confirmation in the composer.
- **Colour:** Stitch's violet `tertiary` stripe and an EMERGENCY chip while active. Afterwards the post takes its status colour.
- **Notifications:** the author is told when priority is removed. Out of scope: alerts to followers, email or push, and email alerts to moderators (Brevo allows 300 emails/day).
- **Not adopted from Stitch:** "bypasses verification", "trust tokens", the "permanent emergency marker" and "request expedited audit". After expiry, only the detail page shows a small neutral note.
- **As built in Part 11C (c-45):** eligibility is checked under the author's lock in the order email, age, score, block, daily limit, fact quota, and refused with one code and the rule's reason; the composer shows the reason on the disabled toggle and needs the confirmation ticked; the pinned section folds with × for the tab; a FALSE emergency blocks its author whoever labelled it, and the block lifts when that FALSE is overturned; moderators also have Demote emergency, Block and Unblock emergency posting and an emergency filter, with active emergencies first in the queue and in the pipeline.

### f-2 Appeals now also cover removals (Part 11)

- A removal now lowers a public score, so the author of a removed post can also ask for another look (guide §16). It is still one appeal per post.
- If the appeal is overturned, the post returns to its previous status, and the score events are reversed for the author and for every reposter.

### f-3 Sources / DOI (ARCHITECTURE §4c; Parts 4–5)

- Up to 5 optional sources on fact posts (changed from one by you on 2026-10-01), each an http(s)
  URL or a DOI, in the order entered. Duplicates after normalisation are refused.
- Stored in one `sources` array column on the post: they are immutable and always read with it,
  so the feed needs no extra query and "opinions have no sources" stays a plain DB check.
- They are validated and stored, but **never fetched** by the server (no SSRF risk).
- Cards show the first source and "+N more"; the detail page lists them all.
- The pipeline contract carries them for the future real pipeline.
- Follow-up, not in the MVP: a DOI title lookup against Crossref's fixed API host, sending only the DOI.

### f-4 Bookmarks and reposts (ARCHITECTURE §4d; Part 7B)

- **Bookmarks:** a private list. Nobody sees counts, not even the author of the post.
- **Reposts:**
  - Plain reposts only. They inherit the original's live label, with no new check.
  - You can't repost your own posts, FALSE-labelled posts or removed posts.
  - If the original is deleted or removed, the repost shows "This post is no longer available".
  - They appear in Following and on profiles, not in Recent.
  - They affect the reposter's score (f-5).

### f-5 Credibility score (ARCHITECTURE §4a; Part 11B)

- **Range and formula:** 0–100, starting at **50**. Score = `100 · (5 + P) / (10 + P + N)`, where P and N are the sums of positive and negative event weights. The 5/10 terms act as 10 imaginary starting events, so no single post causes a wild swing.
- **Shown publicly only after 3 counted events**; before that the profile says "New".

| Event | Effect |
|---|---|
| Your fact post verified TRUE | P + 1 |
| Your fact post labelled FALSE | N + 1 |
| Your emergency post ends FALSE | N + 3 (instead of N + 1) |
| Your emergency post verified TRUE | P + 1 (no bonus, so the flag can't be farmed) |
| Your post removed by a moderator | N + 2 |
| Reports on your post dismissed | no change |
| Opinions | count only when removed |
| Your report upheld (the post was removed or labelled FALSE by a moderator) | P + 0.25 for you, at most 4 per 30 days; a dismissed report costs nothing |
| A post you reposted while it was still unchecked (pending or under review) gets its outcome | TRUE P + 0.25 · FALSE N + 0.5 · emergency FALSE N + 1 · removed N + 0.5 |
| Reposting an already-verified post | nothing |

- **Stickiness:** deleting a post doesn't undo its events, and undoing a repost after the verdict doesn't either. A failed appeal costs nothing.
- **Storage:** an append-only ledger plus a denormalised score on the user. Every overturn appends reversal rows, so any change is reversible and auditable.
- **Legal caution (guide §16):** the score is public, so it has:
  - a full appeal path (f-2);
  - a visible history for the account owner, with an appeal link on each negative item;
  - a plain "How this is calculated" page;
  - Terms that need legal review.

  It is never shown on post cards, and people are never ranked by it.
- **Names:** "Credibility score" in the UI, `reputation` in code.
- **As built in Part 11B (c-44):** the score is rounded half up; a removal **adds** N + 2 to the label's event; a report is credited only when the moderator's decision changed the post (Remove, or a Mark FALSE of a post that wasn't FALSE already), never for the deciding moderator's own report, and a reversed FALSE takes the credits back; a review freezes the score; the public sees "Credibility 72" or "New" in neutral grey (no teal, no seal) in the profile header and user rows, with the account's recent own-post events at `GET /api/v1/users/{u}/reputation/`; the owner's full ledger is at `GET /api/v1/me/reputation/events/` (11D and 14 show it).

### f-6 Charts (Part 11D)

| Stitch | Becomes | Data |
|---|---|---|
| b3 "Consensus Gauge" | Confidence meter with the auto-label threshold marked | `confidence_score`, `confidence_threshold` (pipeline verdicts only) |
| b3's three tiles | Confidence · Threshold and margin · Time to verdict | the same, plus `seconds_to_verdict` |
| b3 "Exhibit A" bar chart | Reposts and likes per day, first 14 days, verdict day marked | grouped counts from `reposts`, `likes`, `comments` |
| c1 "Epistemic Standing" ring | Credibility ring + "20 verified · 3 FALSE" | reputation endpoint |
| b4 sparkline | 30-day credibility trend inside that widget | ledger `score_after` |
| c2 "Credibility Index" bar | Your score bar + full history | your ledger |
| c3 / b4 people rows | Score as a number + verified count (not a chart) | user payload |

- Dropped: the b1/b4 claim-data telemetry boxes and the b4 contributor spotlight.
- **No chart library.** Charts are token-built HTML/SVG as in Stitch, each with a text alternative for screen readers.
- Moderator verdicts never show a %.
- **As built in Part 11D:** the meter marks **today's** threshold (it is not stored per verdict; if it was raised since, the tile says "Below today's threshold of N%"); the spread chart is for fact posts only and draws reposts and likes (comments are in the payload and the hidden table); the stats of a removed post are a 404 for everyone; credibility visuals (ring, bar, sparkline) are **neutral grey**, the confidence meter keeps its verdict tone; the owner's panel shows the real score; Stitch's gauge was a bar without a threshold marker and its ring started at 9 o'clock by mistake (built from 12 o'clock); `StatTile` is plain text (no image role) while every picture-like chart has a summary and a sibling hidden table.

### f-7 Profile photos (ARCHITECTURE §4e; Part 14B)

Storage options checked on 2026-09-29, with no card allowed:

| Option | Verdict |
|---|---|
| Cloudflare R2 (the guide's suggestion) | ❌ needs an "R2 subscription" checkout with a payment method, even for the free tier |
| Cloudflare Images | ❌ storage is paid ($5 per 100,000 images); only transformations have a free allowance |
| Workers KV | ❌ free, but a Cloudflare-only binding (breaks D10's portability), and Django would need a Cloudflare API token to write to it |
| Supabase Storage | ⚠ free (1 GB, no card), but a new service, and free projects pause after 7 days without activity |
| Cloudinary | ⚠ free (25 credits/month, no card), but a new service |
| **Postgres (Neon), in a separate `avatars` table** | ✅ **chosen**: no new service and no card. About 20 KB per photo, so 5,000 photos ≈ 100 MB of the 0.5 GB. |

- **Upload rules:**
  - JPEG, PNG or WebP only, detected by decoding the file, not by its extension. No SVG, GIF, HEIC or animation.
  - At most 5 MB and 25 megapixels (WebP: 12), at least 128×128. The browser accepts originals up to 20 MB (c-49).
- **Processing:**
  - EXIF rotation is applied, then **all** metadata (EXIF/GPS/ICC/XMP) is dropped.
  - The image is centre-cropped to a square and re-encoded as WebP at 256 and 96 px. The original is never stored.
  - The browser shrinks the image before upload (centre square, at most 1024 px, JPEG), but the server redoes everything, one decode at a time site-wide.
- **Serving:** `/api/v1/avatars/<user>/<version>-<size>.webp` through the relay, cached for a year (the URL changes with every new photo), with `nosniff` and a sandbox CSP.
- **Who and how often:** email-verified users only, 5 changes per day.
- **Moderation:**
  - Moderators can remove a photo, block uploads (which also removes the photo) and allow them again (all logged with the account, c-49).
  - There is no user-facing "report photo" button in the MVP (follow-up).
  - The Google profile photo is not imported.
- **Fallback:** initials when there's no photo, while loading, on error, and after removal.
- **As built (Part 14B):** see c-49 and ARCHITECTURE §4e. Measured decode peaks above the process baseline: 25 MP RGBA PNG about 112 MB, 24 MP JPEG about 10 MB, 12 MP WebP about 189 MB.

### f-8 Logo (ARCHITECTURE §14; Part 0D)

- **Master files:** `design/logo.svg` is the master. `design/logo.png` is untouched and unused.
- **Header:** the logo alone, with the accessible name "Rumor Zero". No text beside it and no tagline, because the logo already is the wordmark. The same applies to auth cards, marketing nav and footer (the footer adds "© 2026 Rumor Zero").
- **Favicon and app icons:** the cyan "0" on the dark `inverse-surface` plate (5.4 : 1), because the full wordmark is unreadable below about 48 px. Everything else uses the full wordmark.
- **Share image, email logo, Google logo, admin logo:** the full logo on the same dark plate.
- **Google consent screen:** don't upload a logo for now. Google shows it only after brand verification, and verification checks domain ownership, which a free `workers.dev` address very likely can't pass. The optional steps are in ENV_GUIDE §2.9.
- **Colour clash:** the first SVG's teal/amber matched the verdict colours. It was resolved by your recolour on 2026-09-30 to grey + cyan (e.1, ARCHITECTURE §14).
- **Part 0E not needed:** the planned "swap in the SVG" part was dropped because the SVG arrived before Part 0D.

**Sources (f-7, f-8):**
- R2: <https://developers.cloudflare.com/r2/get-started/>, <https://community.cloudflare.com/t/why-using-r2-free-tier-involves-giving-card-info/945179>
- Cloudflare Images: <https://developers.cloudflare.com/images/pricing>
- Workers Cache API (off on `workers.dev`): <https://developers.cloudflare.com/workers/runtime-apis/cache/>
- Supabase: <https://supabase.com/docs/guides/platform/free-project-pausing>
- Cloudinary: <https://cloudinary.com/documentation/developer_onboarding_faq_free_plan>
- Google OAuth branding: <https://support.google.com/cloud/answer/15549049>, <https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification>
