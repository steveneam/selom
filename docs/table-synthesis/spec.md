# Proprietary table synthesis (L3) — spec

> Status: **SIGNED OFF (s43, 2026-06-21) — building.** Owner accepted the spec defaults
> (D-t1 A-first · D-t2 synthesized MAY feed the score, tagged · D-t3 Tier A first · D-t4 proprietary).
> **Tier A COMPLETE (9/9) + reader integration SHIPPED (s43)** + **the Tier-B clean trio SHIPPED
> (s44).** `extract/synthesize.py`: pca · composition · cluster · pvca · regression · integration ·
> trajectory (part 1, `39b44b3`) **+ `umap_scrna`/`annotate`** (trace-length synthesizers, verified
> against the live stub panels — per-type *cluster* counts aren't in the figure so they're not faked,
> S4; subtitle totals fold into the title) **+ `corr_heatmap`/`sankey`/`upset`** (s44, each behind a
> faithfulness gate → `None` on a non-conforming shape: corr_heatmap → long-form `[row,col,r]`
> dropping the redundant lower triangle + r=1 diagonal when square-symmetric; sankey → `[source,
> target,value]` resolving link indices→labels, out-of-range index → None; upset → `[intersection,
> sets,size]` from the size bars + member sets read back from the "present" dots). Each verified on
> its skill's own live stub figure. **Build step 2 done:** `extract/readers.py` `read_metric` now
> falls back to `synthesize_table` when the skill emits no native table, re-tagged `L3`/synthesized at
> reduced confidence (S3) — a real computed value, so it MAY feed the score (S2); registering the new
> synthesizers auto-extended reader coverage (no reader edit). **Remaining:** the **lossy** Tier-B set
> (`scorecard`/`boxplot`/`violin`/`heatmap`, each gated or → L4) · FE Statistics-node wiring
> (cross-lane) · `proteomics_de` at source.
> Original directive (s41): make our own custom Statistics tables so skills that don't emit one *do*;
> skills that genuinely can't → don't force it → L4 Pro AI. Sequenced after the L1/L2 reader (shipped).
> Companions: `docs/reproduction-engine/skill-table-schemas.md` (the inventory this builds on),
> `docs/reproduction-engine/live-reproduction-spec.md` (the consumer), `extract/readers.py` (L1/L2),
> [[selom-proprietary-skills-folder]] [[layered-deterministic-extraction]] [[selom-extract-reproduction-bridge]].

## 1. Why (the moat)

The s41 inventory found that **only 10 of ~30 skills emit a Statistics `table`**. The other ~20 are
purely visual — their numbers live in figure title/subtitle/axis/annotation strings or trace arrays
(`docs/reproduction-engine/skill-table-schemas.md`). That hurts in two places:

- **The product.** A figure without a Statistics node is less trustworthy and less editable. "Every
  compatible figure ships its numbers as an editable table" is a concrete, demoable Selom edge
  (Pillar 1, [[selom-figure-editor-architecture]]).
- **Reproduction.** The L1/L2 reader has to special-case figure-string regex and trace lookups per
  skill. If every skill exposed a canonical table, the reader becomes a uniform table read.

**L3 is the layer that synthesizes a canonical Statistics table for a tableless skill from its own
output.** It is the third layer of Selom's extraction stack ([[layered-deterministic-extraction]]):
L1 skill-specific reader · L2 generic reader · **L3 table synthesis** · L4 Pro AI. It is the moat
because it is cross-cutting (every skill), curated (one synthesizer per skill), and dual-use (FE +
reproduction) — not one feature.

## 2. The honest scope (what L3 is and is NOT)

- **L3 reads a skill's OWN computed output** (the traces/strings the skill already produced) and
  re-shapes it into a table. **It recomputes nothing and invents nothing.** A composition synthesizer
  reads the proportions the skill already plotted; it does not re-run the analysis.
- **Therefore a synthesized value IS a real computed value** — *not* a digitized guess. This is the
  crucial distinction from chart-digitization ([[selom-extract-reproduction-bridge]], where
  digitize ≠ reproduce and never feeds the score): there we trace pixels off a *published* image; here
  we re-shape *our own engine's* numbers. **A synthesized table MAY feed the Reproducibility Score.**
  (Confidence is tagged so a synthesized read is distinguishable from a native-table read — §5.)
