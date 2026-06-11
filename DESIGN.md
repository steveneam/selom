---
name: Selom
description: A dark multi-omics IDE with a luminous, editable figure artboard.
colors:
  background: "#0a0e16"
  foreground: "#e6edf3"
  card: "#111824"
  popover: "#141c28"
  primary: "#22d3ee"
  primary-foreground: "#04161b"
  secondary: "#1a2433"
  secondary-foreground: "#cdd9e5"
  muted: "#161f2c"
  muted-foreground: "#8b98a9"
  accent: "#16404a"
  accent-foreground: "#a5f3fc"
  destructive: "#f43f5e"
  destructive-foreground: "#fff5f7"
  border: "#1e2a3a"
  input: "#233044"
  ring: "#22d3ee"
  artboard: "#ffffff"
  artboard-foreground: "#0f172a"
  chart-1: "#22d3ee"
  chart-2: "#a78bfa"
  chart-3: "#fb923c"
  chart-4: "#34d399"
  chart-5: "#f472b6"
  chart-6: "#facc15"
  chart-7: "#60a5fa"
  chart-8: "#f87171"
typography:
  headline:
    fontFamily: "Geist Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Geist Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Geist Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Geist Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.06em"
  mono:
    fontFamily: "Geist Mono, ui-monospace, SFMono-Regular, monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
    fontFeature: "tabular-nums"
rounded:
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "14px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "20px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  button-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.secondary-foreground}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.foreground}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.xl}"
    padding: "20px"
  input:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "36px"
  badge-verified:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
    padding: "2px 6px"
---

# Design System: Selom

## 1. Overview

**Creative North Star: "The Lit Lab Bench"**

Selom is a dark multi-omics IDE built so a bench scientist — not a bioinformatician — can turn raw data into a publication-quality figure. The whole interface is a **dark, calm workspace** (a deep blue-black bench, `#0a0e16`) on which one thing glows: the **figure**. Journal figures are printed on white paper, so Selom renders every figure on a **light `#ffffff` artboard floating in the dark shell** — the way a Figma artboard floats on its canvas. The dark chrome recedes; the science lights up. The single accent is a **luminous cyan** (`#22d3ee`) that behaves like a status light on lab equipment: it marks what is live, selected, or actionable, and nothing else.

Density is **product-grade and confident, not cramped**. This is a tool people work inside for an hour at a time: tight type scale, hairline dividers, tonal layering instead of drop-shadows, tabular numerals everywhere a value lives. It is closer to Linear or a code editor than to a marketing SaaS dashboard. It explicitly rejects the "AI bio-tool" reflex — purple-on-black gradients, neon glassmorphism cards, hero-metric templates, and emoji-decorated empty states. Trust is the product (every figure is traceable, reproducible, "no black box"), so the visual language is precise and quiet, never flashy.

**Key Characteristics:**
- Dark blue-black shell; the figure is the only bright surface, always on a light artboard.
- One accent — cyan — used as a status light, never as decoration.
- Depth from hairline borders + tonal layering (`background → card → popover`), not shadows.
- Tabular mono numerals wherever a number is shown (params, counts, axis values).
- Confident product density: small type, calm spacing, no choreography.

## 2. Colors

A near-monochrome blue-black ramp carrying a single cyan signal color, with a strictly light artboard for figures and a colourblind-aware data colourway.

### Primary
- **Luminous Cyan** (`#22d3ee`): The brand glow and the only accent. Reserved for primary actions, the current selection/active nav, focus rings, "Verified" status, and live-state indicators. Its `primary-foreground` is a near-black cyan-ink (`#04161b`) so text on a cyan button stays legible.

### Neutral
- **Deep Blue-Black Bench** (`#0a0e16`): The app background — the canvas everything floats on.
- **Panel Slate** (`#111824`): Cards, raised surfaces, the project rail (`bg-card/40`).
- **Popover Slate** (`#141c28`): Menus, popovers, the next tonal step up.
- **Secondary Surface** (`#1a2433`): Secondary buttons, avatar chips, quiet fills.
- **Muted Field** (`#161f2c`): Inset/muted backgrounds, `kbd` chips.
- **Near-White Ink** (`#e6edf3`): Primary text.
- **Slate Ink** (`#8b98a9`): Secondary text, labels, icon defaults. **Body copy must use near-white ink, not slate** — slate is for secondary/label text only (contrast guardrail).
- **Hairline** (`#1e2a3a`): Dividers and card borders — the primary depth cue.
- **Control Stroke** (`#233044`): Input/control borders, hover thumb on scrollbars.

### Tertiary (figure surface)
- **Artboard White** (`#ffffff`) / **Artboard Ink** (`#0f172a`): The publication figure surface and its text. Always light, regardless of theme — this is the printed page.

