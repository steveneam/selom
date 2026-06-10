# Selom build plans — start here

Selom is a no-code multi-omics figure SaaS: a **Python FastAPI backend** runs
omics skills and emits editable **Plotly** figure specs; a **Next.js frontend**
uploads data, renders the figure, and lets the user edit it no-code.

## Two agents, two lanes (run in parallel)

| Agent | Owns | Plan |
|---|---|---|
| **Claude** | `app/frontend/` — upload UI, figure render, no-code property panel | [v2-frontend.md](./v2-frontend.md) |
| **Codex** | `app/backend/` — skill contract, runners, FastAPI, queue, export | [v2-backend.md](./v2-backend.md) |

The two lanes are decoupled by a stable HTTP contract: the frontend talks to the
backend over `NEXT_PUBLIC_API_BASE` (default `http://localhost:8000`). As long as
the request/response shapes agree, each agent can build independently.

## The contract seam (shared, do not break unilaterally)

- **Upload** → `POST /upload` returns a dataset handle.
- **Run a skill** → `POST /skills/{skill}/run` with `param_spec` → returns a
  Plotly JSON figure spec (the editable artifact).
- **Edit** → frontend mutates the figure spec via RFC-6902 JSON-Patch locally;
  the backend re-validates/persists on save.
- **Export** → `POST /figures/{id}/export` → static PNG/SVG/PDF via Kaleido.

If either side needs to change the seam, flag it in the other lane's plan first.

## Workflow

1. Each agent works its own P0 lane (frontend or backend) on its own branch.
2. Stub the seam early (backend returns a canned figure; frontend renders it) so
   both sides integrate before the real runners land.
3. Replace stubs with real implementations (UMAP runner; upload UI → real data).
4. Integrate end-to-end: upload → run `hello-UMAP` → render → edit → export.

## Status

Build-for-self phase. Commercial/licensing gates are **deferred** — see
[`../LAUNCH-GATES.md`](../LAUNCH-GATES.md). Do not let gating block the build.
