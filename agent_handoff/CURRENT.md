# Selom — CURRENT (Live State)

> **LIVE STATE ONLY.** The current state of the two-agent build. History lives in
> each agent's rolling log, not here. This file is **replaced, never stacked** —
> update at MAJOR boundaries only (rule 9 in `agent_handoff/README.md`).

_Last updated: 2026-06-10 20:52 +10:00 · synced from the scaffolding session (vault)_

**Model:** stay on **Fable 5** for all Selom work — Selom carries no biology/security
flag. Only *reading the EAMOS build repo* escalates a session to Opus, and that
source is not needed here. Do not switch to Opus for Selom.

## Active Status

| Agent | Role | Lane | Status |
|---|---|---|---|
| Claude | Frontend (UI/design/product copy) | `app/frontend` + `plans/v2-frontend.md` | IDLE — skeleton scaffolded + committed; P0 not started |
| Codex | Backend (APIs/skill runners/data/tests) | `app/backend` + `plans/v2-backend.md` | IDLE — skeleton scaffolded + committed; P0 not started |

Roles are explicit; any swap is written here before work proceeds.

## Log Edit-Lock

UNLOCKED

## Shared File Locks

None held.

## Cross-Agent Requests

- **[owner action — GitHub not connected yet]** Local commit `4ccb6b6` on `main` is
  **not pushed**; no remote exists. Owner runs `gh auth login`, then
  `gh repo create selom --private --source . --remote origin --push`. Until then the
  repo is **local-only** (this is why it isn't visible on GitHub yet).

## Current State

- **Scaffold complete and committed:** git repo at `D:/selom`, branch `main`, commit
  **`4ccb6b6`** ("chore: scaffold Selom build repo (skeleton + agent workflow)"),
  40 files, clean tree. **Local only — not yet on GitHub.** Identity is set LOCALLY
  to `Steven <mactechdish@gmail.com>` (correct it if that's not the intended GitHub
  identity).
- **Skeletons that ALREADY EXIST — do NOT re-scaffold:**
  - **Backend** (`app/backend`): FastAPI `main.py` (`GET /skills/{id}`,
    `POST /skills/{id}/run`, `GET /health`) + `skills/contract.py` (SkillSpec loader)
    + `skills/umap_scrna/` = `skill.json`, `run.py` (offline **STUB** — returns a
    valid Plotly dict with zero heavy deps; **verified runs on Python 3.10**),
    `run_scanpy.py` (real Scanpy engine, lazy import). `pyproject.toml` = light core
    deps + an `[omics]` extra for the scverse stack. `.python-version` = 3.12.
    `tests/test_contract.py`.
  - **Frontend** (`app/frontend`): Next.js 16 / React 19 / TS / Tailwind 4 shell —
    `app/page.tsx` (file upload → `POST /api/skills/umap_scrna/run` → render via
    `react-plotly.js`), `layout.tsx` (Inter via next/font), `next.config.ts`
    (`/api/*` → `:8000` proxy), tsconfig/postcss/globals.
- **NOT done (by scope):** no installs (`uv sync` / `npm install` not run), no cloud
  (`.env` + `.mcp.json` are TODO placeholders), no Docker, no push. P0 hello-UMAP is
  not wired end-to-end yet.
- **Next milestone = P0 hello-UMAP:** install deps → boot both servers → swap the
  stub for the real Scanpy engine → upload `demo.h5ad` → an editable Plotly UMAP
  renders in the browser.

## Claude — Last Task & Resume

- **Last:** frontend skeleton scaffolded (`app/page.tsx` upload→render against the P0 contract).
- **Next:** `cd app/frontend && npm install --legacy-peer-deps && npm run dev`; confirm
  the page renders the backend's stub UMAP; then build the no-code figure editor
  (custom shadcn/ui panel → RFC-6902 JSON-Patch; `react-chart-editor` is dead, RISKS #1).
  Invoke `ui-ux-pro-max` + `frontend-design`.
- **Resume:**
  ```
  # Resume · 2026-06-10 20:52 +10:00 · Selom · Claude (frontend)
  Selom build repo D:/selom. CLAUDE.md auto-loads. Read agent_handoff/README.md (protocol) + CURRENT.md (this) + plans/v2-frontend.md.
  Delta: scaffold committed 4ccb6b6 (main, local-only); FE shell + BE stub-UMAP skeleton exist; no installs/push yet.
  Next: npm install --legacy-peer-deps + npm run dev → verify stub UMAP renders → build the JSON-Patch figure editor. Stay on Fable 5. End clear-safe.
  ```

## Codex — Last Task & Resume

- **Last:** backend skeleton scaffolded (FastAPI + SkillSpec contract + stub/real umap).
- **Next:** `cd app/backend && uv python install 3.12 && uv sync && uv run uvicorn main:app --reload`;
  then `uv sync --extra omics` + point the `umap_scrna` skill at `run_scanpy.py` for the
  real P0 figure; then Supabase + arq async queue + Kaleido export (RISKS #2/#5).
  Explicit staging only (never `git add -A` after the initial commit).
- **Resume:**
  ```
  # Resume · 2026-06-10 20:52 +10:00 · Selom · Codex (backend)
  Selom build repo D:/selom. CODEX.md auto-loads. Read agent_handoff/README.md + CURRENT.md + plans/v2-backend.md + git status.
  Delta: scaffold committed 4ccb6b6 (main, local-only); BE skeleton exists (stub runs, real scanpy behind [omics]); no installs/push yet.
  Next: uv sync → swap stub→real scanpy for P0 → async queue. Stay on Fable 5. End clear-safe.
  ```
