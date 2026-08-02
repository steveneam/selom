# Skill coverage — how the smoke matrix is built, and what it does *not* prove

The measured answer to "are all the skills working?" lives in [`matrix.md`](matrix.md). This file is
the method behind it: what was run, on what, why those inputs, and where the evidence stops.

Built 2026-08-03 (Parallel Sprint 3, Lane C).

## Why it exists

Nothing in the repo could answer the question, so it got answered from impression. The nearest
thing — `app/backend/tests/test_skills_golden.py` — pins every skill's dependency-free **stub** to a
committed snapshot. That is a genuinely useful test (it keeps the wire shape stable with zero heavy
deps) but by construction it says *nothing* about whether the real engine runs: it sets
`SELOM_SKILLS_ENGINE=stub` on purpose. So the suite could be entirely green while every real engine
was broken.

## What the matrix is

One declared case per registered skill, run through its **real** engine against a **real** file in
`SELOM_DATASETS_DIR`, recording pass / fail / explicitly-skipped-with-a-reason plus runtime.

* Cases: `app/backend/skills/smoke.py` (`CASES`)
* Gate: `scripts/skill-smoke.sh` — exit-code gated, non-zero on regression
* Ratchet: `app/backend/tests/test_skill_smoke.py`
* Published: `matrix.md` + `matrix.json` (generated; `scripts/skill-smoke.sh --write`)

### The honesty rules

A smoke matrix that lies is worse than no matrix, so four things are shut off by construction
(`skills/smoke.py:pin_process`):

