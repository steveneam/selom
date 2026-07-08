# CI — the single required check `ci`

`ci.yml` is the one workflow that gates merges to `main`. This file is its **living contract**: what
`ci` guarantees and *why it is shaped the way it is*, kept beside the workflow so the reasoning travels
with the config (a stripped "why" is how a needed permission gets deleted in a later sweep). The
one-time port audit — MEASURE → CONFORM → ENFORCE — lives in `docs/hardening-port/gate-ledger.md`
(§ M-004); this doc is for whoever edits the workflow next.

## The check

One workflow, so GitHub `needs:`-aggregation can produce **one** stable required-check name across the
monorepo (two path-filtered workflows can never both be required — a skipped required check blocks a PR
forever). Jobs:

- `changes` — dorny/paths-filter → `backend`/`frontend` booleans (path-gates the heavy jobs);
- `backend` / `frontend` — path-gated; run only when their tree (or `ci.yml`) changed;
- `hygiene` + `workflow-lint` — always run, path-independent;
- **`ci`** — `needs:` all of the above, `if: always()`; passes iff no required job **failed or was
  cancelled** (a *skipped* path-gated job counts as pass). This aggregate is the single required check;
  its name stays `ci` even if a job is later sharded.

## Why the permissions are shaped this way

The workflow default is least-privilege — `permissions: contents: read` — and **no job silently widens
it**. Every extra scope is granted at the job level, next to the step that needs it, with a comment:

- `changes` also declares **`pull-requests: read`**. On a `pull_request` event dorny/paths-filter calls
  the `pulls.listFiles` GitHub API to compute changed paths; `contents: read` alone does not grant it,
  and the call 403s (`Resource not accessible by integration`) → `changes` fails → the `ci` aggregate
  goes red. **Do not strip it.** (Fixed in PR #1, commit `24c6797`, after it shipped missing.)

**Rule for new jobs:** least-privilege is the *default*, not a finished setting. Any job that calls the
GitHub API (lists PR files, comments, reads deployments, requests an OIDC token…) must declare the
specific scope it needs at the job level. zizmor's `excessive-permissions` audit catches *too many*
permissions; **nothing automated catches *too few*** — that is caught only by the workflow running as
its real trigger event (below).

## How it is verified (what CONFORM actually means here)

A workflow change is verified only once it has **run green as its target trigger event** — for the
merge gate, an actual `pull_request` run. Local `pytest` / `tsc` / `vitest` / `zizmor`, and even a push
to a feature branch, run in a *different* context: they do not exercise the `pull_request` event, the
restricted `GITHUB_TOKEN`, or the path-gated `needs:` graph. The `contents: read` clamp that broke
paths-filter passed every local gate and was only surfaced by the first real PR run. **Before
branch-protecting `main` on `ci`, confirm `ci` has gone green on a genuine PR** (not just locally).

## What this does NOT do

- **Not the full science suite.** The backend job runs a light fast-gate closure (`pytest -m "not
  slow"`) without the omics extras, so `auto` resolves the **stub** engine for the science skills — the
  gate protects structure / contract / provenance, not real deg/gsea (see gate-ledger **DL-017**). The
  slow suite is out of the merge gate by design.
- **Not a lockfile refresh.** `uv.lock` is not regenerated here; `uv sync` (no `--locked`) resolves the
  pinned deps. A deliberate `uv lock` bump is a separate task.
