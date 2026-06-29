# Scope — Harmony2 fit-assessment for Selom Melody

> Status: **BUILT + VALIDATED (session 30, 2026-06-19).** Owner approved the recommended subset
> (deltas **A + B**); shipped behind a **default-off `harmony2` flag** in
> `skills/integration/melody.py` (+ `run_real.py`, `skill.json`, `tests/test_melody.py`). Validated
> by metric against the **R `harmony` 2.0.5** (Harmony2) oracle — results at the foot of this doc.
> The original scope + recommendation is preserved below unchanged.
> Author: Claude (acting FE+BE), session 30, 2026-06-19.
> Question (owner-directed): Harmony2 (Patikas et al., bioRxiv 2026) is the 7-years-on successor
> to the 2019 Harmony method that **Selom Melody** (`skills/integration/melody.py`, shipped +
> validated s29) implements. Which of its improvements are worth folding into Melody to keep our
> integration engine novel and future-proof — and which are scale engineering we should ignore?
> Same discipline as the Melody build: **clean-room from the PAPER, validate by metric.**
> Companion docs: `docs/records/selom-integrate/spec.md` (the Melody spec), `docs/records/harmony-reimplementation-scope.md`
> (the s28 scope), memory `selom-harmony-reimplementation`.

---

## TL;DR — recommendation

**Fold in two algorithmic quality improvements, behind a single default-off `harmony2` flag.
Ignore the scale engineering. Treat batch-pruning as an optional low-priority extra.**

| What | Decision | Why |
|---|---|---|
| **(A) Stabilized (scale-invariant) diversity penalty** | **RECOMMEND — build** | A literal **one-term** change to the soft-assignment update; the exact formula is printed in the preprint (clean-room-able); directly fixes over-integration — the exact failure mode the figure-repro mission keeps hitting (batch≈genotype, cluster-abundance confounds). Negligible risk behind a flag. |
| **(B) Dynamic λ estimation (`λ̂_kb = α·E_kb`, α=0.2)** | **RECOMMEND — build** | Explicit printed formula (clean-room-able); the second half of Harmony2's anti-over-integration story (the paper turns A **and** B on together). Small, contained change to the correction step. |
| **(C) Batch pruning (`O_kb/N_b < 1e-5` → drop)** | **OPTIONAL — low priority** | Mostly a scale/speed + numerical-stability feature; at ~10k cells / ~4 batches it almost never triggers, and dynamic λ already shrinks outlier batches. Cheap to add as a robustness guard, but low value at our scale. |
| **Scale engineering** — sparse Φ, arrowhead inversion, k-means++ seeding, incremental/streaming PCA | **OUT OF SCOPE** | The headline of the paper (>100M cells, >1K batches) but irrelevant to Selom's ~10k-cell workloads. Arrowhead inversion is **mathematically identical** to Melody's existing `np.linalg.solve`; k-means++ is already what our `sklearn.KMeans` does. No quality change — pure performance for a regime we never hit. |

**Net:** A + B make Melody a clean-room implementation of the **current (2026) state-of-the-art**
Harmony method, not just the 2019 one — genuine novelty (no permissively-licensed Harmony2 exists;
the canonical R `harmony` 2.x and `harmonypy` 2.0.0 are both GPL-3.0 / C++) and longevity, with
**zero regression risk** to the validated s29 numbers (default-off). Effort **S–M (~1–1.5
sessions)**. Verdict: **worth it.**

---

## Source & method (clean-room discipline held)

- **Paper:** "Integration of large, complex single-cell datasets with Harmony2", Patikas, Yao,
  Madhu, Raychaudhuri, Hemberg, Korsunsky — bioRxiv 2026, doi `10.64898/2026.03.16.711825`,
  posted 2026-03-18. **License: CC-BY-NC-ND 4.0** (the *preprint text*; the *software* is GPL-3.0).
- **Extraction:** dogfooded our own `papers.extract_text` (pypdf/PDFium) on the owner-supplied PDF
  (26 pp, 72 k chars). The Online Methods prose extracts as text; the **equations render as image
  objects**, so the exact update rules were captured by rendering pp. 9–10 to PNG (`papers.render_page`,
  200 dpi) and reading them — same vision-gateway dogfood pattern as the figure-repro work.
