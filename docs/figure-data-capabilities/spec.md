# Spec (DRAFT / research-first) — Capability-driven figure editing surface (`figure-data-capabilities`)

> **Status: STUB for next-session deep work (owner steer 2026-06-24).** This is not yet an
> implementation spec — it captures the problem + the design direction so next session starts from
> research + design, not a live patch. Sequence: research → design → spec → build (the Selom way).
>
> **⚑ Next session OPENS with an owner interview** (owner-requested 2026-06-24) — use AskUserQuestion
> to verify + harden this spec BEFORE building. Topics: (a) where the capability contract lives
> (`meta.selom` vs `skill.json`) + which capabilities; (b) the gesture model (default drag = select?
> zoom/pan as buttons? does zoom matter for ERG traces? keyboard modes); (c) the figure→tools mapping
> (which skills get marks / fit / scale-bar / none); (d) scope (ERG-only first vs general); (e) the
> a/b dot UX (label show/hide + styling — labels weren't visible in the T16 demo). The answers
> finalize §D1–D3 below.

## Problem
The figure editor (cosmetic inspector) and the **Figure-data** window currently wire editing
affordances too broadly. The ERG landmark-dot **drag** is bound to *any* editable, non-overlay figure
(it silently no-ops when there are no dots); the **Marks panel** shows when `meta.selom.marks` is
present; **zoom** is Plotly's default drag gesture. The owner's steer (2026-06-24): the editing
surface must **recognize the figure's data + skill** and present only the right tools —
- dot-dragging should exist for an **ERG trace grid / line graph**, never for a scRNA-seq UMAP scatter;
- **zoom** (if useful at all for traces) should be a **button-activated mode**, not the default
  click-drag; the default drag should be **select / no-op**, not box-zoom;
- this is the **same "window-pane metadata" concept** as `meta.selom` — generalized from per-feature
  hints into a per-figure **capability contract** that drives the whole window.

## Direction (to research + design next session)

### D1 — One derived capability, not per-route / per-skill-id wiring
Every editing affordance (dot-drag, Marks panel, dot-toggle, fit knobs, scale-bar, …) keys off **one
capability model derived from the figure's `meta.selom`** (the skill stamps it; the editor reads it).
`deriveFigureModel` already does this for scalebar/overlay/series — fold landmark editing in as a
first-class capability (`capabilities.landmarkMarks`), and gate the canvas drag + Marks editor on it.
A figure that doesn't stamp it gets none of that UI. (Today the drag is wired for any editable figure
and no-ops without dots — replace with explicit capability-gating so the gesture story is coherent.)

### D2 — Gesture model: default ≠ zoom
Remove the zoom-vs-drag conflict at the source instead of intercepting Plotly's mousedown:
- For a figure with editable landmarks, set Plotly `dragmode` to a **non-zoom default** (e.g. `false`
  or a select mode), so a stray drag never box-zooms.
- Expose **zoom / pan as explicit modebar buttons** (Plotly ships them) — a mode the user *presses*.
- The landmark-dot grab is then an unambiguous interaction (no competition with pan/zoom).
- Research: Plotly `dragmode` options (`false`, `select`, `pan`, `zoom`), modebar customization, and
  whether `select` interferes with the custom dot-grab. Mental model = GraphPad / Illustrator: select
  is the default tool, zoom is a mode.

### D3 — Figure-capability **descriptor** (the dynamic Figure-data window)
Generalize `meta.selom` from "hints" to a **declared contract**: each skill enumerates which editing
panels + gestures its figure supports (`marks` editor, Naka-Rushton fit knobs, scale-bar, default
gesture, …). The Figure-data window **and** the editor inspector tabs **compose** their tools from that
descriptor — so adding a skill with a custom editor is **declarative**, not a hardcoded `if skillId`.
- Research: descriptor schema (where it lives — `meta.selom` vs `skill.json`); how one descriptor
  drives both surfaces; backward-compatibility with the inference floor (a third-party figure with no
  descriptor still gets a correct generic editor).

## Out of scope / keep
- The **backend** landmark re-measure + provenance (erg-manual-marks v1) is shipped and correct — the
  drag/panel write `manual_marks`, the metric re-measures, the Statistics table updates (verified live
  on real Diagnosys data). This spec is about *which editing tools appear and how gestures behave*, not
  the measurement.
- The numeric Marks panel works; its gating (shown when `seededMarks` present) is already the D1 model
  in miniature — generalize it.

## References
- `app/frontend/lib/figure-model.ts` (`deriveFigureModel`, capabilities) — the inference floor to extend.
- `app/frontend/components/figure/{figure-canvas,mark-drag}.tsx` — the drag wiring to capability-gate.
- `app/frontend/components/project/{figure-data-panel,marks-editor}.tsx` — the window to make descriptor-driven.
- `docs/erg-manual-marks/spec.md` (the shipped backend/v1) · `docs/figure-editor-contract/spec.md` (`meta.selom`).
- memory [[selom-figure-editor-architecture]] [[selom-erg-module]].
