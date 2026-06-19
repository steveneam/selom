# Spec — Selom Integrate (clean-room in-house Harmony)

> Status: **APPROVED → BUILT → VALIDATED** (session 29, 2026-06-19). Shipped as
> `skills/integration/melody.py` (engine `melody()`); the `integration` skill is flipped to
> `origin: "proprietary"`, branded **"Selom Melody"**, with `harmonypy` removed from the
> shipped path. Owner renamed the engine Harmony→**Melody** so our clean-room code is never
> confused with the GPL packages. Validated by the batch-mixing METRIC vs. the harmonypy
> oracle on real GSE201356 — results at the foot of this doc.
> Author: Claude (acting FE+BE), session 29, 2026-06-19.
> Supersedes the recommendation in `docs/harmony-reimplementation-scope.md` (extends it; the
> scope's "0.0.10 is MIT" premise is **corrected** below).

## What

Replace the third-party `harmonypy` dependency on the `integration` skill's shipped path with
a **clean-room, pure-numpy reimplementation of the 2019 Harmony algorithm** (Korsunsky et al.,
*Nature Methods* 16:1289–1296), built **from the published paper only** (not from harmonypy's
source). The new engine — **"Selom Integrate"** — is a deterministic, dependency-light
(`numpy`/`scipy`/`scikit-learn`) module the `integration` skill calls instead of
`scanpy.external.pp.harmony_integrate`. The skill's public contract (id, params, `{data,layout}`
output, batch-mixing diagnostic) is unchanged, so the swap is drop-in. `harmonypy 0.0.10` stays
installed as a **validation oracle only** and leaves the shipped path entirely.

## Context

### Why now — two reasons, one of them new this session

1. **License (the new, decisive finding).** The whole Harmony lineage is **GPL-3.0**, not MIT.
   Verified at the source this session:
   - The installed `harmonypy-0.0.10.dist-info/METADATA` classifier = `GNU General Public
     License v3 or later (GPLv3+)`; the bundled `LICENSE` file is GPLv3.
   - `harmonypy 2.0.0` (Apr 2026, C++/Armadillo) is GPL-3.0 with `license_expression =
     GPL-3.0-or-later`.
   - The upstream R `harmony`/`harmony2` lineage is GPL-3 throughout.

   The scope doc, this session's memory, CURRENT.md (s23), and `integration/skill.json`
   (`"license": "MIT"`) all recorded "0.0.10 MIT/slowkow." **That was wrong** — exactly the
   license-drift trap the project's own `license-decision-framework` rule warns about ("verify
   the LICENSE at decision time, not from memory"). Consequence: **we are currently shipping
   GPL-3.0 code on the `integration` path.** For a *pure web SaaS* this is tolerable today (GPL,
   unlike AGPL, is not triggered by server-side use — no "conveying"), but it is a copyleft
   dependency that blocks any future on-prem / desktop / Docker-to-customer distribution and is
   not the clean base we assumed. Removing it is now a license-hygiene win, not just hardening.

2. **Fragility (the original reason).** `harmonypy 0.0.10` is unmaintained pure Python; `2.0.0`
   is a C++/CMake/Armadillo rewrite that **does not build here** (`CMAKE_CXX_COMPILER not set`).
   A stray `uv sync` re-resolves to the unbuildable 2.0.0 (hit live in s28; pinned `harmonypy<1`
   to recover). A pure-numpy reimplementation removes the pin and the build risk permanently.

