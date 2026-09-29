---
name: Epistemic Ledger
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#3c4946'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#6c7a76'
  outline-variant: '#bbcac5'
  surface-tint: '#006b5f'
  primary: '#006b5f'
  on-primary: '#ffffff'
  primary-container: '#00a896'
  on-primary-container: '#00352e'
  inverse-primary: '#59dbc7'
  secondary: '#006398'
  on-secondary: '#ffffff'
  secondary-container: '#5bb8fe'
  on-secondary-container: '#00476e'
  tertiary: '#732ee4'
  on-tertiary: '#ffffff'
  tertiary-container: '#a87dff'
  on-tertiary-container: '#3c0088'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#79f7e3'
  primary-fixed-dim: '#59dbc7'
  on-primary-fixed: '#00201c'
  on-primary-fixed-variant: '#005047'
  secondary-fixed: '#cce5ff'
  secondary-fixed-dim: '#93ccff'
  on-secondary-fixed: '#001d31'
  on-secondary-fixed-variant: '#004b73'
  tertiary-fixed: '#eaddff'
  tertiary-fixed-dim: '#d2bbff'
  on-tertiary-fixed: '#25005a'
  on-tertiary-fixed-variant: '#5a00c6'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
  verdict-review: '#F4A261'
  on-verdict-review: '#9a4a12'
typography:
  display-hero:
    fontFamily: Newsreader
    fontSize: 3.5rem
    fontWeight: '600'
    lineHeight: 4rem
    letterSpacing: -0.03em
  display-hero-mobile:
    fontFamily: Newsreader
    fontSize: 2.25rem
    fontWeight: '600'
    lineHeight: 2.75rem
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Newsreader
    fontSize: 2.25rem
    fontWeight: '500'
    lineHeight: 2.75rem
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Newsreader
    fontSize: 1.75rem
    fontWeight: '500'
    lineHeight: 2.25rem
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Newsreader
    fontSize: 1.25rem
    fontWeight: '600'
    lineHeight: 1.75rem
    letterSpacing: -0.01em
  claim-headline:
    fontFamily: Newsreader
    fontSize: 1.375rem
    fontWeight: '500'
    lineHeight: 1.875rem
    letterSpacing: -0.01em
  claim-opinion:
    fontFamily: Newsreader
    fontSize: 1.375rem
    fontWeight: '400'
    lineHeight: 1.875rem
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 1.125rem
    fontWeight: '400'
    lineHeight: 1.75rem
  body-md:
    fontFamily: Inter
    fontSize: 0.9375rem
    fontWeight: '400'
    lineHeight: 1.5rem
  body-sm:
    fontFamily: Inter
    fontSize: 0.8125rem
    fontWeight: '400'
    lineHeight: 1.25rem
  label-code:
    fontFamily: JetBrains Mono
    fontSize: 0.75rem
    fontWeight: '600'
    lineHeight: 1rem
    letterSpacing: 0.06em
  label-metric:
    fontFamily: JetBrains Mono
    fontSize: 0.875rem
    fontWeight: '700'
    lineHeight: 1.25rem
  label-badge:
    fontFamily: Inter
    fontSize: 0.6875rem
    fontWeight: '600'
    lineHeight: 0.875rem
    letterSpacing: 0.03em
rounded:
  DEFAULT: 0.125rem
  lg: 0.25rem
  xl: 0.5rem
  full: 9999px
spacing:
  gutter: 1.25rem
  gutter-mobile: 0.75rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.875rem
  space-lg: 1.25rem
  space-xl: 2rem
maxWidth:
  reading: 760px
  wide: 1240px
  form: 480px
  modal: 620px
---

## Brand & Style

This design system establishes an austere, forensic, and unassailable visual architecture for verification-first social discourse. Drawing foundational cues from academic journals (*Nature*, *The Lancet*), institutional financial broadsheets (*The Financial Times*, *Reuters*), and cryptographic ledger explorers, the interface strips social engagement of gamified sensory triggers and replaces them with epistemic certainty.

