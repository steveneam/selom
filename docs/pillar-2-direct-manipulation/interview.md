# Pillar 2 — owner interview (figure-editing workflow)

_2026-06-30 22:05 +10:00 (Australia/Sydney). The Prism-discipline interview that precedes the design pass
(the sibling of `docs/pillar-1-liveness-lineage/interview.md`). Grounds the canvas-editor design in how the
owner actually makes figures. Conducted while Layer A Phase 0 built in parallel._

## The questions + answers

**Q1 — Where does the FINAL polishing happen today?** → **Export to Illustrator/Inkscape.** The analysis
tool gives a rough chart; the real polishing happens afterward in a vector editor.

**Q2 — Do you need multi-panel assembly (Fig 1 = panels A–D on one artboard) in Selom?** → **Nice to have,
but later.** Single-figure polish first; multi-panel assembly can wait.

**Q3 — In the editable Prism-style table, what do you want to change live?** → **All of them, priority
most→least: (1) fix/tweak a plotted value · (2) relabel/rename · (4) change which rows are highlighted ·
(3) hide/show or reorder series.**

**Q4 — Which canvas features would you genuinely reach for?** → **All four + drawing.** Rulers + draggable
guides · gridlines + snapping · the color board · free text/arrows/callouts · **and adding/drawing
lines/shapes.**

## Synthesis — the north-star this sets

**Own the last mile: make the Illustrator/Inkscape export unnecessary.** The single most important finding
is Q1: the figure leaves Selom to get finished. So pillar-2's success criterion is concrete — *the owner
never has to export to a vector editor to publish a figure.* Every slice is judged against that.

**What forces the export today = annotations + alignment** (deduced from Q1 + Q4). The owner goes to
Illustrator to add text/arrows/lines/shapes and to align elements precisely. Therefore:

- The **annotation / drawing layer** (free text · arrows · callouts · lines · shapes) is **promoted from a
  phase-2 nice-to-have to a CORE slice** — it is the direct cause of the export. The canvas research had
  filed "free text boxes & callouts" as nice-to-have; the interview overrides that.
- **Alignment chrome** (rulers · draggable guides · snap-to-guide/grid) is core — it's the other reason the
  owner aligns in Illustrator.
- **Drawing lines/shapes** is in scope as **basic primitives** (line, arrow, rectangle, ellipse) — NOT a
  full vector path engine (no nodes/Bézier/booleans; that stays the Inkscape trap). Plotly's **native draw
  tools** (`config.modeBarButtonsToAdd: ['drawline','drawrect','drawcircle','drawopenpath','eraseshape']`,
  writing `layout.shapes`) are the low-effort technical path — they fit the spec-as-model + overlay
  architecture and stay reproducible (shapes live in the spec, export WYSIWYG).

**Editable table — sequence by the owner's priority:** (1) fix/tweak a plotted value [live, marked
override] → (2) relabel/rename → (4) change highlighted rows [extends the existing volcano gene-label
toggle] → (3) hide/show/reorder series. Build the table capabilities in that order.

**Multi-panel / compositing artboard stays a DEFERRED epic** (Q2 confirms the §8 call). Single-figure
polish first.

## Open items for a later touchpoint (not blocking the design pass)

- **Journal targeting** — which journals do you publish to (Nature/Cell/eLife/…)? Feeds the journal-styles
  phase-2 packs + the styling-AI's "match journal X" examples.
- **Toolbar IA disruption** — adopt tools-left / commands-top / palette-bottom now, or evolve the current
  tabbed inspector incrementally? (Spec §9.4 — a `fe-review` + `impeccable` call.)
- **Editable-table column language** — how to visually distinguish live-editable vs re-run columns (spec
  §9.3) — a design-pass call.
