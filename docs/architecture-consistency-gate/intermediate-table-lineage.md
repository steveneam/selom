# D3 — Intermediate-table lineage (local)

_Last updated: 2026-06-27 — Claude. Companion to `roadmap.md` (Task D, D3). The local precursor to
D4 (the deferred DuckDB/Parquet lane)._

## The goal

The owner's "always a table; intermediate tables" — made **inspectable** and **reproducible**.
Between stages (ingest → clean → skill) a table flows; D3 lets you materialize that table as a
content-addressed artifact and ask three questions:

| Acceptance | How D3 answers it |
| --- | --- |
| *"inspect the matrix the skill actually saw"* | a run stamps an `artifact_id`; `GET /artifacts/{id}/table` returns the exact bytes the runner consumed |
| *a cleaned re-run is reproducible* | the id **is** the content hash, so the same input through the same recipe yields the *same* artifact — a re-materialize finds the existing immutable record, never rewrites or forks |
| *combine records "merged from {A, B, C}"* | a merged table's meta carries each source file as a parent and renders the receipt |

## The store (`engine.lineage`)

Content-addressed and immutable, the same discipline as the C1 result cache:

* the table bytes are written under their own SHA-256 — `data/artifacts/<id>.csv` — beside a sidecar
  `data/artifacts/<id>.meta.json` (`ArtifactMeta`);
* the meta records the **lineage**: `parents` (each a `ParentRef` — a source file by its content
  SHA, or a prior artifact by its id), the **`recipe`** (the cleaning-plan steps that produced it),
  `recipe_note`, and a computed **`receipt`** ("merged from {A, B, C}" for a combine, "derived from
  X" otherwise);
* a re-materialize of the same bytes returns the **existing** record (idempotent — the
  reproducibility guarantee; created_at is preserved, nothing is rewritten);
* a single-cell **matrix** (AnnData) is recorded **meta-only** — shape + lineage, never a multi-GB
  CSV (honest and bounded);
* dependency-free (pandas/numpy the engine already imports) and gated by `SELOM_ARTIFACTS` (default
  on).

## Wiring

* **`POST /skills/{id}/run`** — after the run, `lineage.materialize_bundle(bundle, recipe=plan.steps,
  recipe_note=plan.note)` materializes the table the skill consumed; the response carries the
  `artifact` record. Fail-soft — a lineage write never breaks a run.
* **`POST /data/combine`** — the merged cohort table is materialized with each input file as a
  parent (its content SHA captured *before* the temp uploads are cleaned up), so the combine summary
  header surfaces `artifact_id` + the "merged from {…}" `receipt`.
* **`GET /artifacts/{id}`** — the lineage record (meta + the ancestor chain).
* **`GET /artifacts/{id}/table`** — the materialized CSV (download / inspect the matrix).

## D4 is a backend swap, not a rewrite (deferred)

The local-dir store sits behind one `materialize` / `get_table` / `get_meta` / `lineage` interface.
The deferred D4 DuckDB/Parquet lane swaps the local CSV/JSON backend for Parquet artifacts + a
manifest under the same interface — exactly as C1's disk tier swaps for R2. The content-addressing,
the lineage shape, and the receipt all carry over unchanged. **Per the discussion gate, D4 (and any
materialization bucket) waits for the owner conversation** — D3 deliberately stops at the local,
DB-free tier.

## Not in D3 (documented scope)

* Cleaning is **advisory** today (`engine.cleaning` returns a *plan*, "used as-is"), so the ingested
  table *is* the cleaned table and the recorded recipe is the proposed plan (honestly "used as-is"
  for a results/ERG table). When cleaning becomes an applied transform, it materializes a `cleaned`
  artifact whose parent is the `ingested` one — the artifact→artifact chain `lineage()` already
  walks.
* No eviction / lifecycle on the local tier (gitignored, dev-scale tables) — D4 owns artifact
  lifecycle.
* The FE "Inspect the matrix" surface (a button on the figure → the artifact table) is a follow-up
  FE task; D3 ships the `artifact_id` in the run response + the inspect endpoints it needs.
