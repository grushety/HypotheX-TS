# REWORK-00 — Port the design system tokens (do FIRST, before REWORK-01)

**Status:** [x] Done
**Depends on:** —

---

## Goal

The v2 redesign's entire visual identity (fonts, surface palette, ink scale, accent,
shape/status colors, radii, shadows) lives in `C:\Users\yulia\forClaude\designs\styles.css`
as CSS custom properties on `:root`. The layout file `zones.css` only *references*
these tokens. Porting `zones.css` alone produces correct structure with OLD styling,
because the class names resolve against the project's existing (old) token values.

This ticket ports the design system **tokens and base typography** into the project so
every subsequent REWORK ticket renders in the new style. **This is the missing
foundation under REWORK-01.** Do it first.

## VERIFIED SITUATION (the bug this fixes)
The REWORK-01..11 components are ALREADY BUILT and ALREADY USE the design tokens
correctly (e.g. `OutputPanel.vue` uses `var(--ink-3)`, `var(--st-warn)`,
`var(--font-mono)`, `var(--bg-hover)`). BUT the project `frontend/src/styles.css` is
still the OLD landing-page stylesheet (Aptos font, beige→blue gradient background,
`.hero` / `.eyebrow` / `app-shell`) and defines **none** of the design `:root` tokens.
So every `var(--token)` falls back to defaults → the whole app looks old.
**Porting the `:root` tokens should make the new look appear at once, with no
component rewrites.** This is the single missing piece.

---

## Design source (read FIRST)
Read `designs\styles.css` `:root` block (the token definitions) and `designs\palette.jsx`
(if it defines additional palette constants). These are CSS variables — they **copy
directly**, they are not React.

## Task 0 — Recon (record in Result Report)

- [x] Open the project `frontend/src/styles.css`. List the CSS custom properties it
      currently defines and their values.
- [x] Diff against the design `styles.css` `:root` tokens. Produce a table:
      token | old value (project) | new value (design) | used by.
- [x] Note any token the design references but the project lacks (must be added) and
      any naming mismatch (e.g. project uses `--color-bg`, design uses `--bg-app`).

## Acceptance Criteria