### Semantic
- **Cyan-Tinted Accent** (`#16404a` bg / `#a5f3fc` ink): Hover and selected backgrounds in nav/lists.
- **Rose Destructive** (`#f43f5e`): Delete/destructive actions and danger badges only.
- **Amber Warn** (`#f59e0b`): Guardrail warnings (batch-effect, low-cell, multiple-testing) — a first-class product signal, not an error.

### Data colourway
- **chart-1…8** (`#22d3ee, #a78bfa, #fb923c, #34d399, #f472b6, #facc15, #60a5fa, #f87171`): The default trace palette, ordered to stay distinguishable for common colour-vision deficiencies. Used **only** inside the artboard, never on the chrome.

### Named Rules
**The Status-Light Rule.** Cyan is a signal, not a paint. It appears on ≤10% of any screen — primary action, current selection, focus, live state. If cyan is being used to make something "pop," it is wrong; remove it.

**The Light-Artboard Rule.** A figure is *always* rendered on the `#ffffff` artboard with `#0f172a` ink, even though the app is dark. Never render publication data on a dark surface; the figure is the printed page and must read as one.

## 3. Typography

**Body / UI Font:** Geist Sans (with `ui-sans-serif, system-ui, sans-serif`)
**Mono / Data Font:** Geist Mono (with `ui-monospace, SFMono-Regular, monospace`)

**Character:** One technical-geometric sans carries the entire UI — headings, labels, buttons, body — at product density. Geist Mono is the deliberate second voice, reserved for *numbers and identifiers*: parameter values, counts, axis ticks, keyboard hints. The split is semantic (prose vs. data), never decorative.

### Hierarchy
- **Headline** (600, 1.5rem / 24px, `tracking-tight`): Page titles ("Welcome back, Steven"). One per screen.
- **Title** (600, 1rem / 16px): Card titles, skill names, panel headers.
- **Body** (400, 0.875rem / 14px, line-height 1.5): Default text, descriptions, summaries. Cap prose at 65–75ch.
- **Section Label** (500/600, 0.6875–0.75rem / 11–12px, `uppercase tracking-wider`, slate ink): Section headers ("Recent projects"), the "Projects" rail group, kicker eyebrows ("Command center").
- **Micro Label** (500, 0.625rem / 10px, `uppercase tracking-wider`): Badges and tier chips only.
- **Mono / Tabular** (400, 0.875rem, `tabular-nums`): Every numeric value — stat tiles, param inputs, slider read-outs, counts, axis fields. Applied via the `.tabular` utility.

### Named Rules
**The Tabular-Numbers Rule.** Any digit a user might compare or watch change is set in Geist Mono with `tabular-nums`. Counts, params, p-values, fold-changes — never proportional figures that jitter as they update.

**The One-Sans Rule.** Geist Sans owns all prose and UI. Do not introduce a display or serif face; the only permitted second family is Geist Mono, and only for data.

## 4. Elevation

