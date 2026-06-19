# Scope — clean-room in-house Harmony ("Selom Integrate")

> Owner-requested scope (session 28, 2026-06-19): reverse-engineer + build our own, better
> version of `harmonypy` — the same clean-room move as Cepo and the in-house GSEA/ORA. **Scope
> only; not built this session.** Recommendation: **YES, worth it** — the strategic case (a
> proprietary moat skill) and the practical case (the dependency is fragile — we hit it live
> this session) both hold.

## Why now — the dependency is genuinely fragile

The `integration` skill (Harmony batch correction, shipped s23, `c6e4860`) runs on `harmonypy`,
which is a footgun:

- **`harmonypy 0.0.10`** (slowkow, MIT) is the working version — pure Python, but **unmaintained**.
- **`harmonypy 2.0.0`** is a C++/CMake rewrite that **fails to build in our environment**
  (`CMAKE_CXX_COMPILER not set`) — confirmed live this session when a re-resolve bumped it. We
  had to pin `==0.0.10` to recover. Any unpinned `uv sync` re-introduces the break.

So the shipped path depends on an unmaintained pin whose only forward version doesn't build for
us. A pure-numpy reimplementation removes that risk entirely. This is the same logic that drove
Cepo and the in-house ORA: own the cross-cutting algorithm, don't rent a brittle one.

## The algorithm (Korsunsky et al., Nat. Methods 2019)

Harmony iterates two steps over the PCA embedding `Z` (d PCs × N cells) until the objective
converges (default ≤ ~10 outer iterations):

1. **Maximum-diversity soft clustering** — a modified soft k-means on the L2-normalized
   (cosine) embedding into K clusters (soft assignment `R`, K × N, columns sum to 1):
   - within-cluster distance `+ σ·entropy(R)` (σ = cluster fuzziness)
   - `− θ·diversity` penalty: per cluster k and batch b, penalize observed batch fraction
     `O_kb` deviating from expected `E_kb` (= cluster mass × batch's global share). The
     `R` update reweights by `∏_b (E_kb / O_kb)^(θ·φ_b)`, pushing every cluster toward a
     batch-balanced mix.
2. **Mixture-of-experts linear correction** — for each cluster, a ridge regression (penalty λ)
   of `Z` on the one-hot batch design weighted by `R_k`; subtract only the batch coefficients
   (keep the intercept), soft-weighted by `R`. Yields the corrected embedding `Z_hat`.

Hyperparameters map 1:1 to what the `integration` skill already exposes: `theta` (diversity),
`n_pcs`, `n_neighbors`, `max_iter_harmony` (+ internal `sigma≈0.1`, `lambda≈1`, K≈min(100, N/30),
`max_iter_cluster`). A drop-in replacement keeps the skill's params and the `{data,layout}`
contract unchanged.

## "Better than harmonypy" — the concrete wins

- **Pure numpy/scipy + sklearn KMeans init** → no C++/CMake, deterministic with a seed, portable
  (fixes the 2.0.0 build problem permanently).
- **Trust-as-output**: emit the per-iteration objective + the **batch-mixing entropy / iLISI
  before→after** (we already built that diagnostic for `integration`, s25 G) as provenance — fits
  the reproducibility-score ethos (the integration result carries its own quality number).
- **Robustness**: explicit single-batch no-op, tiny-N guards, >2-batch support, no global RNG
  surprises.
- **Speed (optional)**: vectorized `R` updates; mini-batch KMeans for large N.
- **Proprietary IP** (DECISIONS #8): joins Cepo + in-house GSEA in `skills/proprietary/`; the
  moat is the cross-cutting, validated, reproducible integration layer — not one function.

## License posture

The **algorithm is published** (Korsunsky 2019 — cite it). `harmonypy` itself is MIT, so even
direct use is license-clean; the reason to reimplement is *fragility + control + moat*, not a
license gate. Keep `harmonypy 0.0.10` installed **as a validation oracle only** (the edgeR/fgsea/
mmc2 pattern), never on the shipped path once ours validates.

## Validation plan (the make-or-break)

Harmony is stochastic (KMeans init), so do **not** target a byte-identical embedding — that's the
GSEA-engine-delta lesson ([[selom-gsea-engine-sensitivity]]): **validate by the mixing METRIC, not
pixel match.** Oracle = `harmonypy 0.0.10` on the real **GSE201356** 4-library organoid data (the
s23 result: iLISI **2.10 → 3.18**). Accept when ours achieves **equivalent batch mixing** (iLISI /
kBET within tolerance) **without over-correcting** biological signal (rod-dominant clusters
preserved; the `integration` over-correction diagnostic stays healthy). Add a deterministic
unit-level check on a tiny synthetic 2-batch set (known shift → corrected centroids coincide).

## Effort, risk, sequencing

- **Effort: L** (a real iterative algorithm + a careful validation pass) — ~2–3 focused sessions:
  (1) clustering + correction core + synthetic unit tests; (2) live validation vs the harmonypy
  oracle on GSE201356 + tuning; (3) swap the `integration` skill onto it behind a flag, keep
  harmonypy as oracle, ship as `skills/proprietary/`.
- **Risk**: matching mixing quality + convergence tuning (σ/θ/λ/K). Mitigate by oracle-driven
  iteration and the metric-not-pixel acceptance bar.
- **Sequence**: after the current paper-metadata build and the next figure-repro ledger; it's a
  hardening/moat investment, not a blocker. Pin `harmonypy==0.0.10` until then (done this session
  via the venv recovery; fold into pyproject when the lock is next regenerated).

→ Captured in memory as `selom-harmony-reimplementation`. Related: [[selom-rpgrip1-gap-tooling]]
(Cepo + in-house GSEA = the same clean-room pattern), [[selom-hani-figure-reproduction]]
(integration shipped s23), [[selom-gsea-engine-sensitivity]] (validate by metric, not pixels).