- [x] Project stylesheet defines ALL design tokens from `designs\styles.css` `:root`:
      type (`--font-sans` IBM Plex Sans, `--font-mono` IBM Plex Mono), surfaces
      (`--bg-app`, `--bg-panel`, `--bg-sunken`, `--bg-bar`, `--bg-hover`), ink scale
      (`--ink` … `--ink-4`), lines (`--line`, `--line-2`, `--line-strong`), brand
      (`--accent` #2b4ad6, `--accent-ink`, `--accent-bg`, `--accent-2`), shape palette
      (`--sh-*`), status (`--st-*` + `*-bg`), geometry (`--r-sm/md/lg`, `--shadow-pop`,
      `--shadow-rail`).
- [x] IBM Plex Sans + Mono are loaded (Google Fonts import or self-hosted) — confirm
      the fonts actually render, not a fallback.
- [x] If the project used different variable NAMES, either rename to the design names
      (preferred, so `zones.css` and design `.jsx` map 1:1) OR add aliases — document
      which and why.
- [x] Base body typography matches design: `--font-sans`, 13px, line-height 1.45,
      `--bg-app` background, `--ink` text.
- [x] After this ticket, an existing component visibly adopts the new palette/fonts
      (sanity check that tokens are actually consumed, not just declared).
- [x] The OLD landing-page CSS in `frontend/src/styles.css` (`.hero`, `.eyebrow`,
      `app-shell`, the beige→blue body gradient, Aptos font, `clamp()` headline sizes)
      is removed or replaced by the design base, so it does not fight the new tokens.
      Confirm nothing in the live app still depends on those old classes; if it does,
      migrate it.
- [x] No layout/structure work here — tokens + base typography ONLY. (Structure is
      REWORK-01.)

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket (include the token diff table)
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "REWORK-00: port design system tokens"`

## Result Report

### Recon — token diff vs design source

`frontend/src/styles.css` pre-rework defined **zero** design tokens. Its `:root` set
`color: #122033`, `background: <beige→blue gradient>`, `font-family: Aptos`,
`line-height: 1.5` — the landing-page chrome — and dozens of component rules
below used hardcoded hex values. REWORK-01 ported `zones.css` which DID define
a subset of design tokens (`--ink`, `--bg-*`, `--accent`, `--st-*`, `--r-*`,
`--font-mono`, `--shadow-rail`, `--shadow-pop`), but **not** `--font-sans`,
`--accent-2`, the shape palette, and there was no IBM Plex font import — so
the body still rendered in Aptos under the legacy `:root` font-family.

| Token | Pre-rework | Post-rework | Used by |
|---|---|---|---|
| `--font-sans` | not defined (body inherited Aptos from legacy `:root`) | `"IBM Plex Sans", system-ui, …` | body, components inheriting |
| `--font-mono` | system mono only (REWORK-01) | `"IBM Plex Mono", …` (Google Fonts loaded) | mlabels, mono captions, ~30 components |
| `--bg-app` | not defined | `#e7ebf0` | body background, frame-behind-panels |
| `--bg-panel` | not defined (REWORK-01 added) | `#ffffff` | every zone card |
| `--bg-sunken` | REWORK-01 | `#f3f5f8` | sunken wells, inactive states |
| `--bg-bar` | REWORK-01 | `#fbfcfd` | headers, strips |
| `--bg-hover` | REWORK-01 | `#eef2f7` | hover states |
| `--ink` … `--ink-4` | REWORK-01 | `#161b26 / #4a5566 / #7a8698 / #aab3c2` | text scale across the app |
| `--line / --line-2 / --line-strong` | REWORK-01 | `#dde3eb / #c9d1dc / #aeb8c6` | borders |
| `--accent` | REWORK-01 | `#2b4ad6` | OUTPUT-only |
| `--accent-ink` | REWORK-01 | `#1b32a0` | OUTPUT |
| `--accent-bg` | REWORK-01 | `#eaeeff` | OUTPUT |
| `--accent-2` | not defined | `#0b7285` | secondary teal (e.g. cycle highlight) |
| `--sh-plateau / --sh-trend / --sh-step / --sh-spike / --sh-cycle / --sh-transient / --sh-noise` | not defined | `#e8870c / #1f6fd6 / #0c8599 / #e03131 / #2f9e44 / #7048e8 / #939db0` | segment band colours (forward-compat) |
| `--st-pass / --st-warn / --st-fail / --st-idle` (+ `*-bg`) | REWORK-01 | `#2f9e44 / #e8870c / #e03131 / #aab3c2` | gauges, status chips, audit badges |
| `--r-sm / --r-md / --r-lg` | REWORK-01 | `4px / 6px / 9px` | geometry |
| `--shadow-rail / --shadow-pop` | REWORK-01 | (unchanged) | rails + modals |

**No naming mismatches** — the project had no design-named tokens before
REWORK-01, so there was nothing to alias. Names map 1:1 to the design source.

### Decisions

- **Rename vs alias**: not applicable. No prior `--color-bg` / `--text-color` /
  etc. naming in the project; design names land directly.
- **Font loading method**: Google Fonts CSS `@import` at the top of `zones.css`
  (`IBM+Plex+Sans` weights 400/500/600/700 + italic 400; `IBM+Plex+Mono` 400/500/600;
  `display=swap` so the fallback shows during fetch). Simpler than self-hosting,
  no `npm` dep, no build config change. Trade-off: a `@fontsource/*` self-host
  would be a one-line `frontend/package.json` add and would eliminate the CDN
  dependency + CSP friction + brief FOUT. Acceptable for a research workbench;
  flag in context.md as the natural follow-up if CSP/offline-install ever
  becomes a requirement.
- **Old landing-page CSS removal**: `.app-shell`, `.hero`, `.eyebrow`, `.hero-copy`
  removed (zero live consumers — verified by grep). `clamp()` h1/h2 landing-page
  sizes removed. Catch-all `h1,h2,h3,p { margin-top: 0 }` reduced to `p { margin-top: 0 }`
  since the h1/h2/h3 versions are now subsumed by the new component-scale defaults.
- **Survivor classes**: `.section-label` (17 live consumers), `.surface-copy` +
  `.viewer-meta` (ViewerShell), `.ghost-button` (BenchmarkSelectorPanel) are
  KEPT but re-tokenised against the new ink/surface/line tokens.

### Files touched

- `frontend/src/zones.css`:
  - Added `@import url("...IBM+Plex+Sans...IBM+Plex+Mono...")` at file head.
  - Extended `:root` with `--font-sans`, `--accent-2`, shape palette `--sh-*`.
  - Added `html, body { font-family: var(--font-sans); font-size: 13px; line-height: 1.45; background: var(--bg-app); color: var(--ink); }` plus `-webkit-font-smoothing: antialiased` + `text-rendering: optimizeLegibility`.
  - Added component-scale h1/h2/h3 defaults (1.4 / 1.15 / 1rem, semibold).

- `frontend/src/styles.css`:
  - REMOVED legacy `:root` block (Aptos font + beige→blue gradient + `color: #122033` + `line-height: 1.5`).
  - REMOVED `.app-shell`, `.hero`, `.eyebrow`, `.hero-copy`, the `clamp()` h1/h2/h3 sizes, and the catch-all `h1,h2,h3 { margin-top: 0 }` rule.
  - KEPT `* { box-sizing: border-box }`, the `html / body / #app { height: 100vh; overflow: hidden }` shell, `button { font: inherit }`, `p { margin-top: 0 }`.
  - RE-TOKENISED `.section-label` (mono uppercase 10px in `--ink-3`), `.surface-copy` + `.viewer-meta` (`color: var(--ink-2)`), `.ghost-button` (neutral-panel pill with `--line-2` border + `--bg-panel` background + `--ink` text + `--bg-hover` on hover).
  - Component-specific rules below the legacy block (~1500 lines of `.research-topbar`, `.timeline-*`, `.audit-log-*`, etc.) UNCHANGED per ticket scope.

### Verification

- Frontend `npm test`: **792/792 PASS** (unchanged — no JS surface touched).
- `npm run build`: clean, 90.86 kB CSS bundle (gzip 15.45 kB).
- code-reviewer: APPROVE, zero blocking issues. One nit (Google Fonts CDN trade-off) acknowledged + deferred; one suggestion (viewport self-contained background) skipped — `html, body { background: var(--bg-app) }` covers any uncovered area already.

### Out of scope (intentional, deferred)

- **Self-host fonts via `@fontsource/*`** — one-line dep add. Defer until a strict CSP or offline-install constraint surfaces.
- **Tokenising the ~1500 lines of component-specific styles below the touched block** — hardcoded hex values still abound in `.research-topbar`, `.timeline-*`, `.audit-log-*`, etc. These work today (tokens cascade through `var(--…)` references in the design-aware components), but a follow-up "design polish" ticket could replace the legacy hex values with token references for consistency.
- **Restyling the `--shadow-*` tokens against new dust** — currently uses the design's stock values; a brand-tightening pass could refine.