- **⚠ License — read the PAPER, never the source.** The whole Harmony lineage is **GPL-3.0**
  (`harmonypy` 0.0.10 + 2.0.0, R `harmony`/`harmony2`). A published *algorithm/equation* is not
  copyrightable; *code expression* is. Building from the printed math keeps the clean-room defense
  intact; reading the GPL source to "port" it would taint that defense. This is the same posture
  that produced Melody and Cepo. See `license-decision-framework`. **(This directly answers the
  "would the harmonypy repo help for codebase analysis?" question — see the dedicated section below.)**

---

## The exact deltas (2019 Harmony → 2026 Harmony2)

Notation (paper's): `Z` (d×N) input PCA embedding, `Φ` (B×N) one-hot batch design, `R` (K×N) soft
assignment, `Y` (d×K) centroids, `O_kb`/`E_kb` (K×B) observed / expected cluster×batch counts,
`σ` entropy weight, `θ` diversity penalty, `λ` ridge penalty. Melody works in d×N internally and
already exposes `theta`, `sigma`, `lamb`, `nclust`, `max_iter_*`, `tau`.

### (A) Stabilized diversity penalty — changes the soft-assignment (E-step) only

The diversity term is the third term of the clustering objective. **Only the ratio inside the
`log` changed:**

```
Harmony1 (what Melody implements today):   log( (O_kb + 1)        / (E_kb + 1) )
Harmony2 (stabilized, scale-invariant):    log( (O_kb + E_kb + 1) / (E_kb + 1) )
```

**Why:** with the old `+1` smoothing, when a batch is absent/under-represented in a cluster
(`O_kb → 0`) **and** N is large, the ratio `(0+1)/(E_kb+1) → 1/(E_kb+1)`, so `log(…) → −∞`: the
diversity penalty blows up, dominates the objective, and forces over-mixing (over-integration). The
new ratio `(0+E_kb+1)/(E_kb+1) → 1`, so the penalty `→ log(1) = 0` — it *vanishes* for absent
batches instead of exploding. The paper states this "only impacts the soft cluster assignment
computation — the E-step."

The corresponding **soft-assignment update** (printed on p. 10) is:

```
R_ki  ∝  ( (E_kb + 1) / (O_kb + E_kb + 1) )^θ  ·  exp( −2 (1 − Y_k·Z_i) / σ )       (b = batch of cell i)
```

Melody's current `_cluster` uses the Harmony1 factor `((E_kb + 1)/(O_kb + 1))^θ`. **The whole change
is `+ E_kb` in the denominator:**

```python
# melody.py _cluster(), current (Harmony1):
penalty = ((1.0 + exp) / (1.0 + obs)) ** theta_b
# Harmony2 stabilized:
penalty = ((1.0 + exp) / (1.0 + obs + exp)) ** theta_b
```

### (B) Dynamic λ estimation — changes the correction (M-step / ridge) only

In Harmony1 the ridge penalty is a **scalar `λ = 1`** on every batch coefficient. Harmony2 makes it
**per-(cluster, batch)**:

```
λ̂_kb = α · E_kb                 with default α = 0.2   (intercept still unpenalized, λ₀ = 0)
```

**Why:** in the per-cluster ridge `W_k = (Φ* diag(R_k) Φ*ᵀ + λ̂_k I)⁻¹ …`, a batch with an *outlier*
soft assignment (cell from batch b with `R_ik > 0` but b doesn't really belong to cluster k → small
`O_kb`) should have its correction shrunk to ~0 to avoid over-integration; a batch that is
*legitimately* small should not be over-shrunk. Tying the penalty to the **expected** count `E_kb`
(rather than a fixed 1) achieves both: `λ̂_kb` is large relative to a true outlier's `O_kb` (shrinks
it) but tracks real support otherwise. The paper: a batch needs `> 0.1·λ̂_kb` probability mass to
"offset the shrinkage," hence α = 0.2.

In Melody's `_correct`, the static `ridge = diag([0, λ, …, λ])` becomes a **per-cluster** diagonal
`diag([0, α·E_k1, …, α·E_kB])`. This needs the `exp` (E) matrix threaded from `melody()`'s loop into
`_correct` and an `alpha` parameter — a small, contained change.

