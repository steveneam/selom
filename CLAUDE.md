# Selom — Claude Code Boot

Selom is a no-code multi-omics figure SaaS: drop an h5ad/CSV/mzML, apply analysis skills (UMAP / DEG / volcano / GSEA), get publication-ready editable figures plus auto-methods text.

## The Golden Rule

Two agents share this repo. Stay in your lane.

- **Claude (you) own the frontend** — `app/frontend` (Next.js + React + Plotly editor).
- **Codex owns the backend** — `app/backend` (FastAPI + scverse skill runners).

This is the default split, not a hard wall: cross the line only when a contract change needs both sides, and coordinate it through the handoff before touching the other lane.

## Coordination

`agent_handoff/README.md` is the single coordination home — read it before any cross-lane work. It owns the handoff rules; this file does not restate them. Current state lives in `agent_handoff/CURRENT.md`.

## Files

| File | What it is |
|---|---|
| `README.md` | Project overview, stack, quickstart |
| `PRODUCT.md` | Product vision and positioning |
| `ROADMAP.md` | Phased plan (P0 hello-UMAP -> v2) |
| `agent_handoff/` | Cross-agent coordination home |

## Development

**Backend** (Codex lane — for reference)
- uv binary: `C:/Users/seamegdool/.local/bin/uv.exe`
- Install: `uv sync` in `app/backend`
- Run: `uv run uvicorn main:app --reload` on port `:8000`
- Python `3.12` is pinned via uv (the system interpreter is `3.10` — do not use it directly).

**Frontend** (your lane)
- Install: `npm install --legacy-peer-deps` in `app/frontend` (react-plotly.js has stale peer-deps).
- Run: `npm run dev` on port `:3000`.

**R 4.6** is validation-only — golden-image references, never the production runtime (ADR 0002).

## Coding Guidelines

- **Think before coding** — understand the contract and the goal first.
- **Simplicity first** — smallest change that satisfies the goal.
- **Surgical changes** — touch only what the task needs; no drive-by rewrites.
- **Goal-driven verify** — confirm the change does what it should, in the running app.

## Notes

- This repo stays on **Fable 5**.
- Commercial/licensing gates are **deferred** — build now, gate before launch (see `LAUNCH-GATES.md`).
- For frontend work invoke the **ui-ux-pro-max** + **frontend-design** skills.