The aesthetic philosophy centers on **"Color as Verdict, Never as Decoration."** In standard consumer interfaces, saturated hues signify brand identity, engagement micro-loops, or whimsical notifications. Here, chroma is quarantined entirely: the canvas, navigation, and authoring environments remain strict monochromatic slates, whites, and carbon neutrals. Vivid saturation is unlocked solely when the protocol asserts an empirical state—Verified Teal, Alert Red, Review Amber, or Emergency Violet.

The target audience comprises investigative journalists, macroeconomic analysts, scientific researchers, civic institutions, and truth-critical readers who demand non-reputable evidentiary provenance. The interface inspires cold credibility, disciplined scientific inquiry, and deliberate intellectual friction over algorithmic velocity.

## Implementation (single source of truth)

Every page loads the same `<head>`: Inter (400/500/600/700), JetBrains Mono (400/600/700), Newsreader (roman 400/500/600 and italic 400), Material Symbols Outlined, `https://cdn.tailwindcss.com?plugins=forms,container-queries`, and one byte-identical `<script id="tailwind-config">`. That config **is** this document's frontmatter: the `colors`, `typography` (as `fontFamily` + `fontSize`), `rounded` (as `borderRadius`), `spacing`, and `maxWidth` values above are the exact values coded. No page may define its own colors, fonts, radii, or widths, and no page may use Tailwind's default palette (`slate-*`, `blue-*`, `white`, …) or arbitrary color values (`bg-[#…]`).