**Owner decision (this session):** clean-room the proven **2019 algorithm from the paper**
(not Harmony2's 2026 C++/GPL update — its headline win is >100M-cell scale, irrelevant to
Selom's workloads). Do **not** reverse-engineer either GPL codebase; build from the published
math. This is the same clean-room move as `cepo` and the in-house GSEA/ORA.

### What exists today

- **`app/backend/skills/integration/`** — the skill (shipped s23, `c6e4860`):
  - `skill.json` — params `batch_key`, `n_neighbors`, `n_pcs`, `n_hvg`, `color_by`, `normalize`,
    `theta` (default 2.0), `max_iter_harmony` (default 10); `catalog.name "Selom Integration
    (Harmony)"`; `"license": "MIT"` (**wrong, fix**); `origin` absent (defaults `commodity`).
  - `run.py` — dispatch: `use_real_engine("scanpy", "harmonypy")` → `run_real`, else `_stub_figure()`.
  - `run_real.py` — pipeline: read → `filter_genes` → (normalize→log1p) → optional HVG → PCA →
    **`sc.external.pp.harmony_integrate(adata, batch_key, theta, max_iter_harmony)`** writing
    `X_pca_harmony` → `_batch_mixing` before/after kNN-entropy diagnostic → neighbours/Leiden/UMAP
    on the corrected rep → `px.scatter` → `jsonable({data,layout})`. Includes the str-cast batch
    fix and the single-batch fallback.
- **`skills/proprietary/cepo/`** — the clean-room template: `origin: "proprietary"`,
  `catalog.name "Selom Cepo"`, pure-function core (`cepo_ds(X, labels, genes)`) + thin skill
  wrapper (`run_real.run`) + stub; validated on synthetic ground truth in CI and against a real
  oracle (Hani `mmc2`) in the dogfood. `docs/proprietary-skills.md` + `skills/proprietary/README.md`
  define the `origin` flag, the `catalog.name` branding, and the loader's dual scan.
- **`skills/_engine.py`** — `use_real_engine(*modules)`: `real`/`scanpy` force real; `auto`
  uses real iff every named module is importable; `stub` forces stub.
- **`tests/test_integration_skill.py`** — live skipif test (real GSE201356, asserts 4 traces,
  "Harmony" in title). **`tests/test_cepo.py`** — the pure-core + entrypoint test pattern to mirror.
- **`D:\selom-data\hani\processed\hani_irpe_subset.h5ad`** — the real 4-library oracle dataset
  (`batch_key="sample"`); the s23/s25 result is mixing kNN-entropy **0.49 → 0.83** / iLISI
  **2.10 → 3.18**.

### The algorithm (captured from the paper this session)

Source: `Fast sensitive and accurate integration of single cell data with Harmony.pdf`
(Online Methods §1–§3, Algorithms 1–3), supplied by the owner; extracted with our own pypdf/
PDFium `papers.extract_text`. Notation: `Z ∈ ℝ^{d×N}` original PCA embedding (d PCs, N cells),
`ϕ ∈ {0,1}^{B×N}` one-hot batch design (B batches), `R ∈ [0,1]^{K×N}` soft cluster assignment
(columns sum to 1, K clusters), `Y ∈ ℝ^{d×K}` cluster centroids.

**Algorithm 1 — HARMONIZE(Z, ϕ):** keep `Z` fixed; `Z̄ ← Z`; repeat `R ← CLUSTER(Z̄, ϕ)` then
`Z̄ ← CORRECT(Z, R, ϕ)` until the objective converges (≤ `max_iter_harmony`, default 10).
**Correction always regresses the *original* Z** under the current R (not the running Z̄) — a
deliberate choice to limit transformation and avoid over-correction (Methods §1.1).

**Algorithm 2 — CLUSTER (maximum-diversity soft k-means), cosine/spherical:**
- Init centroids `Y ← KMeans(Z̄, K)` (10 restarts, keep best), then **L2-normalize** each centroid
  column and each `Z̄` column (so squared-Euclidean ≡ cosine).
- `O ← R ϕᵀ` (K×B observed co-occurrence: `O_{kb}=Σ_i R_{ki}·1[i∈b]`),
  `E_{kb} ← (N_b/N)·Σ_i R_{ki}` (expected under independence; eq 6).
- Repeat to convergence (≤ `max_iter_cluster`): for each **update block** (a partition of cells,
  block_size = 5%): remove the block's mass from `O,E`; update the block's columns
  `R_{ki} ∝ exp(−2(1 − Y_kᵀ Z̄_i)/σ) · ∏_batch-vars ((1+E_{k,b(i)})/(1+O_{k,b(i)}))^{θ_b}`
  (derivation eq 8, with the `+1` smoothing of §2.6.3); renormalize each cell's column to sum 1;
  add the block's new mass back to `O,E`. Then recompute centroids `Y ← Z̄ Rᵀ` and L2-normalize.
- The diversity factor uses `(1+E)/(1+O)` (note the **E/O** orientation from the eq-8 derivation,
  with `+1` smoothing so an empty (cluster,batch) cell can't send the penalty to ∞).

**Algorithm 3 — CORRECT (mixture-of-experts ridge):** `Z̄ ← Z`; `ϕ* ← [1; ϕ]` ((B+1)×N, intercept
row prepended). For each cluster k: `W_k = (ϕ* diag(R_k) ϕ*ᵀ + λI)^{-1} ϕ* diag(R_k) Zᵀ`
((B+1)×d ridge fit, **`λ` penalizes batch rows only — intercept penalty λ₀ = 0**); zero the
intercept row `W_k[0,:] ← 0`; subtract `Z̄ ← Z̄ − W_kᵀ ϕ* diag(R_k)`. Returns the **unnormalized**
corrected embedding (correction happens in the unnormalized space; the next CLUSTER call
re-normalizes — Methods §3.4).

**θ-discounting (eq, §2.6.4):** `θ_b = θ_max · [1 − exp(−N_b/(Kτ))]²` down-weights small batches;
`τ` = "min cells per cluster per batch" (paper uses 5–20). **Default τ = 0 = off** (matches the
oracle's effective behavior; on by setting τ).

**Defaults (paper + standard Harmony):** `σ`(sigma)=0.1, `λ`(lambda)=1, `θ`(theta)=2 (user param),
`K`=min(100, ⌊N/30⌋) (Methods §2.6.5), block_size=0.05, KMeans restarts=10, τ=0,
max_iter_harmony=10 (user param), max_iter_cluster=20, ε_cluster=1e-5, ε_harmony=1e-4.

## Requirements

1. A pure-Python (`numpy`/`scipy`/`scikit-learn` only — no C/C++/CMake, no `harmonypy`,
   no `scanpy` import) function `harmonize(Z, batch, *, theta, ...) -> Z_corrected` implementing
   Algorithms 1–3 above, returning a corrected embedding of the **same shape** as `Z`.
2. **Deterministic**: identical output for identical input + `random_state` (seeded KMeans init
   and seeded block partition; no reliance on global RNG).
3. **Drop-in for the skill**: `integration/run_real.py` calls `harmonize` to produce
   `X_pca_harmony`; the skill's `skill.json` params, `{data,layout}` output shape, single-batch
   fallback, str-cast batch fix, and the `_batch_mixing` before/after diagnostic are unchanged.
4. **harmonypy off the shipped path**: the `run.py` real-engine gate no longer requires
   `harmonypy`; the real branch needs only `scanpy` (for the surrounding PCA/neighbors/Leiden/UMAP).
   `harmonypy` is imported **only** by the oracle validation test.
5. **Multi-batch + edge cases**: ≥2 batches supported; single-batch is a no-op handled by the
   skill's existing fallback (engine still must not crash if called with one batch — returns `Z`
   unchanged); tiny-N guard (K clamped to ≥1 and ≤ N; degenerate clusters tolerated via the
   `+1` smoothing).
6. **Trust-as-output**: the engine exposes the per-iteration objective trace (for convergence/
   provenance); the skill keeps emitting the before→after batch-mixing number in the subtitle.
7. **Validation by metric, not pixels**: accept when batch mixing on real GSE201356 is
   **equivalent to the harmonypy oracle** (kNN-entropy reaching ≈0.83 / iLISI ≈3.18 from ≈0.49 /
   2.10) **without over-correcting** (rod-dominant clusters preserved; mixing rise is real, not
   a collapse). A deterministic synthetic 2-batch unit test must pass (known shift → corrected
   batch centroids coincide while cell-type separation is preserved).
8. **Proprietary marking**: `integration` becomes `origin: "proprietary"`, `catalog.name
   "Selom Integrate"`, `license` corrected from `"MIT"`; classification doc + proprietary README
   updated.

## Design

### Module placement (recommended)

Add **`app/backend/skills/integration/harmony.py`** — the pure-numpy engine, co-located with the
only skill that uses it. Keep the `integration` skill where it is (flat dir, stable id/entrypoint/
golden) and **flip it to proprietary via the `origin` flag** — exactly the pattern
`skills/proprietary/README.md` prescribes for "already-shipped skills that stay flat to preserve
entrypoints + goldens, marked by the flag." The IP is the algorithm module; the flag + branded
`catalog.name` mark the skill.

> Alternative considered: a shared `skills/_harmony.py` (sibling of `_scrna.py`/`_genes.py`) or a
> new `skills/proprietary/integrate/` skill. Rejected for v1: only `integration` uses Harmony, so
> a shared module is premature; a new proprietary skill would duplicate the existing `integration`
> id/golden. If a second consumer appears later, promote `harmony.py` to `skills/_harmony.py` then
> (cheap move). **Decision is reversible.**

### Engine interface (`harmony.py`)

```python
def harmonize(
    Z,                      # (N, d) float ndarray — PCA embedding (cells × PCs), as scanpy stores obsm["X_pca"]
    batch,                  # (N,) array-like of batch labels (str/categorical)
    *,
    theta: float = 2.0,
    max_iter_harmony: int = 10,
    max_iter_cluster: int = 20,
    nclust: int | None = None,   # None → min(100, N // 30), floored at 1
    sigma: float = 0.1,
    lamb: float = 1.0,           # ridge penalty on batch rows (λ); intercept unpenalized
    tau: float = 0.0,            # θ-discounting; 0 = off
    block_size: float = 0.05,
    epsilon_cluster: float = 1e-5,
    epsilon_harmony: float = 1e-4,
    random_state: int = 0,
) -> np.ndarray:             # (N, d) corrected embedding, same orientation as input
    ...
```

Internals work in the paper's `d×N` orientation; the public function accepts/returns scanpy's
`N×d` (`obsm`) orientation and transposes internally. Helpers (module-private): `_one_hot(batch)`,
`_init_R(Z_cos, Y, sigma)`, `_cluster(...)` (Algorithm 2), `_correct(Z, R, phi, lamb)`
(Algorithm 3), `_objective(...)` (eq 4 for convergence). Single batch → return `Z` unchanged.

### Skill wiring (`integration/run_real.py`)

Replace the `sc.external.pp.harmony_integrate(...)` block with:

```python
from skills.integration.harmony import harmonize
adata.obsm["X_pca_harmony"] = harmonize(
    adata.obsm["X_pca"],
    adata.obs[batch_key].to_numpy(),
    theta=float(params.get("theta", 2.0)),
    max_iter_harmony=int(params.get("max_iter_harmony", 10)),
)
```

Everything around it (HVG, PCA, the str-cast, `_batch_mixing` before/after, neighbors on
`X_pca_harmony`, Leiden, UMAP, colour-by, `jsonable`) is **unchanged**. The str-cast can stay
(harmless) or be dropped (our `_one_hot` won't have pandas-3's nullable-boolean problem); keep it
for safety. `run.py` gate: `use_real_engine("scanpy")` (drop `"harmonypy"`).

### Data flow (unchanged externally)

`POST /skills/integration/run` (multipart matrix + params) → `run.py` → `run_real.py` →
`harmonize()` → `X_pca_harmony` → neighbors/Leiden/UMAP → editable Plotly `{data,layout}` (+
mixing subtitle) → FE editor. Same wire format as `umap_scrna`.

## Decisions

1. **Target the 2019 algorithm, build from the paper, pure numpy.** (Owner-decided this session.)
   Alternatives: RE harmonypy 2.0.0 C++ (GPL-taint + build fragility + irrelevant scale);
   keep GPL 0.0.10 (fragile + copyleft). **Not reversible casually** — it's the whole premise.
2. **Co-locate the engine in `skills/integration/harmony.py`; flip the existing skill to
   proprietary.** Alternatives above. **Reversible** (promote to `_harmony.py` later).
3. **Faithful block updates (block_size=0.05), seeded partition.** Alternative: a single
   full-batch R update per cluster iteration (simpler, but converges differently from the oracle).
   Chosen because faithful blocks track the paper + oracle behavior and the cost at our scale
   (~10k cells) is negligible. **Reversible** (engine-internal; metric-gated).
4. **Defaults match the oracle** (sigma=0.1, lambda=1, theta=2, K=min(100,N/30), tau=0,
   block=0.05, max_iter_cluster=20, ε_cluster=1e-5, ε_harmony=1e-4) so the metric comparison is
   apples-to-apples. These are paper-stated or universally-documented Harmony defaults (facts,
   not GPL expression). **Reversible** (tunable params).
5. **Correct the original Z each iteration (not cumulative).** Per Methods §1.1 — prevents
   over-correction. **Not reversible** (it's the algorithm).
6. **harmonypy stays installed, pinned `<1`, as oracle only.** Removed from the runtime gate and
   never imported by shipped code. **Reversible.**
7. `Assumption:` numeric ε / max_iter_cluster (not printed in the Online Methods) use the
   standard Harmony values; final values are confirmed during Phase-4 metric tuning, not by
   reading GPL source.

## Versions

- Runtime deps (all already in the hand-sewn venv): `numpy` (2.x), `scipy==1.17.1`,
  `scikit-learn` (KMeans init), `scanpy==1.12.1` (surrounding pipeline only). **No new deps.**
- `harmonypy==0.0.10` (pinned `>=0.0.10,<1`) — oracle only, test-time import.
- Python `3.12` (uv-managed). Env per `selom-uv-sync-footgun`: add nothing via `uv sync --extra`;
  no installs needed for this build.

## Invariants

- **No `harmonypy`/`scanpy.external` import on the shipped path** — grep the skill + engine for
  `harmonypy` / `harmony_integrate` returns nothing outside tests.
- **`integration` public contract stable**: skill id, param names/defaults, `{data,layout}` shape,
  trace-per-batch, single-batch fallback title, mixing subtitle — all unchanged; the existing
  golden (`test_skills_golden`) and the live test (`test_integration_skill`) still pass.
- **Determinism**: `harmonize(...)` with fixed `random_state` is bit-stable across runs.
- **Mixing rises, structure preserved**: after-mixing > before-mixing on real GSE201356, and
  per-cluster max single-sample share does not collapse (no over-integration).

## Error Behavior

- `< 2` batches → return `Z` unchanged (no-op); skill's fallback labels the figure "single batch".
- `N < nclust` or tiny N → clamp `K = max(1, min(nclust, N))`; `+1` smoothing keeps empty
  (cluster,batch) cells finite; never raises on degenerate clusters.
- Non-finite `Z` (NaN/inf) → raise `ValueError` early (don't silently emit garbage).
- KMeans non-convergence is tolerated (init only); the outer loop is metric-gated, not assertion-gated.

## Testing Strategy

Mirror the Cepo pattern (`tests/test_cepo.py`): pure-core synthetic tests in CI + a real-oracle
dogfood reported in the handoff.

1. **`tests/test_harmony.py` (new, CI, no heavy deps):**
   - *Synthetic 2-batch recovery*: two batches, same 3 cell-type centroids + a known additive
     batch shift. Assert after `harmonize`: (a) per-cell-type **batch centroids coincide** (shift
     removed, within tol), (b) **cell-type separation preserved** (between-type distance ≫
     within-type), (c) a batch-mixing metric rises vs. raw.
   - *Determinism*: two calls with the same `random_state` are `allclose`.
   - *Single-batch no-op*: one batch → output `== Z`.
   - *Shape/orientation*: `(N,d)` in → `(N,d)` out; tiny-N (e.g. N=20) doesn't crash.
2. **`tests/test_integration_skill.py` (extend):** the existing live skipif test must still pass
   **without harmonypy installed** (gate now needs only scanpy). Optionally drop the
   `harmonypy` find_spec from its skip condition.
3. **Oracle validation (Phase-4 dogfood, not CI):** run BOTH engines on real GSE201356
   (`hani_irpe_subset.h5ad`, `batch_key="sample"`): harmonypy 0.0.10 (oracle) vs. `harmonize`.
   Compare the kNN-entropy / iLISI before→after and per-cluster batch composition. **Accept** when
   ours reaches equivalent mixing (≈0.49→≈0.83 / 2.10→≈3.18) without over-correcting. Report the
   two numbers in CURRENT.md (trust-as-output). Use the gated R/`harmonypy` oracle discipline
   (validation-only, never shipped) per `selom-r-validation-oracle`.
4. **Full suite**: `pytest` BE green (baseline 471) + `ruff` clean.

## Out of Scope

- Harmony2 (2026) scale/anti-over-integration features — possible later fast-follow from the
  preprint; not v1.
- Reference mapping (Methods §3.3), `>1` batch *variable* / covariate adjustment, GPU/mini-batch
  scaling — the engine should not preclude them, but they are not built now.
- FE changes — none; the output contract is unchanged.
- `uv.lock` regeneration / folding the `harmonypy<1` pin into `pyproject` — separate deferred chore.
- Removing `harmonypy` from the venv — it stays as the oracle.

---

Phase plan after approval: **(3)** build `melody.py` + synthetic tests → wire the skill + flip
the gate/flag → **(4)** validate by metric vs the harmonypy oracle on real GSE201356, tune to
equivalence, report the before→after numbers. Per-lane scoped commits (code vs docs separate);
ASK before any push.

## Validation result (Phase 4 — PASSED)

Identical preprocessing + PCA on real **GSE201356** (`hani_irpe_subset.h5ad`, 10,000 cells,
21,516 genes, 50 PCs, 4 libraries, `batch_key="sample"`), then harmonypy 0.0.10 (oracle) vs.
Selom Melody on the same `X_pca`. Melody **matches the oracle on every axis**:

| metric | raw PCA | harmonypy (oracle) | Selom Melody |
|---|---|---|---|
| batch mixing — kNN entropy (↑) | 0.489 | 0.825 | **0.826** |
| batch mixing — iLISI (↑) | 2.168 | 3.188 | **3.192** |
| structure ratio over KMeans-10 bio groups (↑) | 12.180 | 12.417 | **12.412** |
| cLISI — cell-type purity (↓) | 1.207 | 1.349 | **1.351** |

Equivalent batch mixing **and** equivalent structure preservation (mixing equals — not
exceeds — the oracle, so no over-correction). Reproduces the s23/s25 result (0.49→0.83 /
2.10→3.18). Plus a deterministic synthetic 2-batch unit test (`tests/test_melody.py`, 9 tests):
a known additive batch shift is removed (per-type batch gap 9.16→0.57) while cell-type
separation is preserved/sharpened (6.38→14.74). **pytest BE 480 green (471 + 9); ruff clean.**
harmonypy stays installed (pinned `<1`) as the validation oracle only.