- **Don't force it.** Node-link skills (`go_graph`/`pathway`/`string_network`) carry per-node stats
  only in hover strings, and `boxplot` carries raw distributions; these are lossy or genuinely
  table-hostile. Where a faithful table can't be synthesized deterministically, **leave it to L4 Pro
  AI** (propose a table; never required; never gates the score). No fabricated table.

## 3. What already exists (reuse)

| Need | Existing piece |
|---|---|
| The canonical table shape | `skills/_table.py` `table(columns, rows, title)` (+ `de_table`) — D7: additive, `{data,layout}` stays pure |
| Per-skill output shapes | `docs/reproduction-engine/skill-table-schemas.md` (exact columns / where every metric lives) |
| The reproduction consumer | `extract/readers.py` (L1/L2) — already reads native tables + figure strings + traces |
| Proprietary namespace + origin flag | `skills/proprietary/` + `SkillSpec.origin` (cepo precedent) |
| FE Statistics node | `lib/skills-api.ts` `StatsTable` + the figure-editor Statistics panel (renders any `{columns, rows}`) |

## 4. Architecture

A new **synthesis layer** — `extract/synthesize.py` (library, pure) — with one synthesizer per
tableless skill, keyed by `skill_id`:

```python
def synthesize_table(skill_id: str, figure: dict) -> dict | None:
    """Read a tableless skill's figure → a canonical {columns, rows, title, synthesized: True}
    Statistics table, or None when this skill has no deterministic synthesizer (→ L4)."""
```

- **Read-only over `figure`** (traces + layout strings). No skill execution, no data access.
- **Additive + non-destructive.** Never mutates the skill or the figure; the consumer attaches the
  synthesized table where a native one is absent.
