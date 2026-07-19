# Selom — Codex Backend Entry

Selom is a no-code multi-omics figure SaaS: drop an h5ad/CSV/mzML, apply analysis skills (UMAP / DEG / volcano / GSEA), get publication-ready editable figures plus auto-methods text. You own the backend.

## Start Here (read order)

1. `CODEX.md` — this file.
2. `agent_handoff/README.md` — coordination home and handoff rules.
3. `agent_handoff/CURRENT.md` — live shared state.
4. `agent_handoff/RISKS.md` — open risks and landmines.
5. `docs/pillars/plan.md` + `docs/aws-materialization/plan.md` — the current backlog
   (these supersede `plans/v2-backend.md`, which is historical P0 framing).
6. `git status --short --branch` — see the working tree before you touch it.

## Your Lane

- `app/backend` — FastAPI gateway + scverse skill runners (Python 3.12 via uv).
- Current backlog: `docs/pillars/plan.md` + `docs/aws-materialization/plan.md`
  (`plans/v2-backend.md` is historical).
- Your own section in `agent_handoff/CURRENT.md` — update it, do not overwrite Claude's.

Claude owns `app/frontend`. Cross the line only for a contract change that needs both sides, coordinated through the handoff.

## Working Rules

- **Backend-led contracts.** The API shape (endpoints, request/response schemas, job/SSE contract) is defined here. Publish contract changes in the handoff so the frontend can follow.
- **Explicit staging.** After the initial scaffold commit, never `git add -A` or `git add .` — stage named paths only, so each commit is intentional and lane-scoped.
- **End clear-safe.** At every stop, leave the tree verified (no half-applied edits), update your `CURRENT.md` section, and finish with a clear-safe line.

## Development

- uv binary: `uv` (on PATH; install from https://astral.sh/uv)
- Install: `uv sync` in `app/backend`
- Run: `uv run uvicorn main:app --reload` on `:8000`
- Python `3.12` is pinned via uv (system interpreter is `3.10` — do not use it directly).
- R 4.6 is validation-only (golden-image references), never the production runtime (ADR 0002).

## Repo structure conventions

Keep the tree clean as we grow. Full plan + rationale: `docs/repo-structure/plan.md`.
Backstopped by `app/backend/tests/test_structure_guard.py` (fails if BE rules drift).

- **Routes live in `routers/<domain>.py`** (`APIRouter`). `main.py` only does app setup +
  `include_router(...)` — **no `@app.<method>` handlers in `main.py`.** Preserve the
  deliberate lazy in-function imports.
- **Keep the flat-import style** (`import export`, `from config import settings`). Do
  **not** introduce a `src/` package — no packaging driver, ~80-file churn.
- **Split on cohesion, not line count.** A single-responsibility module stays whole even
  past a few hundred lines; split only when a file mixes multiple concerns.
- New feature = new router (and a feature *package* if >1 module), registered in one
  `include_router` line.
