# Selom

A no-code multi-omics figure SaaS — a **project-first command center / IDE** for biology. A wet-lab biologist with no bioinformatician drops raw omics data (h5ad / CSV / mzML), **browses and installs analysis skills like apps in an App Store**, answers a few guided questions, and gets publication-ready, editable figures plus auto-generated methods text — every figure traceable to a versioned analysis recipe, not a black box. Skills are sourced from **bioSkills** (540 reference) + **ClawBio** (88 runnable); the launch wedge runs natively, the catalog grows to the full ~600 via the Skill Foundry.

See `PRODUCT.md` for the vision, `docs/command-center/design.md` for the command-center architecture, and `ROADMAP.md` for the plan.

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

**P1 figure editor built; command-center expansion in design.** The editable-Plotly
figure editor (spec = source of truth, RFC-6902 JSON-Patch, dark-IDE brand) is built
and verified in-browser against an MSW mock. The **project-first command center**
(projects sidebar + Skill Store + guided intake) is specced in
`docs/command-center/design.md`; the frontend shell is being scaffolded mock-first
(phases C1–C3). Backend (registry API, ingest/intake, Supabase persistence, Verified
runner expansion) is filed to the Codex lane (phases B1–B4).

## Reference

Full build dossier (architecture, infra, cost, first-10-days):
`C:/Users/seamegdool/Desktop/Claude code and website tips/EAMOS Web Tool/Selom/Wiki/product/selom-build-dossier.md`