- **One consumer seam, two callers:**
  - *Reproduction:* `extract/readers.py` gains a pre-step — if `table is None`, try
    `synthesize_table(skill_id, figure)` before L1/L2. Uniform: the reader then reads a table whether
    native or synthesized.
  - *FE Statistics node:* the run/job response attaches `table = table or synthesize_table(...)` so
    a tableless skill suddenly shows an editable Statistics table in the editor. (Wiring TBD with the
    FE; out of this spec's first build.)
- **Provenance:** synthesized tables carry `synthesized: True` (+ a `source` note). The reader stamps
  a lower confidence for synthesized reads than native-table reads; the FE labels the node
  "computed by Selom from the figure".

## 5. The synthesizer registry (from the inventory)

Ordered by reproduction value × synthesis cleanliness. **Tier A** = clean trace/string → table,
build first; **Tier B** = synthesizable but lossy/needs care; **L4** = leave to AI.

| skill | Tier | synthesized columns | read from |
|---|---|---|---|
| **pca** | A | `[component, variance %]` | axis titles `PC1 (39.7%)` |
| **composition** | A | `[category, <series…> %]` | bar trace arrays (the JEV Müller % case) |
| **cluster** | A | `[cluster, cells, %]` (+ silhouette in title) | bar `y` + subtitle |
| **umap_scrna** | A | `[cluster, cells]` | one trace per `color_by` level |
| **annotate** | A | `[cell type, clusters, cells]` | subtitle counts + per-type trace lengths |
| **pvca** | A | `[factor, variance %]` | bar `x`/`y`/`text` |
| **regression** | A | `[statistic, value]` (slope, R², p) | `layout.annotations[0].text` |
| **integration** | A | `[metric, before, after]` (batch mixing) | title `<sub>` |
| **trajectory** | A | `[metric, value]` (clusters, edges, lineages) | subtitle |
| **corr_heatmap** | B | long-form `[row, col, r]` or the z-matrix | trace `z` + `x`/`y` labels |
| **sankey** | B | `[source, target, value]` | trace links |
| **upset** | B | `[intersection, sets, size]` (+ set sizes) | bar `y`/`text` + dot matrix (members lost) |
| **scorecard** | B | `[condition, metric, score]` (normalized) | scatterpolar/heatmap traces |
| **boxplot** | B | `[group, n, min, q1, median, q3, max]` (compute server-side) | raw per-group trace values |
| **violin** | B | `[gene, pubmed hits, verdict]` (annotate=pubmed only) | annotation string |
| **heatmap** | B | `[gene, <group…> z]` | trace `z` + `x`/`y` (z-scores, not absolute) |
| **proteomics_de** | — | (the GAP) it computes real per-protein logFC+padj but attaches no table | **fix at source** (attach a `de_table`), not synthesis |
| **go_graph / pathway / string_network** | L4 | per-node p/FDR/overlap — only in hover | leave to Pro AI (hover-scrape is fragile) |
| **deg** | — | already a table, but cannot give DE counts (no padj/direction) | route DE-count goldens to `volcano` (done in the drive) |

## 6. Invariants

- **S1 — Read, don't recompute.** L3 only re-shapes the skill's own output. No re-analysis.
- **S2 — Synthesized ≠ digitized.** A synthesized value is the engine's own number → it MAY feed the
  score (unlike pixel-digitized values, which never do — [[selom-extract-reproduction-bridge]]).
- **S3 — Tagged provenance.** `synthesized: True` flows to the reader (lower confidence than native)
  and the FE (labelled). Never silently passed off as a native table.
- **S4 — Don't force.** No deterministic synthesizer → `None` → L4 AI; never a fabricated/guessed
  table. (L4 never gates the score; L2/L4 two-axis honesty preserved.)
- **S5 — Additive (D7).** The figure stays a pure `{data, layout}`; the table is attached alongside,
  exactly as native-table skills do. Existing outputs unchanged when a skill already has a table.

## 7. Decisions to confirm (owner)

- **D-t1 — Synthesis (Option A) vs enrich-at-source (Option B).** *Recommended: A-first.* A =
  post-hoc `extract/synthesize.py` reading the figure (additive, no skill edits, stays in the
  reproduction lane). B = patch each `run_real.py` to attach a richer native table (the "real" fix,
  but touches the skill runners = Codex's lane, more invasive). Hybrid: synthesize broadly now,
  promote the highest-value ones (e.g. `proteomics_de`) to native over time. Confirm A-first + a
  short list of promote-to-native skills.
- **D-t2 — Score eligibility of synthesized values.** *Recommended: yes (S2), at a tagged lower
  confidence.* A synthesized read is the engine's own output, so it should be allowed to validate a
  golden — but flagged so the scorecard can show it as synthesized-derived. Confirm.
- **D-t3 — First build scope.** *Recommended:* Tier A (pca, composition, cluster, pvca, regression,
  umap_scrna, annotate, integration, trajectory) — the clean trace/string → table set that also
  unblocks the most reproduction panels. Tier B + the FE Statistics-node wiring as fast-follows.
  Confirm the starting set.
- **D-t4 — Proprietary classification + FE surfacing.** *Recommended:* register L3 as a proprietary
  module (the moat, `docs/proprietary-skills.md`), and surface synthesized tables in the FE
  Statistics node labelled "computed by Selom". Confirm whether FE wiring is in-scope now or a
  fast-follow.

## 8. Build plan (phased — each its own scoped commit, gated)

1. **Synthesis core + Tier A** — `extract/synthesize.py` with the registry + Tier-A synthesizers,
   unit-tested against the real trace/string shapes (mirroring `test_readers.py`).
2. **Reader integration** — `extract/readers.py` tries `synthesize_table` when `table is None`
   (synthesized read tagged at lower confidence); re-verify the drive on a Tier-A panel
   (e.g. composition %, pca variance) end-to-end.
3. **Tier B (clean trio)** — `corr_heatmap`, `sankey`, `upset`, each gated by a faithfulness check.
   **DONE (s44).** Read directly off well-formed traces (heatmap `z`+labels, sankey links, upset size
   bars + present dots); the gate returns `None` on a ragged/out-of-range/missing shape.
3b. **Tier B (lossy)** — `scorecard`, `boxplot`, `violin`, `heatmap`, each gated by a faithfulness
   check OR deferred to L4 where a deterministic faithful table can't be synthesized (S4). *(open)*
4. **FE Statistics-node wiring** (cross-lane) — attach synthesized tables in the run/job response so
   tableless skills show an editable table in the editor; labelled provenance.
5. **proteomics_de at source** (Codex lane) — attach a native `de_table` (the one real source fix).