Notes on the coded values:
- `rounded-full` is **not** overridden (an earlier `full: 0.75rem` override made avatars and pills render as rounded squares; it was removed, so `rounded-full` is a true `9999px` circle/pill).
- In this config `rounded-lg` = **4px** (not Tailwind's default 8px), `rounded` = 2px and `rounded-xl` = 8px. Only `rounded-lg` and `rounded-full` are used (see Shapes).
- Every `text-<token>` size utility also sets that token's `font-weight` (and line-height/letter-spacing). A weight class on a parent therefore does not reach a child that has its own `text-<token>`; put the weight class on the same element as the size token.

## Colors

The palette operates under an invariant doctrine of semantic isolation. Hex codes below are the coded token values.

### Verdict colors (the only saturated hues)

| Verdict | Token (text / icon) | Badge | Stripe / dot | Badge glyph |
|---|---|---|---|---|
| **Verified** — Fact Teal | `primary` `#006b5f` | `text-primary bg-primary/10 border-primary/30` | `bg-primary` | `check_circle` |
| **Debunked** — Alert Red | `error` `#ba1a1a` | `text-error bg-error/10 border-error/30` | `bg-error` | `cancel` |
| **Under Review** — Review Amber | hue `verdict-review` `#F4A261`; ink `on-verdict-review` `#9a4a12` | `text-on-verdict-review bg-verdict-review/10 border-verdict-review/30` | `bg-verdict-review` | `hourglass_top` |
| **Emergency / Unverified fast-track** — Emergency Violet | `tertiary` `#732ee4` | `text-tertiary bg-tertiary/10 border-tertiary/30` | `bg-tertiary` | `bolt` |
| **Opinion** — Silent Gray (zero chroma) | `outline` `#6c7a76` | `text-outline bg-surface-container-low border-outline-variant` | `bg-outline-variant` `#bbcac5` | none |

- **Fact Teal** renders as `primary` (`#006b5f`) everywhere — badges, stripes, checkmarks, the `verified` seal. `primary-container` (`#00a896`, the historical "Fact Teal" swatch) stays in the palette but is not used for verdicts, because as text it reaches only ~2.9:1 on white; `#006b5f` reaches ~6.2:1.
- **Review Amber** has two tokens because the hue `#F4A261` is only ~1.9:1 on white — illegible as text. The hue is used for stripes, dots, fills, tints and borders; any amber *text or icon* uses the ink `on-verdict-review` (`#9a4a12`, ~5.8:1 on the badge tint). All four verdict inks sit at roughly 6:1.
- Verdict tints for dossier drawers and panels use the same family at low opacity (`/5`–`/10` fill, `/20`–`/30` border).
- Non-verdict states reuse the verdict families by meaning: success/available/connected → `primary`; form errors, error banners, destructive actions → `error`; warnings/pending notices → `verdict-review`.

### Protocol Blue (actions)

- **Protocol Blue — `secondary` `#006398`** (hover `on-secondary-container` `#00476e`). It marks actions and protocol state, never verdicts: every primary action button, the active navigation item, links, focus rings, checked controls, selected-tab underlines, and informational callouts (`bg-secondary/10 border-secondary/30`).

### Neutrals (canvas, structure, type)

- Canvas `surface` `#faf8ff` (every page's `<body>`); cards, panels, modals `surface-container-lowest` `#ffffff`; inset panels, hover fills and filled inputs `surface-container-low` `#f2f3ff`; stronger neutral fills (chips, tracks, placeholders) `surface-container` `#eaedff` → `surface-container-highest` `#dae2fd`.
- Text `on-surface` `#131b2e` (primary), `on-surface-variant` `#3c4946` (secondary), `outline` `#6c7a76` (meta, placeholder, disabled).
- Hairlines `outline-variant` `#bbcac5` at 30% (default), 50–100% for inputs and secondary buttons; interactive-card hover border `outline` at 50%.
- Dark fills (emblem tiles, tooltips, the header avatar) `inverse-surface` `#283044` with `inverse-on-surface` `#eef0ff`. Modal scrim `inverse-surface` at 40%.

## Typography

The typographic hierarchy establishes distinct epistemic lanes across three specialized font families. Always pair a family utility with a size utility (`font-headline-md text-headline-md`); pairing a family token with a different size token is allowed when a role needs it (e.g. `font-label-code text-label-badge` for 11px mono labels).

1. **Editorial Assertion (Newsreader)**: Primary claim texts, broadsheet hero titles, and formal doctrine headers use a transitional serif. When an author posts a verifiable claim, it renders in upright Newsreader (`claim-headline`). When an author submits a subjective opinion, it renders in Newsreader Italic (`claim-opinion` + `italic`), instantly signaling non-empirical discourse to the eye before the user reads a single syllable. Headings: `display-hero` (marketing hero only), `headline-lg` (page H1), `headline-md` (auth-card titles, major sections), `headline-sm` (card, panel and modal titles; the "Rumor Zero" wordmark).
2. **System & Evidentiary Synthesis (Inter)**: Navigation, dossier summaries, citation footnotes, explanatory breakdowns, and body copy rely on Inter: `body-lg` (lead paragraphs), `body-md` (default copy, inputs, buttons, nav), `body-sm` (secondary copy, helper text, table cells), `label-badge` (tiny chips).
3. **Tabular Telemetry & Provenance (JetBrains Mono)**: Consensus percentage calculations, cryptographic multi-hashes, timestamp markers, audit log IDs, tab labels and system status taxonomies use `label-code` (uppercase system labels) and `label-metric` (emphasized numbers) so numerals stay stable during active peer-triage updates.

Generic Tailwind sizes (`text-sm`, `text-2xl`, `text-[13.5px]`, …) and generic families (`font-sans`, `font-serif`, `font-mono`) are not used.

## Layout & Spacing

- **App shell (desktop)**: a fixed 256px (`w-64`) left rail for navigation and Audit Queue access, a fixed 64px (`h-16`) top bar (claim search, Verification Ledger control, account avatar), and the page content in `<main>` offset by `pl-64 pt-16`.
- **Named content widths** (Tailwind `maxWidth` tokens), chosen by page type rather than per page:
  - `max-w-reading` — **760px**: single-column reading pages (home feed, post detail, notifications, following list, settings forms). This replaces the earlier 680px figure; the coded feed column had already standardized on 760px.
  - `max-w-wide` — **1240px**: pages whose main container holds a multi-column grid, rail, or dense table (moderator review queue, profile with its side rail, search with its filter rail, the logged-out marketing sections, the Epistemic Charter).
  - `max-w-form` — **480px**: authentication cards (sign up, log in, verify email, forgot and reset password).
  - `max-w-modal` — **620px**: modal dialogs (post composer, report post).
  - Inner typographic measure limits on a paragraph (`max-w-md`/`xl`/`2xl`) are allowed; page containers use only the named widths.
- **Content padding**: page containers use `px-space-lg py-space-xl` with `gap-space-lg` between sections.
- **Tablet / mobile** (intended behavior, not yet implemented in the Stitch export, which is desktop-only): the rail condenses to an icon dock under 1280px, and on mobile (<768px) the content spans the viewport minus `margin-mobile` (1rem) with navigation moving to a bottom sheet.

Spacing rhythm prioritizes scientific density over decorative whitespace. Component padding and gaps use the named scale only: `space-xs` 4px, `space-sm` 8px, `space-md` 14px, `space-lg` 20px, `space-xl` 32px (plus `gutter` 20px and `margin` 32px). Sub-token micro-spacing (`py-0.5` on badges) and large page-level offsets (≥ 36px) may use plain Tailwind values.

## Elevation & Depth

This design system rejects ambient blur, heavy drop shadows, and neon depth cues. It operates on **hairline flat-planing and strict tonal layering**:

- **Borders over Shadows**: Spatial differentiation is accomplished almost exclusively through 1px hairlines (`border-outline-variant/30`). `shadow-sm` is the only shadow in use (primary buttons, raised segmented-control segments, menus).
- **Surface Elevation Levels**:
  - *Base*: global canvas `surface` `#faf8ff`.
  - *Surface-Container*: `surface-container-lowest` `#ffffff` cards bounded by 1px `outline-variant/30`. Hovering on interactive claims shifts the border to `outline/50` instead of adding a drop shadow.
  - *Evidentiary Sidecars & Inset Panels*: `surface-container-low` `#f2f3ff`, or a low-opacity verdict tint (`primary/5–10` for verified audits, `error/5–10` for empirical rebuttals, `tertiary-fixed/20` for emergency telemetry), bounded by an inset hairline.
  - *Overlays & Modals*: flat `surface-container-lowest` dialogs (`max-w-modal`, hairline border, `rounded-lg`) over an `inverse-surface/40` scrim, stacked above the app shell (`z-[60]`).

## Shapes

The interface embraces an architectural, near-orthogonal geometry (`roundedness: 1`). Exactly two radii are used:

- **`rounded-lg` (4px)** for every card and container, inset/dossier drawer, modal and auth card, action button, badge, status chip, category tag, filter chip, input/select/textarea, checkbox, menu, tooltip, and icon tile. This soft corner preserves tabular discipline while preventing visual harshness across hundreds of stacked claim items. Pill shapes are intentionally rejected for status chips to eliminate any association with gamified consumer tags or toy social media apps.
- **`rounded-full`** only for elements meant to be fully round: avatars, status dots, toggle-switch tracks and knobs, progress/strength bars, segmented-control tracks and segments, circular icon-only buttons, and the header's Verification Ledger pill.
- **4px Verdict Stripe**: an absolutely positioned `w-1` band flush against the left edge of every verification card (`relative overflow-hidden rounded-lg`), in the verdict's stripe token.

## Components

### App shell (identical on every logged-in page)
- **Sidebar**: the "Rumor Zero" wordmark (`font-headline-sm text-headline-sm font-bold tracking-tight`), primary nav Home (`home`), Search (`search`), Notifications (`notifications`), Profile (`person`), then a full-width primary **Submit Claim** button (`edit_note`). In the footer: Audit Queue (`fact_check`) and Settings (`settings`), followed by the account card (avatar, name, handle) with a `more_horiz` "User menu" button. Every link carries `data-path`. The current page's item is marked `aria-current="page"` and rendered `bg-secondary text-on-secondary font-semibold`; reference pages that are not nav destinations (the Epistemic Charter) mark nothing active.
- **Top bar**: claim search input (`rounded-lg`, filled `surface-container-low`), the **Verification Ledger** control (an interactive pill button with neutral chrome and the `verified` glyph in `primary`), and the account avatar button (initials on `inverse-surface`).
- Logged-out pages (logged-out home, sign up, log in, verify email, forgot/reset password) have no app shell.

### Verification Cards
- **Structural Spine**: `surface-container-lowest` card bounded by 1px `outline-variant/30`, with the 4px verdict stripe running down the full left edge.
- **Left Stripe Encodings**: `bg-primary` (Verified), `bg-error` (Debunked), `bg-verdict-review` (Under Review), `bg-tertiary` (Unverified / Emergency fast-track), `bg-outline-variant` (Opinion).
- **Header Structure**: Author identity, academic affiliation, or verified role badge on the left; category chip (`FACT` vs `OPINION`) and status badge on the right.
- **Statement Presentation**: Verifiable empirical statements render in `claim-headline` enclosed in precise typographic quotation marks. Opinion pieces render in `claim-opinion` italic without scientific confidence telemetry.
- **Evidentiary Dossier Drawer**: Directly beneath the claim text, a light tinted panel lists primary source citations, consensus telemetry feeds, or rebuttals with external ledger links.

### Status Chips & Badges
- **Triple-Channel Accessibility Protocol**: No status is communicated via color alone. Every badge pairs:
  1. A semantic glyph (`check_circle`, `cancel`, `hourglass_top`, `bolt`; opinions carry none).
  2. An unambiguous uppercase label (`VERIFIED`, `DEBUNKED`, `UNDER REVIEW`, `EMERGENCY`, `OPINION`).
  3. A tabular monospace confidence numeral where one exists (e.g., `94%`, `98%`).
- **Surface Styling**: `inline-flex items-center gap-space-xs px-space-sm py-0.5 rounded-lg font-label-code text-label-code font-bold uppercase border`, plus the verdict's badge classes (1px border at 30%, 10% fill; see Colors).
- **Category chips** (`FACT`, `OPINION`, topic tags): neutral `text-outline bg-surface-container-low border-outline-variant/30`, same shape.

### Buttons & Inputs
- **Primary Action Button** (every filled CTA sitewide, e.g. `Submit Claim`, `BROADCAST CLAIM`, `Log in`, `Create account`): `bg-secondary text-on-secondary hover:bg-on-secondary-container`, `rounded-lg`, `px-space-md py-space-sm`, `font-body-md text-body-md font-semibold`, `shadow-sm`. Labels keep their authored casing.
- **Secondary Actions**: `surface-container-lowest` fill, 1px `outline-variant` border, `surface-container-low` on hover; same shape and type as primary.
- **Destructive Actions** (irreversible account and key operations only): the primary shape in `bg-error text-on-error`.
- **Inputs**: filled `surface-container-low`, 1px `outline-variant/50` border, `rounded-lg`, `px-space-md py-space-sm`, `body-md`; focus switches to a `secondary` border with a `secondary/20` ring on a white fill. Checkboxes and radios are checked in `secondary`.
- **Assertion Composer**: Minimalist text area marked with clear claim-mode switches (`[ Empirical Claim ]` vs `[ Civic Opinion ]`), accompanied by an inline pre-flight checklist for source verification links and dataset attachments.

### Iconography
- Functional icons use **Material Symbols Outlined** only (`<span class="material-symbols-outlined">glyph</span>`), sized `text-[0.75rem]`–`text-[2rem]` (0.75, 0.875, 1, 1.125, 1.25, 1.5, 2rem) and colored with a text token.
- One glyph per concept across the app: `home`, `search`, `notifications`, `person`, `settings`, `fact_check`, `edit_note`, `verified` (the single verified seal; `verified_user` is retired), `link`, `database`, `tune`, `send`, `cached`, `compare_arrows`, `more_horiz` (all overflow menus), `check_circle`, `cancel`, `hourglass_top`, `bolt`.
- Inline SVG is reserved for genuine third-party brand marks (the multicolor Google "G"), each tagged `data-rz-keep`.

### Data Tables & Registries
- Hairline horizontal division lines (`outline-variant/30`). Zero vertical divider clutter.
- Header cells in `label-code` uppercase `outline`; body cells in `body-sm`.
- Fixed JetBrains Mono formatting for hash digests, block heights, and triage time counters.
- Left-aligned academic nomenclature and right-aligned statistical percentages.
