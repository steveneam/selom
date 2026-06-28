# v2 — Backend lane (Codex owns `app/backend/`)

> **HISTORICAL (2026-06-29).** Superseded by `docs/pillars/plan.md` +
> `docs/aws-materialization/plan.md`. Kept for the original P0 framing only.

FastAPI service that runs omics skills and returns editable Plotly figure specs.
Python 3.12, uv-managed. Frontend talks to this over `NEXT_PUBLIC_API_BASE`.

## P0 — first end-to-end figure

### 1. Skill contract
- Define the JSON skill contract: `id`, `engine` (`python` | `r`), `param_spec`
  (Pydantic v2 model: typed, validated inputs), `inputs` (dataset handles),
  `outputs` (a Plotly JSON figure spec).
- One contract, many skills. The runner dispatches on `engine`.
- Validate every inbound `param_spec` against the skill's Pydantic model; reject
  bad params with a 422 before any compute runs.

### 2. Stub → real UMAP runner
- Ship `hello-UMAP` first as a **stub**: ignore inputs, return a canned Plotly
  scatter so the frontend can integrate against a real shape immediately.
- Then make it **real**: `scanpy` QC → normalize → PCA → neighbors → UMAP →
  cluster; emit the embedding as a Plotly scatter figure spec.

### 3. FastAPI endpoints (the contract seam)
- `POST /upload` — accept an upload (`.h5ad` / matrix), store to local data dir
  (later R2), return a dataset handle.
- `POST /skills/{skill}/run` — validate `param_spec`, run the skill, return the
  Plotly JSON figure spec.
- `POST /figures/{id}/export` — Kaleido static export (PNG/SVG/PDF).
- `GET /healthz` — liveness.
- CORS: allow the frontend origin.

## P1 — productionize

### 4. Supabase
- Auth (JWT verify on protected routes), Postgres for figures/datasets metadata,
  RLS as the primary access-control layer. Migrate via `supabase db push`.

### 5. arq async queue
- Long skills (real UMAP, scvi-tools) run off-request on **arq** over Redis;
  `/skills/{skill}/run` enqueues and returns a job id; add `GET /jobs/{id}`.
- arq is maintenance-only upstream — fine for v1; Dramatiq is the active fallback
  if arq blocks us.

### 6. Kaleido export
- kaleido **1.3.x** + plotly **6.8.x**. v1 needs **system Chrome** in the Docker
  image (`apt-get install -y chromium`; `ENV KALEIDO_CHROME_PATH=/usr/bin/chromium`).
  EPS is dropped — PNG/SVG/PDF only.

## B2 (charter) — Steven's Stage-1 skills · ✅ DONE 2026-06-12 (local, not yet pushed)

Built all 6 backend runners (UMAP shipped in B1), each `skills/<slug>/{skill.json, run.py + run_real.py}`,
entrypoint `skills.<slug>.run:run`, params from the `SkillSpec` `param_spec`, returning an editable
plain-array Plotly spec via the shared **`skills/_plotly.jsonable`** (factored out of `run_scanpy.py`; umap
reuses it). Each ships a **golden-image snapshot test** pinned to a dependency-free STUB
(`tests/test_skills_golden.py` + `tests/golden/`, regen `tests/regen_golden.py`) — deterministic regardless of
installed deps, mirroring `test_contract`. Engine selection: `SELOM_SKILLS_ENGINE` (auto/stub/real) via
`skills/_engine.py`. `main.py` `POST /skills/{id}/run` generalized to any Verified skill (query-string params +
preserved upload suffix). FE conformed with the one new `selom.violin` catalog entry.

