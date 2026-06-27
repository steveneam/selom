# D1 — Declared skill input contract + pre-run data-contract gate

_Last updated: 2026-06-27 — Claude. Companion to `roadmap.md` (Task D, D1)._

## The problem

A skill assumes its input has a shape. Drop the wrong table and the skill reaches for a
column that isn't there — a `KeyError` deep in the runner that surfaces as a 500 "the
service is unavailable", or (worse) a misleading figure. The owner's acceptance:

> A DE-viz skill dropped on a counts table gets a **clear pre-run message**, not a runtime
> stack trace.

## The contract already exists — D1 enforces it

The per-skill **input contract** was built with the data-fit scorer (s52,
[[selom-data-fit-scorer]]) and lives in `engine/compat.py`:

| Declaration | What it says | Example |
| --- | --- | --- |
| `_REQS[skill]` | the payload **modality class** the skill needs (matrix vs table) | `umap_scrna → {sc_counts}` (a flat table can never be a single-cell matrix) |
| `_SCHEMA[skill]` | the named **column groups** a table-consuming skill needs | `volcano → [fold-change, significance]` (matched by synonym substring: `avg_log2FC`, `p_val_adj`, `adj.P.Val`, …) |

`compat.fit(skill, file)` returns a `DataFit` whose `verdict` is `fit` / `missing_columns`
/ `wrong_modality` / `unclear` / `unreadable`, and a `gated` flag. **Before D1 this was
advisory** — surfaced as a 0-100 score on the data-fit/intake surface and used by the
reproduction *matcher* to avoid force-feeding a bad supplement — but the own-data `POST
/run` path did **not** gate on it: a certain mismatch fell through to the runner.

**D1 promotes the advisory contract to an enforced pre-run gate** and guards the
declarations from drift.

## The gate (`POST /skills/{id}/run`)

After the QC "is-my-data-clean?" gate, and **before** the runner is entered:

```python
data_fit_obj = compat.fit(skill_id, compat.assess_bundle(bundle))
if data_fit_obj.gated and not override:
    raise HTTPException(422, detail={"error": "data_contract_failed",
                                     "message": compat.contract_message(data_fit_obj),
                                     "skill_id": ..., "data_fit": ..., "routing": ...})
```

* **Honest** — only a *positively-determined* incompatibility blocks (`compatible is
  False`). An unreadable or modality-unclear file stays optimistic and runs (the same
  load-bearing rule the matcher uses, so no fake-path drive and no real-but-odd file is
  ever false-blocked).
* **Overridable** — `override=true` (the same escape hatch as the QC gate) bypasses it,
  for a rare classifier / column-synonym miss.
* **Single source** — the `DataFit` is computed once here and reused for the response's
  `data_fit` (no second load/score).
* **Complementary, not duplicated** — a skill *without* a compat contract (e.g. the ERG
  skills) is never gated here; its own runner raises `ValueError → 400` (the T6 honest-
  error path). D1 is the declared, uniform safety net *above* per-runner validation.

The FE surfaces the structured `detail.message` (`runSkill` now reads `detail.message` for
any typed `{error, message}` gate), so the user reads "…missing a fold-change column…"
rather than "the request was rejected (422)". The data-fit verdict also already renders on
the intake surface (`DataFitVerdict`), so the *why* is visible before Run, too.

## The guard (drift protection — the ratchet)

`tests/test_skill_input_contract.py` keeps the declarations honest, mirroring the OUTPUT
`test_skill_table_contract.py` philosophy ("declared + mechanically guarded"):

* every skill named in `_REQS` / `_SCHEMA` is a real shipped skill (no dangling contract);
* a `_SCHEMA` contract declares something checkable (≥1 named group with synonyms, or a
  numeric-score requirement);
* a `_SCHEMA` skill's modality requirement (if any) admits a *table* class — else the L2
  class gate would block before the column check could run.

`tests/test_data_contract.py` proves the endpoint behaviour (counts → 422 naming the
missing columns · a DE table → 200, no false block · `override=true` bypasses · an
uncontracted skill is not gated).

## Adding a contract for a new table skill (fill-in-the-blanks)

1. Add `skill_id → ([group, …], needs_numeric)` to `_SCHEMA` (reuse the synonym sets in
   `engine.databundle` — `_LOGFC`, `_PVAL`, … — so header variants resolve), and/or a
   modality class to `_REQS`.
2. The pre-run gate, the data-fit score, and the matcher all pick it up — one declaration,
   three consumers.
3. The guard test enforces it ships against a real skill.

## Not in D1 (documented scope)

* The **jobs** path (`POST /skills/{id}/jobs`) is not gated — it already wraps runner
  errors into the job's `error` field (no 500 leak), and a pre-flight `assess_file` would
  double-load the heavy matrix inputs jobs are used for. The gate can extend there if a
  clearer submission-time message is wanted later.
* Broadening `_SCHEMA` beyond the DE-table consumers (volcano / enrichment / gsea) is a
  fill-in-the-blanks follow-up; param-driven skills (e.g. `proteomics_de`'s group
  substrings) don't have a static column contract.
