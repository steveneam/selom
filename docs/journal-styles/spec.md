# Journal Styles — v1 spec

_Status: **v1 SHIPPED 2026-06-15** (BE `dd2e68f` + FE `ae221c6`, local/unpushed). Author: Claude (acting FE+BE)._

**Shipped vs spec:** all v1 tasks landed. The editor-toolbar `Style ▾` picker restyles live as one
undoable edit; export is WYSIWYG; the export menu's Style slot reflects the active style. As an
unplanned bonus from owner feedback, the export popover got a **focus treatment** — the page dims+blurs
behind it while the figure artboard stays crisp (it's the export subject).

**Known v1 limitations (deferred polish):**
- **Undo/redo doesn't rewind the picker label.** The figure (source of truth) reverts correctly, but the
  toolbar's active-style label is separate React state, so after undoing a style change the label can be
  stale until you pick again. Fix path: stamp the style id into the spec (e.g. `layout.meta.selom_style`)
  and derive the label from the spec — deferred to avoid Plotly unknown-key console noise + golden churn.
- Mock `style/apply` only remaps palette/font/bg (enough for an offline preview); the real backend runs
  the full transform.

**Future enhancement (owner-flagged, parked):** a true **export preview** — the crisp figure reflects the
chosen size preset's crop/aspect (e.g. Nature 89 mm framing) before download. Fuses size + style + export.

Installable/importable **visual style packs** for figures — the sibling of the journal
**size** presets shipped in the export feature (2026-06-15). Owner-requested; sequenced as
the feature after export. Memory: `selom-journal-styles-feature`.

## Locked decisions (owner, 2026-06-15)

1. **v1 boundary = engine + built-in styles + apply.** Extract `theme.py` into a named
   style **registry**, ship 4–5 built-in journal styles, expose + apply them. The Style
   **Store** (browse/install) and **import-your-own / capture-as-a-style** are **Phase 2**;
   a workspace **default** style is **Phase 3**. Out of scope for v1.
2. **Apply surface = export-skin + live editor preview, one definition.** Picking a style
   restyles the live figure in the editor (still fully editable); export is **WYSIWYG**
   (renders the on-screen spec verbatim). One style on the figure → it bakes into the
   download. No separate "export style" that can diverge from the editor.

## What a "style" is

A named **token pack** that parametrizes exactly what `theme.py` hardcodes today, applied as
the same non-destructive dict transform over the Plotly spec (touches styling only — layout,
fonts, palette, marker/line — never the data arrays, so figures stay editable Plotly specs).

```jsonc
// a Style (skills/styles/<id>.json or a Python token dict)
{
  "id": "nature",
  "label": "Nature",
  "description": "Nature house style — sans-serif, single-column friendly, CB-safe.",
  "attribution": "Spec follows Nature figure guidelines (springernature.com). Font: open Arimo (Arial-metric).",
  "tokens": {
    "font_family": "Arimo, Arial, Helvetica, sans-serif",
    "font_size_base": 12, "font_size_title": 15, "font_size_axis_title": 12,
    "font_size_tick": 10, "font_size_legend": 10,
    "ink": "#222222", "ink_strong": "#000000",
    "grid": "#ededed", "axis": "#000000", "paper": "#ffffff",
    "colorway": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"],
    "sequential": "Viridis",
    "show_grid": false,
    "title_align": "left",
    "marker_size": 5, "marker_opacity": 0.9, "line_width": 1.5
  }
}
```

Token set = today's `theme.py` constants, externalized: `FONT_FAMILY` + the per-role sizes,
`INK`/`INK_STRONG`, `GRID`/`AXIS`/`PAPER`, `COLORWAY`, `SEQUENTIAL`, grid default,
title alignment, and the marker/line weights used by the figure-type polish.

**Font note (v1):** sizes stay in Plotly **px** (the unit the whole app already uses), tuned
to look journal-appropriate at the default export sizes. Precise **pt-accurate** typography
(which interacts with the export DPI/size preset) is a Phase-2 refinement, called out, not faked.

## Built-in styles (v1 set)

| id | label | what differs | source / font |
|---|---|---|---|
| `selom` | Selom default | **today's `theme.py`, verbatim** (the default) | — |
| `nature` | Nature | sans-serif, gridless, black axes, CB-safe palette, left title | Nature fig guidelines · Arimo (Arial-metric) |
| `cell` | Cell | sans-serif, light grid, Cell-ish density | Cell STAR Methods fig guidelines · Arimo |
| `science` | Science | compact, sans-serif, thin lines (single-col friendly) | Science fig prep · Arimo |
| `grayscale` | Grayscale (print-safe) | grayscale colorway + `Greys` sequential, black ink | print-safe variant |

Journals mandate **legibility + colorblind-safety**, not specific palettes, so the meaningful
differences are font / weight / density / grid / CB-safe-or-grayscale — encoded honestly.

## Backend design (`app/backend`)

- **`skills/styles/`** — the registry. `registry.py` holds `STYLES = {"selom": …, "nature": …, …}`
  built from token dicts (or `<id>.json` files), plus `get_style(id)`, `list_styles()`.
  `selom` is built from today's constants so its output is **byte-identical** (golden-pinned).
- **`theme.py` refactor** — thread a `style` through the transform:
  `theme.apply(spec, skill_id, style="selom")`. The styling functions read tokens from the
  resolved style instead of module constants. **Re-application safety:** switch style-managed
  keys from `setdefault` to direct assignment and reset them before applying, so re-styling an
  already-themed figure fully takes (today's `setdefault` would ignore a new style's margins/
  colorscale). First-apply on a fresh spec is unchanged (key absent → assign == setdefault), so
  goldens stay green.
- **Endpoints:**
  - `GET /figures/styles` → `{styles: [{id,label,description,attribution}]}` (catalog for the picker).
  - `POST /figures/style/apply` body `{figure, skill_id, style}` → `{figure: styledSpec}`
    (the editor calls this for live preview; one Python source of truth, no TS duplicate of the transform).
  - `POST /figures/export` — **no new param needed** for the WYSIWYG path (renders the spec verbatim).
    Keep an **optional** `style` param as a headless convenience (apply-then-render); the FE menu
    does not expose an independent style dropdown, so editor and export never diverge.
- **Tests:** goldens for `selom` unchanged (re-run `regen_golden.py` only if intended); a
  per-style snapshot test (apply each built-in to a fixture → assert tokens land); a
  re-application test (selom → nature → selom round-trips cleanly); `/figures/styles` +
  `/figures/style/apply` API tests.

## Frontend design (`app/frontend`)

- **`lib/styles-api.ts`** — `fetchStyles()` + `applyStyle(figure, skillId, styleId) -> FigureSpec`.
- **Editor toolbar style picker** — a `Style ▾` `Select` in the Figure-tab toolbar (next to
  Export/Undo). Picking a style calls `applyStyle` and commits the result as **one undoable
  history entry**: `store.commit([{op:"replace",path:"/data",value:styled.data},
  {op:"replace",path:"/layout",value:styled.layout}])` — undo reverts the restyle. (Verify
  `lib/patch.ts applyPatches` handles root replaces; fall back to a `store.init`-with-history
  shim only if needed.)
- **Export menu** — the existing forward-compat **"Style" slot** becomes a **read-only reflection**
  of the active style ("Style: Nature") so the WYSIWYG promise is visible; no separate dropdown.
- **MSW mock** — `GET /api/figures/styles` (the 5 built-ins) + `POST /api/figures/style/apply`
  (echo the figure with the style's `colorway`/`font_family` patched in, enough to preview offline).
- Built with the 3 design skills; browser-verified at desktop (pick style → live restyle → undo →
  export reflects it).

## Licensing (already-decided posture)

Encode the **spec** (sizes/weights/palette/CB-safety) and **cite** the journal guideline; do
**not** gate. Map proprietary fonts (Helvetica/Arial) → open metric-compatible equivalents
(**Arimo** / Liberation Sans) or the system stack. **Never bundle a paid font.** Per-style
`attribution` string carries the citation, surfaced on the picker (and later the Store cards).

## Out of scope (v1) — deferred

- **Phase 2:** Style **Store** surface (browse/install, Verified/Community tiers), **import-your-own**
  (upload a JSON style pack), **capture current figure as a style** (derive a reusable pack from an
  edited spec) — the moat-y "install/import" half.
- **Phase 3:** workspace **default** style (every new run comes out in the chosen house style).
- pt-accurate typography tied to the export size preset.

## Verification plan

- BE: `pytest` (goldens unchanged + new style/apply/re-apply/endpoint tests); ruff; live uvicorn
  smoke (`/figures/styles`, `/figures/style/apply`, and a styled `/figures/export`).
- FE: tsc + `next build`; browser-verify at desktop — pick each style → live restyle, undo reverts,
  export renders the active style (WYSIWYG), console clean.

## Task list (v1)

1. BE: `skills/styles/` registry + 5 built-in token packs (`selom` byte-identical).
2. BE: refactor `theme.py` to thread `style` + be re-application-safe.
3. BE: `GET /figures/styles` + `POST /figures/style/apply` (+ optional export `style` param).
4. BE: tests (snapshot per style, re-apply round-trip, API).
5. FE: `lib/styles-api.ts`.
6. FE: editor-toolbar `Style ▾` picker → live apply as one undoable commit.
7. FE: export-menu Style slot → reflect active style.
8. FE: MSW mocks.
9. Verify both lanes; scoped commits `feat(backend:)` / `feat(frontend:)`; update handoff + memory.
