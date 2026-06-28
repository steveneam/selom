# Selom

A no-code multi-omics figure SaaS — a **project-first command center / IDE** for biology. A wet-lab biologist with no bioinformatician drops raw omics data (h5ad / CSV / mzML), **browses and installs analysis skills like apps in an App Store**, answers a few guided questions, and gets publication-ready, editable figures plus auto-generated methods text — every figure traceable to a versioned analysis recipe, not a black box. Skills are sourced from **bioSkills** (540 reference) + **ClawBio** (88 runnable); the launch wedge runs natively, the catalog grows to the full ~600 via the Skill Foundry.

See `PRODUCT.md` for the vision, `docs/pillars/plan.md` for the current engine-spine plan, and `docs/README.md` for the docs index. (`ROADMAP.md` and `docs/command-center/design.md` are historical — see the docs index.)

## Stack

- **Backend:** Python 3.12 + FastAPI + scverse (Scanpy / anndata / pyDESeq2 / decoupler) skill runners.
- **Frontend:** Next.js 16 + React 19 + editable Plotly figures (react-plotly.js render + custom shadcn/ui property panel emitting RFC-6902 JSON-Patch).
- **Data / infra (AWS-first; deploy = step 8):** Aurora Serverless v2 Postgres (min=0 ACU), S3 (SSE-S3) object storage, split deploy = light zip Lambda (API) + heavy Fargate (compute), Step Functions for async jobs, Clerk (auth), Vercel (FE). Plan of record: `docs/aws-materialization/plan.md` (supersedes the earlier Supabase + Cloudflare R2 + Redis/arq + Stripe shape).
- **R 4.6:** validation-only (golden-image references), never production runtime (ADR 0002).

## Repo Layout

| Path | What |
|---|---|
| `app/backend/` | FastAPI gateway + skill runners (Codex lane) |
| `app/frontend/` | Next.js app + figure editor (Claude lane) |
| `agent_handoff/` | Cross-agent coordination home |
| `plans/` | Per-lane build plans (e.g. `v2-backend.md`) |
| `docs/` | Project docs |
| `.claude/` | Claude Code config |

## Quickstart

**Backend** (`app/backend`)
```
uv sync
uv run uvicorn main:app --reload   # :8000
```
uv binary: `C:/Users/seamegdool/.local/bin/uv.exe` (pins Python 3.12; system is 3.10).

**Frontend** (`app/frontend`)
```
npm install --legacy-peer-deps
npm run dev                        # :3000
```

**P0 gate (hello-UMAP):** upload `demo.h5ad` -> backend runs Scanpy -> returns a Plotly spec -> frontend renders an interactive, editable UMAP coloured by Leiden cluster -> a style change applies client-side without recompute.

## Status

**All engine pillars complete; step 7c (FE state → Postgres) shipped; next = step 8
(AWS deploy).** The project-first command center is built and live at
[selom.vercel.app](https://selom.vercel.app): figure editor (spec = source of truth,
RFC-6902 JSON-Patch, dark-IDE brand), Skill Store, guided intake, the reproduction
engine + layered extractor, and the account-level Workspace Library. Frontend state now
persists to the backend (optimistic-cache projectStore/workspaceStore behind unchanged
interfaces). Current backlog: `docs/pillars/plan.md` + `docs/aws-materialization/plan.md`.
Live shared state: `agent_handoff/CURRENT.md`.

## Reference

Full build dossier (architecture, infra, cost, first-10-days):
`C:/Users/seamegdool/Desktop/Claude code and website tips/EAMOS Web Tool/Selom/Wiki/product/selom-build-dossier.md`
