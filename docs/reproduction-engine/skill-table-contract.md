# Skill table-contract uniformity audit (P4-4a)

> Built s56 (2026-06-22) by classifying **every** shipped skill against reality (run the stub +
> grep each runner for `spec["table"]`), not from memory. Enforced by
> `app/backend/tests/test_skill_table_contract.py` — this doc is the human-readable ledger; that test
> is the guard that keeps it true. Companion: `skill-table-schemas.md` (the column-level reference for
> *where inside the output* each metric lives); this doc answers the prior question — *does every
> in-scope skill have a table source at all?*

## Why this exists

Pillar P4's contract is that every in-scope skill emits `{figure, table}`, so the reproduction
reader (and the own-data Statistics node) always has a table to read a golden back from. The risk
this audit closes is a **silently tableless skill in a graded path**: a skill that drives during
reproduction but produces no table and has no synthesizer, so its golden can never be read — it
quietly classifies `needs_recipe` forever and nobody notices the *contract* gap (vs. a real
data/recall gap). The guard test makes that impossible to introduce unnoticed: a new skill with no
declared table source fails CI until it is classified.

## The three table sources (the partition)

Every skill's Statistics table comes from exactly one of three layers
([[layered-deterministic-extraction]]):

- **native** — the runner attaches its own `spec["table"]` (popped by `run_skill_with_table`). The
  stub (`run.py`) and/or the heavy `run_real.py`; `gsea`/`ssgsea` attach it *conditionally* on real
  data (the stub shows none), `diff_abundance`/`markers`/`normalization_qc`/`pseudotime_genes` attach
  it **only** in `run_real.py`. The *source* is the truth, not the stub output.
- **L3** — no native table, but `extract.synthesize.synthesize_table` re-shapes the skill's own
  figure into a canonical table (read, never recompute; tagged `synthesized: True`). This set is
  **exactly** `extract/synthesize.py::_SYNTHESIZERS` — the code is the registry, the test asserts it.
- **L4-only** — node-link / un-tabulatable skills whose numbers are edges, not a stats table. No
  native table, no synthesizer; their table is the deferred **L4 Pro-AI** tier. A reviewed, honest
  gap — not a surprise.

## The ledger (30 skills)

### native — attaches its own `spec["table"]` (11)

| skill | attach site | note |
|---|---|---|
| `volcano` | `run.py` + `run_real.py` | always; the clean DE-count source |
| `deg` | `run.py` + `run_real.py` | always (no padj/direction — not a DE-count source) |
| `proteomics_de` | `run.py` + `run_real.py` | native `de_table` added s46 (was the last at-source gap) |
| `enrichment` | `run.py` | always (combined + split branches) |
| `cepo` (proprietary) | `run.py` + `run_real.py` | both stub + real emit it |
| `gsea` | `run.py` (cond.) + `run_real.py` | conditional on `lib_mode`; stub default → none |
| `ssgsea` | `run.py` (cond.) + `run_real.py` | conditional; stub default → none |
| `diff_abundance` | `run_real.py` only | stub emits none |
| `markers` | `run_real.py` only | only when `rank_by ∈ {cohens_d, auc}` |
| `normalization_qc` | `run_real.py` only | only when `filter` and/or `doublets` |
| `pseudotime_genes` | `run_real.py` only | stub emits none |
| `boxplot` | `run.py` (cond.) | conditional on `pairs=`; also L3 — see below |
| `violin` | `run.py` (cond.) | conditional on `pairs=`; also L3 — see below |

Column-level detail (exact columns, caps, golden metrics readable) is in `skill-table-schemas.md`.

### The one declared native ∩ L3 overlap — `boxplot` · `violin`

A skill normally declares **one** table source, and the guard's disjointness assertions force that
decision. These two are a reviewed exception (`NATIVE_L3_BOTH` in the guard), and the runtime
already models it: `_run.py` attaches the native table and falls back to L3 **only** `if table is
None`.

Both gained `pairs=` (the shared significance engine, `skills/_stats.py`). A pairwise p-value exists
nowhere in the figure except as a star, so when `pairs=` is set the native table carries the numbers
behind those stars — they are **irrecoverable** by synthesis, and stars without their p-values are a
claim the figure cannot back. With no `pairs=` there is no native table and L3 synthesizes what the
figure *does* encode: `boxplot`'s five-number summary (readable straight off the drawn box) and
`violin`'s PubMed marker call.

So the two sources cover disjoint **runs**, not disjoint **skills** — the distinction the original
three-way partition could not express. The completeness guard is unchanged, so nothing can become
silently tableless, and `test_native_l3_overlap_really_is_conditional` makes each entry prove it
behaves this way (no native table on a default run, a native table once `pairs=` is set, and a
working synthesizer either way) rather than letting the set become a place to park a
double-classified skill.

### L3 — synthesized from the figure (16, == `_SYNTHESIZERS`)

`pca` · `composition` · `cluster` · `umap_scrna` · `annotate` · `pvca` · `regression` ·
`integration` · `trajectory` · `corr_heatmap` · `sankey` · `upset` · `boxplot` · `heatmap` ·
`scorecard` · `violin`

Each behind a faithfulness gate (a non-conforming figure → `None` → L4; never a fabricated table).
Spec + per-skill shapes: `docs/records/table-synthesis/spec.md`. Note these synthesizers yield a table only
when the figure has the expected shape — e.g. `violin` tabulates only its PubMed marker-call
annotation, `integration` only when the title carries the batch-mixing delta — by design (S4: don't
force). That is a *figure-shape* condition, not a missing contract; the skill still **has** an L3
source.

### L4-only — no faithful table, deferred to the L4 Pro-AI tier (3)

`go_graph` · `pathway` · `string_network` — node-link network figures; their quantitative content is
the graph (nodes/edges), which has no canonical Statistics table. The reviewed allowlist in the guard
test; a panel of one of these with a printed golden classifies honestly `needs_recipe` (0 Selom
defects) until the L4 AI tier ships.

## The guard (`tests/test_skill_table_contract.py`)

- **`test_table_contract_partitions_every_skill`** — the core guard: `native ∪ L3 ∪ L4-only` equals
  every skill `list_skill_ids()` returns, the three sets pairwise disjoint. A new tableless skill
  with no synthesizer that isn't a reviewed L4-only entry lands in none of them and fails here.
- **`test_native_classification_matches_source`** — `NATIVE` equals exactly the skills whose runner
  source attaches `spec["table"]`, so the `native` list above cannot silently drift from the code.
- **`test_stub_native_skill_yields_a_table`** — the stub-visible native skills really emit a
  non-empty table from the stub (the others attach in `run_real`/conditionally, covered by source).
- **`test_l4_only_is_honestly_tableless`** — each L4-only skill has no synthesizer, attaches no
  native table, and yields no table at runtime — the allowlist can't hide a skill that should be
  native/L3.

## How to extend (adding a skill)

1. If the skill computes a tabular result → attach `spec["table"]` in its runner (it becomes
   `native`; add it to `NATIVE` in the guard test and to the ledger above).
2. Else if its figure faithfully encodes the numbers → add a synthesizer to `_SYNTHESIZERS`
   (it becomes `L3` automatically; no test edit needed beyond the partition staying complete).
3. Else if it is genuinely un-tabulatable (node-link) → add it to `L4_ONLY` in the guard test.
4. Run `tests/test_skill_table_contract.py` — the partition test fails until the skill is classified.
