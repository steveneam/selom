# Selom

A no-code multi-omics figure SaaS. A wet-lab biologist with no bioinformatician drops raw omics data (h5ad / CSV / mzML), applies composable, reproducible analysis **skills** (UMAP, clustering, DEG, volcano, heatmap, GSEA), and gets publication-ready, editable figures plus auto-generated methods text — every figure traceable to a versioned analysis recipe, not a black box.

See `PRODUCT.md` for the vision and `ROADMAP.md` for the plan.

## Stack

- **Backend:** Python 3.12 + FastAPI + scverse (Scanpy / anndata / pyDESeq2 / decoupler) skill runners.
- **Frontend:** Next.js 16 + React 19 + editable Plotly figures (react-plotly.js render + custom shadcn/ui property panel emitting RFC-6902 JSON-Patch).
- **Data / infra (placeholders, wired later):** Supabase (Postgres + Auth + RLS), Cloudflare R2 (object storage, $0 egress), Redis + arq (async job queue), Stripe (billing).
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

**Scaffold / pre-build.** Repo skeleton and agent-boot files are in place; the P0 hello-UMAP path is not yet wired.

## Reference

Full build dossier (architecture, infra, cost, first-10-days):
`C:/Users/seamegdool/Desktop/Claude code and website tips/EAMOS Web Tool/Selom/Wiki/product/selom-build-dossier.md`
