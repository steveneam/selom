# Pillar 1 — Liveness & Lineage · Owner Interview (running log)

> Resolves the open questions in `research.md §5`. Feeds the design + spec. Question
> IDs (B1, C1, …) reference that section. Live log — appended as the interview proceeds.
>
> _Started 2026-06-16 · Claude (FE+BE acting) ↔ owner (Steven)._

---

## Resolved

- **B1 — Workrail replaces the tabs.** ✔ The Prism-style sectioned left workrail
  (**Data → Statistics → Figure → Layout**) *becomes* the project navigation, replacing the
  current Overview / Data / Workbench / Figure tabs. The four sections feed top-to-bottom so the
  raw-data→output connection is the IA itself.

- **C1 — Branch & compare unifies under "parameter sweep."** ✔ All three fork types (params,
  datasets, skills) are real, but the owner's call: focus the primitive on **parameter sweeps**
  because it's the general case — *vary one dimension → N variants → compare* — and the other
  forks fall out of the same mechanism (vary the dataset axis / the skill axis instead of the
  param axis). Design ONE variant-set primitive, lead with parameters. (Owner note: a strong
  engine reduces the *need* for param sweeps; focus then shifts to dataset forks — but the sweep
  mechanism still subsumes that.)

## Direction set (recommendation given, owner confirm pending)

- **B3 — The "Statistics" section = the result table behind each figure.** In multi-omics the
  Statistics node is **not** a catalog of statistical *tests* (Prism's t-test/ANOVA world) — it
  is the **machine-readable result table the skill already computes**, surfaced between Data and
  Figure. Selom skills already produce these; today only the plot is shown. Per skill:
  - volcano / deg / proteomics_de → the DE table (gene, log2FC, test stat, p, padj)
  - enrichment / gsea → the enrichment table (term, set size, overlap, p, FDR, genes)
  - markers → the marker table (gene, cluster, score, logFC, p)
  - heatmap / clustermap → the matrix + clustering stats (linkage, z-scores)
  - corr_heatmap → the correlation matrix (r, p)
  - umap / cluster → cluster assignments + sizes + silhouette / variance explained
  - purely-visual skills → thin / no stats node (rail stays honest, no empty nodes)
  **Scope guard** (answers "it will be huge"): do NOT build a test chooser or add new statistics
  — just **plumb the table each skill already emits** into an inspectable / exportable / citable
  node. Value: supplementary-table export + the "retrace & defend" receipts; and it's the natural
  future home for **Pillar 3** (the test used, FDR method, Analysis Checklist live here).
  _Open for owner: show the Stats node only when substantive (recommended), or always?_

## Resolved — round 2 (2026-06-16)

- **C2 — Compare = both.** ✔ The compare view shows variants **side-by-side (figures)** *and* a
  **numbers/params diff** (e.g. "res 0.5 → 12 clusters; 1.0 → 19; these markers changed; padj
  shifted"). The stats-diff leans on the Statistics-node tables (B3).

- **D1 / Freeze — folded into versioning, not a separate subsystem.** ✔ Owner's rethink: with
  **explicit re-run** a figure never *silently* changes (it only changes when you click run), so a
  heavyweight "freeze" feature is redundant with the staleness signal + provenance + version
  history. **Resolution:** freeze = *tag a version as "the paper one"* on top of the version
  history we're already building for branch/compare; immutability is inherent (each run/version is
  a distinct record). No standalone freeze subsystem. (Caveat to watch: in-canvas *edits* still
  mutate the working figure — the "tagged version" is what protects the submitted state.)

- **E1 — Dogfood now, durable architecture in mind.** ✔ Built for the owner's dogfood workflow
  (RPGRIP1 / Fidelle / ALPK1, single user), **but** the lineage/version store must be designed
  durable-ready for the future web stack (**Supabase + Vercel + Render**, the eamos pattern). Posture:
  implement against the existing `ProjectStore` interface, schema-shaped for the Supabase swap
  (`figures` / `figure_history` / etc., design §5) — a backend-impl change later, not a FE rewrite.

- **B4 / Layout — DROPPED from Pillar 1.** ✔ Owner doesn't use Prism's Layout (uses PowerPoint /
  Photoshop; Prism's is underwhelming — hard to re-zone + label A/B/C; wants Illustrator precision).
  **Resolution:** the workrail is **Data → Statistics → Figure** (no Layout section). Feed the
  owner's existing external layout workflow with **clean per-figure SVG/PDF export** (already
  shipped, B4 Kaleido). A real in-app multi-panel composer is a *separate future feature* — built
  Illustrator-grade or not at all. Tech pointers for that day (owner asked):
  - Python templating: **FlyRanch/figurefirst** (Inkscape SVG template → matplotlib fills named
    panels; rearrange in Inkscape, rerun) · **svgutils** (compose existing SVG panels + auto A/B/C
    labels, pure-Python — composes Selom's Plotly SVG exports directly).
  - In-app web canvas (Illustrator-feel): **Konva.js** (Transformer resize/rotate handles,
    snap-to-grid, React bindings) or **Fabric.js** (SVG import/export round-trip). tldraw for a
    polished infinite-canvas base.

## Net effect on Pillar 1 shape

The four original jobs collapse cleaner: **(1) catch staleness** = the core liveness engine ·
**(2) retrace/defend** = lineage rail + the receipts we already emit · **(3) branch & compare** =
one **variant-set / version-history** primitive (parameter-sweep-led) · **(4) freeze** = a *tag*
on (3), not its own feature. **Layout is out.** So Pillar 1 ≈ *sectioned workrail
(Data→Stats→Figure) + staleness engine + version history (subsumes branch/compare + freeze-as-tag)
+ Statistics-node plumbing.*

## Still open → carry recommended defaults into the spec (the review gate)

These are detail-level; rather than belabor the interview, I'll bring recommended defaults into
`spec.md` for owner review:
- A1–A3 — staleness trigger granularity (which factors gate; replace-vs-append; transitive
  propagation + cascade display).
- B2 — rail item granularity (per figure vs per analysis vs per dataset).
- B3 tail — show the Statistics node only when substantive (recommended) vs always.