1. **No stub can score a pass.** The run forces `SELOM_SKILLS_ENGINE=real` and
   `SELOM_UMAP_ENGINE=scanpy`. Under the default `auto`, one missing dependency makes a skill return
   a *fabricated* figure instead of failing (RISKS #11) — which a naive matrix would record as a
   pass. Forced-real turns that into an honest `ImportError`. `run_matrix` additionally asserts the
   resolved engine policy is `real` and refuses to run otherwise.
2. **No cache can score a pass.** The C1 result cache and C3 input cache are disabled. A cached
   figure is returned without executing the engine at all — the second run of a broken skill would
   go green in 0.00 s.
3. **A stub that leaks through anyway is a failure.** Any figure whose title still contains
   `(stub)` fails the row.
4. **A skip must carry a reason.** A silent skip reads as a pass. `smoke.Skip` requires one, and the
   ratchet fails on a thin one.

Every case also asserts what the golden test asserts — non-empty `data`, a `layout` dict, and a
clean JSON round-trip (no numpy or Plotly typed-array leakage).

### Choosing the inputs

Smallest real file that exercises the engine honestly. Two scRNA anchors carry most of it:

| File | Shape | Why |
|---|---|---|
| `jev/retina_fadl.h5ad` | 8,699 × 18,223, **already log-normalized**, carries `leiden` + `X_umap` | the cluster-driven skills (deg / markers / violin / heatmap / trajectory …). `normalize=False` on every case — normalizing it again would be double-normalizing |
| `hani/processed/hani_irpe_subset.h5ad` | 10,000 × 64,591, **raw counts**, 4 batches | the batch-aware and QC skills (integration / mixing_metrics / normalization_qc), which need genuine counts |
| `rpgrip1/processed/rpgrip1_merged.h5ad` | 83,659 cells, 9 samples, WT/C3/PT/FS + cell types | the only corpus matrix carrying sample **and** condition **and** cell-type labels together — the one shape `diff_abundance` can be honestly asked for |
| `alpk1/irpe_rawcounts/DE_oracle_d311_limma.csv` | ~21 k **human** genes, limma DE | every gene-set skill. Selom's license-clean libraries (GO, WikiPathways, curated) are human-symbol keyed, so the mouse JEV proteome overlaps almost nothing and gseapy legitimately refuses |
| `erg-fig1e/*.csv` | rd10 AAV Fig-1E waveforms + device metrics | the ERG family, plus `boxplot` / `regression` / `pvca`, which want a real long-form table with genuine grouping factors |

**Adapters.** Two rows convert the corpus file first, and the matrix says so:

* `erg_flicker` — the only *real* flicker recording in the corpus is a Diagnosys Espion `.TXT`
  (LA 10/30 Hz steps). It is read through `skills._celeris`, exactly as `engine.ingest` does for
  that format, into the canonical `erg_waveforms_long` CSV the skill takes.
* `upset` — `hani/mmc2_markers_long.csv` is pivoted from long `(gene, cell_type)` to the wide
  boolean membership matrix the engine documents as its input ("top markers per cell type").

## What the run found

Three things that were not visible before, all now fixed or recorded:

1. **`pathway` was dead in production.** Every live Reactome call returned `403 Forbidden`:
   Reactome sits behind CloudFront, which rejects urllib's default `Python-urllib/3.x`
   User-Agent. The skill has no network fallback by design, so it raised on every run. Fixed by
   sending a browser-like UA — the same thing `app/backend/scripts/build_gene_sets.py` already does
   for its GO downloads. Nothing tested it because the only coverage was the stub.
2. **`go_graph` cannot run from a clean checkout.** Its real engine loads
   `skills/go_graph/go_dag.json`, which is **gitignored** — a ~7 MB build artefact. Absent, the
   engine raises `FileNotFoundError`; it does not degrade to the stub (the module docstring's claim
   that it does is stale — the stub is only reachable through `SELOM_SKILLS_ENGINE`). The same
   applies to `enrichment`'s preferred `gene_sets_go.json`, which *does* fall back to a small
   committed sample. Staged copies live in the corpus at `$SELOM_DATASETS_DIR/genesets/`;
   `scripts/skill-smoke.sh --install-artifacts` installs them, and the matrix records the row as
   *not run* rather than passing when they are missing.
3. **`umap_scrna` is not stub-only.** It was believed to be the last skill without a real engine
   because it ships no `run_real.py`. Its real engine is `run_scanpy.py`, selected behind the same
   entrypoint by `SELOM_UMAP_ENGINE` (default `auto` → real whenever scanpy imports, which it does).
   The full pipeline — filter → PCA → kNN → Leiden → UMAP — runs on the real matrix in ~11 s. The
   reason it *looks* stub-only is that it is the one skill excluded from `test_skills_golden.py`:
   its engine selector is not `SELOM_SKILLS_ENGINE`, so pinning that to `stub` would not make its
   golden deterministic.

## What this does NOT prove

Worth stating plainly, because a green matrix invites over-reading:

* **Not numerical correctness.** A row passing means the real engine consumed real data and returned
  a well-formed editable figure. It does not mean the numbers are right — that is the reproduction
  engine's job (`docs/reproduction-engine/`, the R oracle, the paper ledgers).
* **Not the full parameter space.** One case per skill: one dataset, one parameter set. A skill can
  pass here and still break on another mode (`deg` alone has scRNA, bulk, pseudobulk and
  time-course paths; only the scRNA one is smoked).
* **Not CI-enforced.** CI runs `pytest -m "not slow"` with no `SELOM_DATASETS_DIR`, so the live
  matrix never runs there. What CI *does* enforce is the structural half of the ratchet: every
  registered skill has a case, skips carry reasons, the committed matrix matches the live roster,
  and every real-engine module imports. The live gate is `scripts/skill-smoke.sh`, run at a
  milestone or before a release.
* **Two rows depend on the network** (`pathway` → Reactome, `string_network` → STRING). Offline they
  fail rather than fabricating, which is the correct behaviour but does make those rows
  environment-dependent.
* **Runtimes are indicative, not benchmarks.** They were measured on a 6-vCPU box running three
  build lanes at once.

## Re-running it

```bash
export SELOM_DATASETS_DIR=/path/to/selom-data
scripts/skill-smoke.sh --install-artifacts   # once per checkout: the gitignored GO build outputs
scripts/skill-smoke.sh                       # ~4 min; non-zero exit on regression
scripts/skill-smoke.sh --write               # regenerate matrix.md + matrix.json after a change
```