Dependency order built: **cluster → violin → DEG → volcano → heatmap → GSEA**.
1. `cluster` — Leiden + cluster-size bar + resolution param. `[scrna]`. ✅
2. `violin` — marker-gene expression violins per cluster. `[scrna]`. (new skill) ✅
3. `deg` — scRNA (`rank_genes_groups`) + bulk (`pydeseq2`, with a CPM-log2FC fallback when pydeseq2 absent). ✅
4. `volcano` — from a DE table; pure pandas/plotly, no new deps. ✅
5. `heatmap` — markers-per-cluster (scRNA) or top-variance (bulk), row z-scored. ✅
6. `enrichment` (GSEA) — **in-house hypergeometric ORA + BH FDR** over a bundled GO/Reactome `gene_sets.json`.
   **NO gseapy/MSigDB** (DECISIONS #9 / RISKS #6 — license-clean by construction). ✅

Verification: `uv run --directory app/backend python -m pytest` = **14 passed**; real engines smoke-tested on
synthetic h5ad/CSV (all 8 paths). Locked decisions honoured: **public proxy datasets** (the engines accept the
uploaded file; no bulk dataset bundled — golden tests use the stub), **GSEA = Reactome/GO**.
B2 follow-ups (later): full GO/Reactome GMT ingestion to replace the bundled sample; real-engine numerical
golden tests vs an R oracle (RISKS #7). Out of B2 scope: async queue (B3), reproducibility/guardrails/methods/Kaleido (B4).

## B3 (charter) — Skills as a service (jobs + storage) · ✅ CORE DONE 2026-06-12 (pushed)

- **Live `GET /skills` registry.** `skills/registry.py` maps each `skills/<slug>/skill.json` (+ a new optional
  `catalog` block on `SkillSpec`) to the FE `SkillCatalogEntry` shape. Adding a skill dir surfaces it in the Store
  with no FE edit. `test_registry.py` pins the shape + completeness.
- **Async jobs API.** `POST /skills/{id}/jobs` (enqueue) → `GET /jobs/{id}` (poll) / `/jobs/{id}/events` (SSE,
  `text/event-stream`) / `/jobs/{id}/result` (`{figure}`, same shape as `/run`). New `config.py` (pydantic-settings),
  `jobs/{store,queue,worker}.py`, `storage/results.py`. One `execute_job` is shared by the inline executor and the
  arq worker so the modes can't drift. `test_jobs.py` covers the inline lifecycle + SSE + 404s.
- **Infra off by default.** Jobs run **inline**, results land on the **local filesystem** — a fresh `uv sync` +
  uvicorn runs the whole API with zero infra. `SELOM_QUEUE=arq` (+ Redis, DECISIONS #6) and `SELOM_R2_*` (+ Cloudflare
  R2; boto3 with the RISKS #5 checksum fix) flip on the distributed/cloud path. New optional `[jobs]` extra; the
  inline+local path needs none of it. `/run` stays **synchronous** (the proven light-skill path); only heavy skills use `/jobs`.
- **Open B3 item (carries to next session):** arq cross-process job *status* needs a **Redis-backed JobStore**.
  Today success propagates cross-process via the shared result store (`get_job` probes it), but queued/running/error
  states live in each process's in-memory store — see the caveat in `jobs/worker.py`. Stand up Redis + a Redis JobStore
  to make arq mode fully observable. (R2 + arq are otherwise wired; they just need real infra, a B7/B8 concern.)

`pytest` = **21 passed** (14 base + 3 registry + 4 jobs); ruff clean; live uvicorn smoke (skills/submit/poll/result/SSE) green.

## B4 (charter) — publish-confidence · 🟡 SLICE-1 DONE 2026-06-12 (committed `2ab7c43`, not pushed)

The product's core decision made tangible: *"is THIS the right, trustworthy, reproducible figure?"*. Slice-1 = the
two machine-+human halves of the answer; both ride on every `/run` and job result.

- **Reproducibility bundle** — `provenance.py`. `build(spec, data_path, filename, params)` returns
  `{skill{id,version,title,engine}, params (resolved+typed), input{filename,sha256,n_bytes}, environment{python,platform,
  engine_policy,packages}}`. SHA-256 streams the upload; `packages` reads installed dist versions via `importlib.metadata`
  for the tracked scientific stack (absent ones omitted). Pure-Python, deterministic, **no new deps**.
- **Auto methods-text** — `methods.py`. `build(spec, params)` → `{text, citations}` from deterministic per-skill templates
  that quote the exact (resolved) params + canonical tool citations (Scanpy/Leiden/UMAP/PyDESeq2/DESeq2/BH/GO/Reactome/SciPy);
  generic fallback for unknown ids; every text closes with the Selom attribution sentence.
- **Typed param resolution** — `contract.resolved_params(spec, params)` overlays defaults + coerces to `param_spec` types
  (the runners still coerce their own inputs — the proven path is untouched).
- **Wire-up (additive).** `POST /skills/{id}/run` + `GET /jobs/{id}/result` now return `{figure, provenance, methods}`
  (same shape both paths; the FE still reads `.figure`). `Job` gained `filename`; `submit`/`execute_job` thread it; the shared
  `execute_job` builds + stores the **full bundle** (so inline + arq stay identical); `result_store.put` param figure→payload.
- **Verified:** `pytest` = **28 passed** (21 + `tests/test_provenance.py` + `tests/test_methods.py` + jobs-bundle asserts);
  ruff clean; live uvicorn smoke (`/run` + job submit/result) returns the full bundle with typed params, SHA-256, env, cited methods.
- **B4 remaining (next):** (a) **statistical-guardrail expansion** — `cluster` already carries a silhouette subtitle; add
  batch-effect / normalization / multiple-testing / low-cell warnings into the bundle (a `guardrails` field or figure subtitle);
  (b) **Kaleido journal export** PNG/SVG/PDF — kaleido≥1.3 + plotly≥6.1.1 + **system Chromium** in a Docker image
  (`KALEIDO_CHROME_PATH`; RISKS #2 / DECISIONS #7) — lands with the deploy image (B8-adjacent); scope a CPU-Docker path or defer.

## Integration backlog (owner-directed 2026-06-12) — see `../docs/integrations.md`

Done this session: **heatmap hierarchical row-ordering** (item 2 below) + **`gseapy` dropped** from `[omics]` (item 1's
SCA cleanup). Remaining:
1. **OmicVerse as a 2nd Verified engine + Foundry source — isolated.** It pins `pandas<3.0`/
   `anndata<0.12` (RISKS #9), so it can't share this venv. Stand up an OmicVerse worker in its
   own env/container and call it out-of-process (subprocess JSON or its MCP server — `ov.*` over
   `adata_id`, `omicverse/docs/mcp_quickstart.md`). Optionally route `cluster`/`deg`/`enrichment`/
   `heatmap` through `ov.pp.leiden`/`ov.bulk.pyDEG`/`ov.bulk.pyGSEA`/`ov.pl`; then trajectory/
   annotation/deconvolution. SCA-gate the 50 transitive deps. (`gseapy` already dropped from `[omics]` — DECISIONS #9.)
2. ✅ **heatmap hierarchical row-ordering** DONE — scipy correlation-distance + average-linkage leaf order
   (`skills/heatmap/run_real.py`, real-engine only; stub/golden unchanged). Optional dendrogram trace is a later add.
3. **R4DS/Quarto + ggplot2 reference set for B4** — methods-text + reproducibility-bundle shape
   (mirror Hermes `commands.sh + environment.yml`), journal figure defaults, and the **R validation
   oracle** harness (limma/DESeq2/ggplot2 golden references; RISKS #7).
4. **Catalog-count true-up** — `scripts/ingest-catalog` pulls live bioSkills/ClawBio; replace the FE
   seed's 540/88→628 with real numbers (≈385/33→418).
5. **MCP:** context7 already in `.mcp.json` (set `CONTEXT7_API_KEY`); add the OmicVerse/JARVIS MCP
   server once its isolated env exists (don't add a broken entry before then).

## Notes / landmines
- Don't pin `numpy<2`. pandas 3.0 = Copy-on-Write default (no in-place slice
  mutation). scvi-tools pulls PyTorch — install the **CPU** torch wheel first in
  CPU workers so uv doesn't grab CUDA.
- boto3 → R2: set `request_checksum_calculation='when_required'`.
- Commercial/licensing gates are **deferred** (see `../LAUNCH-GATES.md`). Build
  now; do not let gating block the lane.
