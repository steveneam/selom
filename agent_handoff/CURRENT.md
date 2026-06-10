# Selom — CURRENT (Live State)

> **LIVE STATE ONLY.** This file holds the *current* state of the two-agent build.
> History lives in `PROGRESS/` and each agent's rolling log — NOT here. This file
> is **replaced, never stacked**: update it at MAJOR boundaries only (rule 9 in
> `agent_handoff/README.md`).

_Last updated: 2026-06-10 20:46 +10:00_

## Active Status

Per-agent heartbeat. Record current role, lane, and what is in flight.

| Agent | Role | Lane | Status |
|---|---|---|---|
| Claude | Frontend (UI/design/product copy) | `app/frontend` + `plans/v2-frontend.md` | IDLE — scaffold complete, awaiting P0 start |
| Codex | Backend (APIs/skill runners/data/tests) | `app/backend` + `plans/v2-backend.md` | IDLE — scaffold complete, awaiting P0 start |

Roles are explicit; any swap is written here before work proceeds.

## Log Edit-Lock

UNLOCKED

> Single line. Claim it (set to `LOCKED by <agent> @ <real-clock stamp>`) before
> editing any handoff/log doc; set back to `UNLOCKED` when done.

## Shared File Locks

None held.

> Required for `CLAUDE.md`, `CODEX.md`, `agent_handoff/*`, `ROADMAP.md`,
> `plans/README.md`, and the FE<->BE contract file. Format:
> `<file> — LOCKED by <agent> @ <stamp>`.

## Cross-Agent Requests

None open.

> Frontend requests backend/contract changes here (contract changes are
> backend-led, rule 5). Format: `<from> -> <to>: <request> [<stamp>]`.

## Current State

- Repo skeleton at `D:/selom` is in place: `app/`, `agent_handoff/`, `plans/`,
  `docs/`, `.context/`, `.claude/`.
- Agent coordination workflow is wired: `agent_handoff/README.md` (protocol),
  this `CURRENT.md`, `RISKS.md`, `DECISIONS.md`.
- **Scaffold complete.** No application code written yet.
- **Next milestone = P0 hello-UMAP:** upload `demo.h5ad` -> backend runs Scanpy
  UMAP -> returns Plotly spec -> frontend renders an interactive, editable Plotly
  UMAP in the browser.

## Claude — Last Task & Resume

- **Last task:** none yet (scaffold handed over).
- **Next:** scaffold `app/frontend` (Next.js 16 / React 19), wire the upload ->
  render path against the backend P0 contract. Invoke `ui-ux-pro-max` +
  `frontend-design`. Install `react-plotly.js` with `--legacy-peer-deps` (RISKS #3).
- **Resume:** see `agent_handoff/README.md` resume-prompt format.

## Codex — Last Task & Resume

- **Last task:** none yet (scaffold handed over).
- **Next:** scaffold `app/backend` (FastAPI), implement the `umap_scrna` skill
  runner + `/skills/umap_scrna/run` endpoint returning a Plotly spec for P0.
- **Resume:** see `agent_handoff/README.md` resume-prompt format.
