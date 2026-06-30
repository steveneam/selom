# `mixing_metrics` skill — integration benchmark metrics (LISI / kBET / ARI / NMI / silhouette)

_2026-06-30 · NEXT#1 (reproduction spine). Closes the biggest cold-drive recall miss
(`docs/records/skill-gaps.md` §Integration mixing-metrics): Selom can compute an integrated
embedding (Melody) but has **no skill to compute the graded mixing metric** from an embedding +
batch/label vector, so integration-benchmark panels route to `integration`, run, and read back
**nothing to score** (`no_golden`). This skill produces those numbers — the single lever that makes
the whole integration-benchmark paper class (Harmony/Korsunsky 2019 et al.) auto-gradable._

## Decisions

1. **Metric set (the scIB standard suite):** **iLISI** (batch mixing) · **cLISI** (label separation)
   · **kBET** (batch acceptance) · **ARI** · **NMI** (clustering vs labels) · **ASW_batch** /
   **ASW_label** (silhouette). Batch-only metrics (iLISI, kBET, ASW_batch) compute whenever a batch
   key resolves; label-dependent ones (cLISI, ARI, NMI, ASW_label) compute only when a `label_key`
   is present — otherwise reported **N/A** (degrade-clean, never error).
2. **License posture — clean-room where the lineage is copyleft** ([[license-decision-framework]],
   mirrors Melody [[selom-harmony-reimplementation]]):
   - **ARI / NMI / silhouette** → `scikit-learn` (BSD-3, already installed) directly.
   - **LISI / kBET** → **clean-room reimplemented from the published definitions** (numpy +
     `sklearn.neighbors`, BSD). The canonical impls (harmonypy `compute_lisi`; the R `kBET` package)
     are **GPL-lineage** — do not copy. Derive from the math (LISI = perplexity-calibrated inverse
     Simpson over a kNN neighbourhood; kBET = per-neighbourhood χ² of local vs global batch
     frequency). **No new dependency** (numpy / scipy / sklearn / scanpy all present in the real env).
3. **Embedding source:** read `obsm[embedding_key]`. `embedding_key=""` auto-resolves in order
   `X_pca_melody` → `X_pca_harmony` → `X_emb` → `X_pca`; if none present, compute PCA (normalize +
   log1p + PCA, like the integration engine) so the skill works standalone on raw counts.
4. **ARI/NMI clustering:** KMeans(`n_clusters = #unique labels`, `random_state=0`) on the embedding
   vs the `label_key` ground truth — deterministic + dependency-light. (scIB optimises Leiden
   resolution to match; KMeans-to-k is a defensible, reproducible proxy — flagged in the skill
   background, honest about the simplification.)
5. **Grading:** the metrics carry into the Statistics table; the tolerance grader's `MT_INTEGRATION`
   (engine-sensitive, WIDE + sign — `reproduction/core.py:442/451`) already exists. Extend
   `metric_type()` so the `mixing_metrics` skill id (and the `kbet`/`ari`/`nmi`/`asw`/`silhouette`
   metric names) route to `MT_INTEGRATION` — so a measured Melody↔Harmony delta is **not** mislabelled
   irreproducible (the [[selom-gsea-engine-sensitivity]] analogue).

## The pure metrics module — `skills/mixing_metrics/metrics.py`

Pure `numpy`/`sklearn`, **no scanpy/anndata import** → unit-testable in the fast gate without the heavy
stack. Functions take plain arrays:

- `compute_lisi(embedding, labels, perplexity=30) -> float` — mean inverse-Simpson diversity over a
  kNN neighbourhood (`3*perplexity` neighbours), with a per-cell Gaussian kernel bandwidth calibrated
  to `perplexity` by binary search on the entropy (the standard LISI calibration). Clean-room.
- `kbet_acceptance(embedding, batch, k=30, n_repeat=100, alpha=0.05) -> float` — sample cells, χ² of
  each neighbourhood's batch counts vs the global frequencies (`df = n_batch-1`); acceptance = fraction
  with `p >= alpha`. Higher = better mixing. Clean-room.
