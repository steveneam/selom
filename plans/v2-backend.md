# v2 — Backend lane (Codex owns `app/backend/`)

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

## B2 (charter) — Steven's Stage-1 skills · SIGNED OFF 2026-06-11, not started

Build 6 backend runners (UMAP shipped in B1), each `skills/<slug>/{skill.json, run.py}`,
entrypoint `<slug>.run:run`, params validated by the `SkillSpec` `param_spec`, returning an
editable plain-array Plotly spec (reuse the `_jsonable` typed-array decoder from
`run_scanpy.py`). Each ships a **golden-image snapshot test** on a fixed demo input (the B4
reproducibility seed). FE already lists these as Verified `selom.*` and `runtimeSkillId()`
routes `selom.<slug>` → `<slug>`, so FE conforms with no change (except a new `selom.violin`
catalog entry — FE lane).

Dependency order: **cluster → violin → DEG → volcano → heatmap → GSEA**.
1. `cluster` — Leiden + cluster sizes/QC + resolution param. `[scrna]`.
2. `violin` — marker-gene expression violins per cluster. `[scrna]`. (new skill)
3. `deg` — scRNA (`rank_genes_groups`) + bulk (`pydeseq2`). Adds `pydeseq2`.
4. `volcano` — from DEG output; pure plotting, no new deps.
5. `heatmap` — top-DEG / marker panel; pure plotting.
6. `enrichment` (GSEA) — ranked-list enrichment. **Gene sets = Reactome / GO (DECISIONS #9,
   license-clean). Do NOT use gseapy/MSigDB** (AGPL — RISKS #6).

Locked decisions: **public proxy datasets now** (pbmc3k scRNA + a public bulk RNA-seq set + a
sample ranked list); real retinal-atlas / RPGRIP1 organoid data dropped in later for hardening.
Out of B2 scope: async queue (B3), reproducibility-bundle/guardrails/methods-text/Kaleido (B4).

## Notes / landmines
- Don't pin `numpy<2`. pandas 3.0 = Copy-on-Write default (no in-place slice
  mutation). scvi-tools pulls PyTorch — install the **CPU** torch wheel first in
  CPU workers so uv doesn't grab CUDA.
- boto3 → R2: set `request_checksum_calculation='when_required'`.
- Commercial/licensing gates are **deferred** (see `../LAUNCH-GATES.md`). Build
  now; do not let gating block the lane.