### (C) Batch pruning — numerical/scale guard (optional)

Before each cluster's ridge, **drop batches with `O_kb/N_b < 1e-5`** (default) and set their
correction factors to 0. Two stated goals: (1) shrink the `(B+1)×(B+1)` matrix that's inverted
(speed, only matters with **multiple** covariates and large B) and (2) numerical stability
(low-support batches make the matrix near-singular for small λ). A *minor* anti-over-integration
side-effect (zeros outlier-batch correction). **At Selom's scale this almost never fires** and
(B)'s dynamic λ already handles the outlier case, so this is a low-priority extra.

### Scale engineering — captured for completeness, all OUT OF SCOPE

| Feature | What it does | Why out of scope for Selom |
|---|---|---|
| Sparse design matrices (CSC Φ/Φᵀ, cached transpose) | linear scaling as #batches grows | At ~4 batches / 10k cells the dense Φ is trivial. No correctness change. |
| **Arrowhead inversion** (closed-form for C=1) | O(B) instead of O(B³) LU for single-covariate ridge | **Mathematically identical result** to Melody's `np.linalg.solve` on the `(B+1)×(B+1)` system — pure speed. At B≈4 the solve is already instant. |
| k-means++ centroid seeding | O(KN) seeding vs native R k-means | Melody already seeds via `sklearn.KMeans(n_init=10)`, which **is** k-means++. Already done. |
| Incremental / truncated-SVD streaming PCA | PCA over 100M cells without materializing | PCA is in the *surrounding* scanpy pipeline, not Melody; irrelevant at our scale. |
| `early_stop` toggle, hybrid sparse–dense backend, 16-thread/SLURM benchmarking | atlas-scale throughput | Implementation/infra detail; some only described in the GPL code → not clean-room-able and not wanted. |

---

## Per-delta fit assessment

**(a) Clean-room-able?** A and B: **yes** — the final update rules and the α/threshold defaults are
*printed explicitly* in the preprint (transcribed above); the derivations are "not shown" but we
don't need them. C: **yes** (threshold printed). Nothing we'd build is GPL-source-only. (The
`early_stop` logic and the sparse/arrowhead engineering are partly code-only, but they're out of
scope anyway.)

**(b) Worth it for Selom's scale + the figure-repro mission?** **Yes for A+B.** Selom never hits the
scale regime, so the speed work is moot — but the *quality* work targets **over-integration**, which
is a recurring, named hazard in our reproduction work: the `scrna-batch-genotype-confound` rule
(cluster-abundance claims that are really batch artifacts), the RPGRIP1 Fig-6D Rod-2 case (99% one
sample), and any heterogeneous multi-study atlas a user drops in. A Melody that **mixes batches
without merging distinct lineages** is strictly better for figure repro than one that can
over-correct. The paper's own Fig-2e numbers make the case: on a non-overlapping stress test
Harmony1 hit purity 0.964 vs Harmony2 0.997 at the *same* batch mixing 0.502.

**(c) Low-risk behind a flag?** **Yes.** Both are opt-in; default-off reproduces the s29 engine
**bit-for-bit** (the regression guard). A is a one-line factor swap; B is a localized ridge-diagonal
change. Neither touches the public skill contract, the `{data,layout}` output, or the mixing
diagnostic.

**Novelty + longevity?** **Yes.** Folding A+B means Melody implements the 2026 method, behind
toggles, with **no GPL dependency** — something that does not exist in permissive form today. It
keeps "Selom Melody" current for years and deepens the proprietary moat (the cross-cutting,
clean-room integration layer), exactly the owner's stated goal.

---

## Recommended subset + surgical sketch

Ship **A + B together behind one `harmony2: bool = False` engine flag** (the paper enables them as a
pair). Keep C as a follow-up only if a real heterogeneous dataset shows a need.

`melody.py` changes (all gated on the flag; default path untouched):