- `clustering_agreement(embedding, labels) -> (ari, nmi)` — KMeans(k=#labels) vs labels via
  `adjusted_rand_score` / `normalized_mutual_info_score`.
- `silhouette_scores(embedding, batch, labels) -> {asw_batch, asw_label}` — `ASW_label =
  (silhouette(emb,labels)+1)/2` (↑ separation); `ASW_batch = 1 - (silhouette(emb,batch)+1)/2`
  (↑ mixing). Each `None` when its label set is absent / has <2 groups.
- `compute_all(embedding, batch, labels=None, *, perplexity, k) -> list[Metric]` — orchestrates,
  returning ordered `{key, label, value, direction, note}` rows (value `None` → "N/A"). `direction` ∈
  {`↑ mixing`, `↓ better`, `↑ separation`} so the table is self-describing. Guards: <2 batches → the
  batch metrics are N/A with a one-batch note (never raises).

## skill.json (`skills/mixing_metrics/`)

- `id: mixing_metrics`, `engine: python`, `omics: scrna-seq`, `entrypoint:
  skills.mixing_metrics.run:run`, `origin: commodity` (standard benchmark metrics; the clean-room
  LISI/kBET provenance is noted in `references`/`background`, not an open-core claim).
- `inputs: [{name: matrix, kind: "anndata|10x_mtx|h5ad", required: true}]`.
- `param_spec`: `batch_key`(str="sample") · `label_key`(str="") · `embedding_key`(str="") ·
  `n_neighbors`(int=30, 5–200) · `perplexity`(int=30, 5–100) · `normalize`(bool=true) ·
  `n_pcs`(int=50, 2–200).
- `outputs: [{name: figure, kind: plotly_spec}]` (+ an attached Statistics `table`, the Pillar-1
  pattern — `contract.run_skill_with_table` pops `spec["table"]`).
- `references`: Korsunsky 2019 (LISI), Büttner 2019 (kBET) — both noted clean-room, GPL lineage not used.

## Runner — stub + real

- `run.py` — `use_real_engine("scanpy")` gate (the established pattern): stub = a dependency-free
  deterministic bar chart of plausible metric values + a matching table, so the contract/golden tests
  + light skeleton run with zero heavy deps.
- `run_real.py` — lazy scanpy: `read_anndata` → resolve embedding (obsm or compute PCA) → resolve
  batch (`_resolve_batch_key` alias logic, reused) + label → `metrics.compute_all` → a horizontal
  **bar chart** (one bar per computed metric, direction in the hover/annotation) + the Statistics
  `table` (`metric · value · direction · note`). Title names the batch + label keys. N/A metrics are
  listed in the table but omitted from the bars.

## Grader touch — `reproduction/core.py::metric_type`

Extend the existing detector (line ~468) so `s == "mixing_metrics"` OR a metric name containing
`kbet`/`ari`/`nmi`/`asw`/`silhouette`/`lisi`/`mixing` → `MT_INTEGRATION`. One-line widen; the tolerance
tuple is unchanged.

## Test plan

- **Unit** (`tests/test_mixing_metrics.py`, numpy only — no scanpy): construct (a) two **well-separated**
  batches and (b) **fully interleaved** batches in a 2-D embedding, assert iLISI(mixed) > iLISI(sep),
  kBET_accept(mixed) > kBET_accept(sep), ASW_batch(mixed) > ASW_batch(sep); construct clusters that
  **match** labels → ARI≈NMI≈1, and shuffled labels → ARI≈0; cLISI(sep-by-type) ≈ 1; one-batch input →
  batch metrics N/A, no raise; `compute_all` row shape + directions; determinism (same input → same
  values).
- **Contract** — auto via `test_input_contract`/`test_skill_table_contract`/`test_skills_golden`
  (regen the stub golden with `tests/regen_golden.py`).
- **Grader** — `metric_type("mixing_metrics", "iLISI") == MT_INTEGRATION` and for `kBET`/`ARI`/`NMI`.

## Verify (real, [[verify-on-real-data-not-mock]])

Run the **real engine** on a real multi-batch h5ad (a small RPGRIP1 / dorgau subset or a tiny
synthetic AnnData with 2 batches + a cell-type column) via a non-`:8000` uvicorn or a direct
`run_real` call: confirm the metrics table populates, iLISI rises on the Melody-corrected embedding vs
raw PCA, and label-dependent metrics appear only with a `label_key`.

## Out of scope / deferred

- Graph connectivity / kBET-graph / cell-cycle-conservation / trajectory-conservation (the rest of the
  scIB suite) — the 6 here cover the printed benchmark numbers; add others on demand.
- Leiden-resolution-optimised NMI/ARI (scIB's exact recipe) — KMeans-to-k proxy ships now; revisit if a
  paper's number only reconciles under optimised Leiden.
- Auto-routing keyword wiring beyond the grader (the paper→skill keyword index) — add when a dogfooded
  benchmark paper with attached data lands ([[selom-skill-keyword-index]]).

### Skill-combination robustness (owner-flagged 2026-06-30, do AFTER this pillar)

Surfaced reviewing how skills combine (the engine runs skills independently; `chains_with` is metadata,
the reproduction deck runs one skill per panel — there is no generic A→B data-flow chain). Two thin spots
to harden later, not now:

1. **ERG trace ↔ bar cross-skill equality test.** `erg_traces` and `erg_bwave_bar` share one measurement
   core (`skills/_erg.py::landmarks`) and each is tested against it, but no test asserts the trace-measured
   b-wave **equals** the bar-measured b-wave on the *same* file. Add that equality test to pin the
   cross-skill agreement that today rests only on the shared core.
2. **`integration` → `mixing_metrics` real chain.** `integration` returns a figure, not a persisted
   corrected h5ad, so `mixing_metrics` only sees `X_pca_melody` if the input file already carries it
   (else it computes its own PCA — not Melody-corrected). Decide whether `integration` should optionally
   persist its corrected embedding so `mixing_metrics` can score it directly as a tested chain (rather
   than the current manual / data-dependent hand-off).

## Gates

BE fast gate (`pytest -m "not slow"`, uv-3.12 PY + `PYTHONPATH=".venv/Lib/site-packages;."`
[[selom-backend-python-exec]]) + ruff. **No new dep** [[selom-uv-sync-footgun]]. Review:
**review-gauntlet** (correctness — the clean-room metric math + the license posture). Verify on real
data + the engine. Commit: named paths, no AI sign-off, owner pushes.