Selom is **flat by default**. Depth is built from two cues, in order: (1) **hairline borders** (`#1e2a3a`) on every panel, card, and divider; (2) **tonal layering** — surfaces step up in lightness from `background` (#0a0e16) → `card` (#111824) → `popover` (#141c28) as they come forward. Drop-shadows are nearly absent; cards carry only a whisper (`shadow-sm`). The one expressive elevation material is **the cyan glow**: the primary button and the brand mark emit a soft cyan halo to read as "live/energized." Glow is earned by primary affordances only.

### Shadow Vocabulary
- **Card rest** (`box-shadow: 0 1px 2px rgba(0,0,0,0.20)` — Tailwind `shadow-sm`): The only ambient shadow; keeps cards from floating flatly on the bench.
- **Primary glow** (`box-shadow: 0 0 0 1px color-mix(in oklab, var(--primary) 40%, transparent)` at rest → `0 0 18px -2px color-mix(in oklab, var(--primary) 60%, transparent)` on hover): The cyan halo on the primary button. Structural, not ambient — it signals "this is the action."
- **Mark glow** (`filter: drop-shadow(0 0 6px color-mix(in oklab, var(--primary) 55%, transparent))`): The luminous halo on the Selom hex mark.

### Named Rules
**The Hairline-First Rule.** Reach for a border before a shadow. If two surfaces need separating, a `#1e2a3a` hairline or a tonal step does it. A drop-shadow on a panel is almost always wrong here.

**The Glow-Is-Earned Rule.** The cyan glow belongs to primary actions and the brand mark only. Never glow a card, a secondary button, or a static container "for atmosphere."

## 5. Components

### Buttons
- **Shape:** Gently rounded (8px, `rounded-md`); 36px tall default (`h-9`), `h-8`/`h-11` for sm/lg, `size-9` icon. Font `text-sm font-medium`, 150ms color transition.
- **Primary:** Cyan fill (`#22d3ee`) with near-black cyan ink, a 1px cyan inset ring at rest, and a cyan glow on hover (hover lightens the fill ~12% toward white). The one loud control.
- **Secondary:** `#1a2433` fill, light-slate ink, lightens on hover. The default non-primary action.
- **Outline / Ghost:** Transparent with (outline) or without (ghost) a control-stroke border; both fill with the cyan-tinted `accent` on hover. Quiet, table/toolbar-grade.
- **Destructive:** Rose fill, reserved for delete.
- **Focus:** 2px cyan ring offset from the background (`focus-visible:ring-2 ring-ring ring-offset-2`) on every variant.

### Chips / Badges
- **Style:** Tiny (10px), `uppercase tracking-wider`, `rounded-md`, 1px border. Used for tier and status.
- **Variants:** `verified` (cyan-tinted bg + border + cyan ink — "runs now"), `community` (muted neutral — "queued"), `warn` (amber — guardrails), `danger` (rose), plus neutral `default`/`outline`. Tier honesty is a product rule: Verified vs. Community is always visibly distinct.

### Cards / Containers
- **Corner Style:** 14px (`rounded-xl`).
- **Background:** `#111824` (`bg-card`) on the `#0a0e16` bench; hover variants lift toward `bg-card/80` and a `primary/40` border.
- **Shadow Strategy:** Hairline border + `shadow-sm` only (see Elevation). Never nest cards.
- **Internal Padding:** 16–20px (`p-4`/`p-5`).

### Inputs / Fields
- **Style:** 36px tall, 1px control-stroke border (`#233044`), translucent dark fill (`bg-background/60`), `rounded-md`, `text-sm`. Placeholder uses muted ink at 70%.
- **Focus:** Border shifts to `ring/60` + a 2px cyan ring at 30% (`focus-visible:ring-2 ring-ring/30`). No glow.
- **Search field:** Leading search icon + trailing `⌘K` mono `kbd` chip; the header's command affordance.

### Navigation
- **Project rail:** 256px (`w-64`), `bg-card/40`, hairline right border. Top: brand lockup. Then Home / Skill Store rail links, a "Projects +" group with a per-project colour swatch, and a pinned Settings + account footer.
- **Rail link states:** default = `foreground/85`; hover = `accent/50` bg + full-ink text; **active = `accent` bg + `accent-foreground` (cyan-200) + medium weight**. Active state is carried by the cyan-tinted accent, consistent with the Status-Light Rule.
- **Header:** 56px tall, `bg-card/30 backdrop-blur-sm`, hairline bottom; holds the search field and a context label. The one sanctioned use of backdrop-blur.

### Signature Component — The Figure Artboard
The editable Plotly figure is the product's centerpiece: a **light `#ffffff` artboard** docked in the dark shell, paired with a tabbed property inspector (Style / Axes / Legend / Data / Page). Every control edits the figure's JSON spec via RFC-6902 JSON-Patch — instant, no recompute. The artboard is the one place the data colourway (`chart-1…8`) and artboard ink (`#0f172a`) appear. Treat it as the printed page floating on the bench.

## 6. Do's and Don'ts

### Do:
- **Do** keep cyan (`#22d3ee`) to ≤10% of any screen — primary action, current selection, focus, live state. It is a status light (the Status-Light Rule).
- **Do** render every figure on the light `#ffffff` artboard with `#0f172a` ink, even in the dark app (the Light-Artboard Rule).
- **Do** separate surfaces with a `#1e2a3a` hairline or a tonal step (`background → card → popover`) before reaching for a shadow (the Hairline-First Rule).
- **Do** set every number — params, counts, p-values, axis ticks — in Geist Mono `tabular-nums` (the Tabular-Numbers Rule).
- **Do** use near-white ink (`#e6edf3`) for body copy; reserve slate (`#8b98a9`) for secondary and label text, and verify ≥4.5:1 contrast.
- **Do** surface statistical guardrails as amber `warn` badges *before* a figure — they are a feature ("no black box"), not an error.
- **Do** keep one consistent component vocabulary: same button, same badge, same input across Home, Store, Project, and Editor.

### Don't:
- **Don't** use cyan as decoration, or glow cards/secondary buttons/static containers "for atmosphere" (the Glow-Is-Earned Rule).
- **Don't** render publication data on a dark surface — figures are never dark.
- **Don't** ship the "AI bio-tool" reflex: purple-on-black gradients, neon glassmorphism cards, gradient text, or the hero-metric template.
- **Don't** use `border-left`/`border-right` > 1px as a colored accent stripe on cards, list items, or alerts. Use full borders or a tint.
- **Don't** introduce a display or serif font; Geist Sans owns the UI, Geist Mono owns data, nothing else (the One-Sans Rule).
- **Don't** nest cards, or default to a modal — exhaust inline/progressive affordances first.
- **Don't** let body text fall to slate gray on a tinted panel; that is the single most common readability failure here.