1. **Signature:** add `harmony2: bool = False`, `alpha: float = 0.2` to `melody(...)` and pass-through
   from `integration/run_real.py` (new optional skill params `harmony2`, `alpha`; defaults preserve
   today's behavior).
2. **(A) in `_cluster`:** when `harmony2`, use `((1+exp)/(1+obs+exp))**theta_b`; else the current
   factor. Optionally mirror the `(O+E+1)/(E+1)` ratio in `_objective`'s diversity term for
   convergence consistency (cosmetic — the objective is only used for early-stop).
3. **(B) in `_correct`:** thread `exp` (K×B) + `alpha` in; when `harmony2`, build the per-cluster ridge
   diagonal `diag([0, *(alpha*exp[k])])` instead of the static `diag([0, λ, …])`.
4. **Tests** (`tests/test_melody.py`): (i) **default-off byte-identity** vs the current engine on the
   synthetic fixture (hard regression guard); (ii) on a *constructed over-integration* synthetic
   (two non-overlapping cell-type groups across batches) assert `harmony2=True` preserves cell-type
   purity at least as well as — and mixing comparable to — `harmony2=False`; (iii) determinism +
   shape unchanged with the flag on.
5. **Provenance / trust-as-output:** when the flag is on, surface it in the skill subtitle
   (e.g. "Melody (Harmony2 mode)") alongside the existing before→after mixing number.

Reversibility: every change is engine-internal and flag-gated → fully reversible; the s29 spec's
invariants (no harmonypy on the shipped path, stable contract, determinism) all still hold.

---

## Validation plan (validate-by-metric, never pixels)

1. **Regression guard (must pass first):** `harmony2=False` must reproduce the s29 result on real
   GSE201356 **exactly** (kNN-entropy 0.826 / iLISI 3.192 / structure 12.41 / cLISI 1.35) and the
   synthetic unit test byte-for-byte. **Keep a spare copy of the validated `melody.py` before
   touching it** (owner's explicit instruction) so we can diff/restore if the flag path disturbs the
   default path.
2. **The right test dataset matters.** GSE201356 (4 libraries of the *same* rod-dominant organoid
   system — overlapping populations) has **little over-integration to prevent**, so it will *not*
   distinguish Harmony1 from Harmony2 — both should land at ≈the same mixing/purity. Demonstrating
   the improvement needs a **non-overlapping stress test** in the spirit of the paper's Fig 2: take a
   real annotated dataset, split samples into two imbalanced groups with **disjoint** cell types,
   integrate, and measure **batch mixing ↑ while cell-type purity stays high**. We can construct this
   from data already on the CMRI share / a public atlas; the metric is the paper's own
   (normalized-entropy batch mixing + `1 − normalized cell-type entropy` purity). Accept when
   `harmony2=True` holds purity at PCA-like levels while raising mixing over raw — and beats
   `harmony2=False` on purity at matched mixing.
3. **Oracle (optional, ASK first).** The true Harmony2 oracle is the **R `immunogenomics/harmony`
   2.x** package (CRAN) — installable against our already-present R-4.6.0 oracle toolchain
   (validation-only, ADR 0002), avoiding the C++ Python build. The Python `harmonypy 2.0.0` is the
   GPL C++/Armadillo build that does **not** compile here (needs a C++ toolchain / Docker) — **do not
   attempt without owner approval** (`ask-before-docker-wsl`). Either oracle is run **black-box**
   (compare metrics on the same input) — never read for code. If no Harmony2 oracle is installed, the
   constructed stress test (#2) + the paper's printed Fig-2e targets are sufficient acceptance
   evidence.
4. **Full suite:** `pytest` BE green (baseline 480) + `ruff` clean; no dev servers.

---

## Does the GPL `harmonypy` repo help for "codebase analysis"? — No (deliberately)

Short answer: **for the reimplementation, no — we should specifically avoid reading it.**

- `github.com/slowkow/harmonypy` is **GPL-3.0** (both 0.0.10 = Harmony1 and 2.0.0 = the C++/Armadillo
  rewrite). Reading its source to guide our port is exactly what taints a clean-room: our legal
  defense is that Melody was written from the *published math*, never from the GPL *code expression*.
  We already have the precise update rules from the preprint (transcribed above), so the source adds
  nothing we're allowed to use.
- The canonical Harmony2 is actually the **R** `immunogenomics/harmony` 2.x package (the paper says so);
  `slowkow/harmonypy` is the Python port and may lag the algorithmic changes — but the license verdict
  is identical either way.
- Where the repo **does** legitimately help: as a **black-box validation oracle** — install it, run it
  on the same input, compare the mixing/purity metrics. That's the established discipline (`harmonypy
  0.0.10` is already pinned as the Harmony1 oracle). Using it as an oracle ≠ reading it as a source.

So: keep harmonypy installed (oracle extra) for metric comparison; build A/B from the paper. (If we
want a *Harmony2* oracle specifically, the low-risk route is the R package on the existing R oracle —
ASK first; the C++ Python build is Docker-gated.)

---

## Open questions for the owner (answer before any build)

1. **Build A+B now, or defer behind the 4th figure-repro ledger / OSCA Gap E?** (Recommend: small
   enough to slot in; A alone is a one-liner.)
2. **A+B together, or A first (cheapest, biggest single win) then B?**
3. **Stand up a Harmony2 oracle?** R `immunogenomics/harmony` 2.x (validation-only, low risk) vs. no
   oracle (rely on the constructed stress test + the paper's printed targets). The C++ `harmonypy
   2.0.0` build is Docker-gated → only with explicit approval.
4. **Include batch-pruning (C)?** (Recommend: skip for v1; revisit if a heterogeneous dataset needs it.)

---

*Phase plan if approved:* keep a spare `melody.py` → `/spec` (PAUSE for review) → build A+B behind
`harmony2=False` → validate (regression byte-identity first, then the constructed over-integration
stress test, optionally vs the R Harmony2 oracle) → per-lane scoped commits (code/doc split) → ASK
before push. Never regress the s29 numbers.

---

## Build + validation result (session 30 — A + B SHIPPED, PASSED)

Owner approved **Build A+B now** + the R Harmony2 oracle + a constructed stress test. Built behind
`melody(..., harmony2=False, alpha=0.2)` (and skill params `harmony2`/`alpha`, default off):
**(A)** `_cluster` diversity denominator `(1+O)` → `(1+O+E)` when `harmony2`; **(B)** `_correct`
ridge `diag([0,λ,…])` → per-cluster `diag([0, α·E_k1, …])` (floored `1e-8`). The spare s29 engine
was copied to `graphify-out/scratch/melody_s29_backup.py` before editing.

**Validation (all three claims passed):**

1. **Default-off byte-identity (regression guard).** New `melody(harmony2=False)` is **`array_equal`
   (max|diff| = 0.0e0)** to the s29 backup on the synthetic fixture — the validated 2019 path is
   bit-for-bit untouched. (The full pre-existing `test_melody.py`/golden/live suite stays green.)
2. **Constructed non-overlapping stress test** (two imbalanced groups, disjoint lineages; θ = 4 and
   6). Harmony2 mode raises batch mixing **and** preserves cell-type purity better than Harmony1:

   | θ=4 | batch mixing ↑ | cell-type purity ↑ |
   |---|---|---|
   | raw PCA | 0.000 | 1.000 |
   | Melody off (Harmony1) | 0.455 | 0.995 |
   | **Melody on (Harmony2)** | **0.569** | **1.000** |

3. **R `harmony` 2.0.5 (Harmony2) oracle**, same stress test, convergence tolerances matched
   (`alpha=0.2`, default `lambda=NULL` = dynamic-λ): **Melody-on matches the oracle on metric** —
   batch mixing **0.569 vs 0.555** (|Δ|=0.014), purity **1.000 vs 1.000** (|Δ|=0.000), both well
   above Harmony1 (0.455 / 0.995). The pre-Harmony2 package (`harmonypy 0.0.10`) corresponds to
   Melody-off (the s29 result). Confirms the clean-room A+B is faithful to the real Harmony2.

   *Oracle note:* R `harmony` 2.0.5's own defaults independently confirm the parameterization —
   `harmony_options()` exposes `alpha = 0.2` (our Delta-B α exactly) and `batch.prop.cutoff = 1e-5`
   (the Delta-C pruning threshold); `lambda = NULL` (dynamic) is its default. Run black-box only
   (validation-only, ADR 0002) — never read for source.

**pytest BE 485 (480 + 5 new Harmony2 tests) green; ruff clean.** Delta C (batch pruning) was
**not** built (low value at our scale, as scoped). No FE change (output contract stable).
