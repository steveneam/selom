# Repo structure — conventions, cleanup, and refactor plan

**Status:** APPROVED for foundation work (conventions + specs + stale-doc fixes); file
moves staged, gated on owner go. · **Stamped:** 2026-06-29 (+10:00).

This is the single foundation doc for keeping Selom's file/folder structure clean,
consistent, and fast as the product keeps growing — before the AWS deploy (step 8) adds
CDK/infra files. It is the durable artifact behind the structure ratchet (see §1.4).

It was produced from a read-only survey of `app/backend`, `app/frontend`, and `docs/`,
weighed against an external "AI Codebase Optimisation Guide". The guide's *principle*
("one file = one responsibility; split when a file hoards concerns") is adopted; its
*numeric prescriptions* (a `src/` move, a hard 150-line cap, a `prompts/` folder) are
rejected as a poor fit — rationale in §4.

---

## 0. Summary / decision

| Bucket | Items | When |
|---|---|---|
| **Conventions (durable rules)** | FE/BE/docs rules + automated guard | now (§1) |
| **NOW — execution-ready** | `main.py` → `routers/`; FE lib/ feature-dir finish + lazy fixture + dead-file delete; stale-doc fixes; cruft cleanup | now / gated moves (§2) |
| **DEFERRED — specced, build later** | BE `reproduction/` package; BE `companions/` package; FE `project-workspace.tsx` hook decomposition | when that area is the active build (§3) |
| **SKIP** | `src/` move; 150-line hard cap; barrel `index.ts` files | never (§4) |
| **Step-8 linked** | wire `obs.py` (CloudWatch JSON logging) | with step 8 |

The headline: the only genuinely large file that *mixes responsibilities* is the backend
`main.py` (1481 lines, ~70 routes, no `APIRouter`). The frontend is ~80% consistent
already and does **not** have the dev-server-slowdown disease (no barrels, no eager
heavy-lib imports, Plotly already fenced behind `dynamic(ssr:false)` + a guard test).

---

## 1. Conventions (the durable rules)

Codified in `CLAUDE.md` (FE) and `CODEX.md` (BE) so both agents read them every session,
mirrored as a memory rule, and backstopped by an automated guard (§1.4).

### 1.1 Backend (`app/backend`)
- **Routes live in `routers/<domain>.py`** as `APIRouter`s. `main.py` only does app
  setup + `include_router(...)`; **no `@app.<method>` handlers in `main.py`.**
- **Keep the flat-import style** (`import export`, `from config import settings`). Do
  **not** introduce a `src/` package — there is no packaging driver and it would churn
  ~80 files (§4).
- **Preserve deliberate lazy in-function imports** (e.g. `import reproduction as R`
  inside a handler) — they keep app startup cheap and avoid import cycles.
- **Split on cohesion, not line count.** A 600–1000-line module that is *one*
  responsibility (e.g. `reproduction.py`, `methods.py`) stays whole. Split when a file
  holds *multiple* concerns (that was `main.py`'s only problem).
- **New feature = new router** (and a feature *package* if it has >1 module),
  registered in one `include_router` line.

### 1.2 Frontend (`app/frontend`)
- **Every `lib/` module lives in a feature dir.** No flat `*-api.ts` at `lib/` root.
  - Feature endpoint module → `lib/<feature>/api.ts` (matches `reproduction/`,
    `gene-sets/`).
  - Shared HTTP transport (the 7c JSON client + write-queue) → `lib/api/`.
  - UI utils → `lib/ui/`; figure domain (model/spec/patch/edits/export/styles) →
    `lib/figure/`.
- **No barrel `index.ts` re-export hubs** in `lib/` — they cause the exact eager-import
  dev-server slowdown EAMOS hit. Import from the concrete module path.
- **Heavy/WebGL libs only via `dynamic(..., { ssr:false })`** (Plotly). Keep
  `lib/figure/ssr-plotly-import.test.ts` green — it is the guard that fenced the bug
  that once 500'd every page.
- **Large data fixtures are lazy-loaded**, never eager module-scope imports (so they
  don't ship in a route's initial JS).
- **Components split on responsibility** — extract orchestration into hooks
  (`useX`) rather than capping lines. Big *presentational* files with co-located private
  subcomponents are fine.

### 1.3 Docs (`docs/`)
- `docs/README.md` is the index — every subdir is bucketed **specs** (live) /
  **records** (completed) / **parked** (on-hold), kept current.
- One home per rule. No duplicate orientation/spec docs; link, don't restate.

### 1.4 Enforcement — the ratchet (lands with the §2 moves)
Chat memory rots; the rule has to fail a check when it drifts. Two lightweight guards:
- **BE** `app/backend/tests/test_structure_guard.py` — asserts `main.py` source contains
  **no `@app.get/post/put/patch/delete`** decorators (routes must be in `routers/`).
- **FE** `app/frontend/lib/structure.guard.test.ts` (vitest) — asserts there are **no
  flat `*-api.ts` files at `lib/` root** and **no `index.ts` barrel** anywhere in `lib/`.

Both run in the existing fast gates (`pytest -m "not slow"`, `vitest`), so a drift fails
CI/local before it lands. This is the automated backstop; CLAUDE.md/CODEX.md are the
in-context rule; the memory file is the portable habit. (The Ratchet: route to ONE home
per layer, surface in a lean index.)

---

## 2. NOW — execution-ready

### 2A. Backend: `main.py` (1481 lines, ~70 routes) → `routers/`
**Highest value, lowest risk.** Touches only *new* files + shrinks `main.py`; **zero**
existing module/test/frontend change because route paths stay identical (the contract).

Router-split map (paths preserved exactly):

| Router file | Routes |
|---|---|
| `routers/system.py` | `/health`, `/ready` |
| `routers/skills.py` | `GET /skills`, `GET /skills/{id}`, `POST /skills/{id}/run`, `/jobs`, `/run-dataset`, `/jobs-dataset` |
| `routers/jobs.py` | `GET /jobs/{id}`, `/jobs/{id}/events`, `/jobs/{id}/result` |
| `routers/data.py` | `POST /data/inspect`, `/data/combine`, `GET /artifacts/{id}`, `/artifacts/{id}/table` |
| `routers/papers.py` | `GET /papers`, `/papers/{slug}`, `/scorecard`, `/methods`, `/legends` |
| `routers/reproduction.py` | `POST /papers/{id}/reproduce`, `/assess-data`, `GET /reproduction-runs/{id}`, `/events`, `POST /papers/route`, `/papers/extract` |
| `routers/litsynth.py` | `POST /methods/compose`, `GET /citations/search`, `/citations/by-doi`, `GET /papers/metadata/by-doi` |
| `routers/gene_sets.py` | `GET /gene-sets`, `POST /gene-sets/compile`, `GET /gene-sets/{id}` |
| `routers/extract.py` | `POST /extract/chart` |
| `routers/figures.py` | `/figures/export/presets`, `/figures/export`, `/figures/styles`, `/figures/style/apply`, `/figures` CRUD, `/figures/{id}` |
| `routers/library.py` | `/projects*`, `/uploads/*`, `/datasets*`, `/import/local-state`, `/workspace*`, `/skill-installs` |

Shared homes for what `main.py` holds today:
- `routers/deps.py` — FastAPI `Depends` providers (`_uploads_repo`, `_library_repo`).
- `routers/_run.py` — the run service (`_execute_skill_run` + helpers), shared by
  `skills.py` and `reproduction.py`.
- Pydantic request models move **with their owning router**.

**Two gotchas the split MUST respect:**
1. **Route order:** the static `/figures/export|styles|style/apply` routes must register
   **before** `/figures/{figure_id}` or the param route shadows them. Keep them in one
   `figures.py` with static declared first (or `include_router` static before CRUD).
2. **Keep the lazy in-function imports** in-function — do not hoist to module top.

Target trimmed `main.py`: **~70–110 lines.** Blast radius: ~1 edited (`main.py`) + 11 new
routers + 2 shared modules. **No existing tests/modules/frontend change.**

### 2B. Frontend
**Phase 0 (1-file-ish each, removes ship weight):**
- **Lazy-load** `lib/reproduction/fixture.ts` (2342 lines / 67 KB) — move its import into
  the offline-fallback `.catch()` (`await import("./fixture")`) so it leaves the
  `/reproduction` route's initial JS, fetched only when the backend is down.
- **Delete dead files:** `components/ui/separator.tsx`, `components/ui/tooltip.tsx` (zero
  usages); drop their unused `@radix-ui/react-separator` + `@radix-ui/react-tooltip` deps.

**Phase 1 (finish the 80%-done feature-dir convention — alias-safe find-replace):**

| Flat file | → | Importers |
|---|---|---|
| `plotly-edits.ts`, `export-api.ts`, `extract-api.ts`, `styles-api.ts` | `lib/figure/` (export/styles) · `lib/extract/api.ts` | 1 each |
| `figure-model.ts` (+ test) | `lib/figure/` | 8 |
| `patch.ts` | `lib/figure/` | 18 |
| `skills-api.ts` (+ test) | `lib/skills/api.ts` | 23 |
| `figure-spec.ts` | `lib/figure/` | 44 |
| `cn.ts` | `lib/ui/cn.ts` | 47 |

~143 import edits, **all `@/lib/*` path-alias rewrites** (no relative-path math). Verify
with `tsc --noEmit` + `vitest run` (they catch any miss at compile time). One commit per
cluster for clean blame. Entirely Claude lane — no Codex coordination.

> Note: `lib/api/` (shared transport) vs the flat `*-api.ts` (feature endpoints) is a
> *naming collision across two layers*, **not** duplication. `skills-api.ts` is multipart
> upload and is **not** superseded by the 7c JSON client.

### 2C. Docs + stale-doc fixes + cleanup
Stale top-level docs actively mislead every new session — highest ROI for agent speed:
- **README.md** — Stack/infra (was Supabase/R2/Redis) → AWS; Status (was "P1 built /
  command-center in design") → step 7c shipped, step 8 next, pillars complete. *(done)*
- **ROADMAP.md** — superseded banner → `docs/pillars/plan.md` + `docs/aws-materialization/plan.md`; P0–v2 marked historical. *(done)*
- **CODEX.md** — fix "plan of record" pointer off `plans/v2-backend.md`. *(done)*
- **plans/README.md + v2-*.md** — superseded banners. *(done)*
- **docs/README.md** — new index for the 72-file tree. *(done)*
- *(gated with moves)* resolve `docs/integrations.md` ↔ `docs/aws-materialization/integrations.md`
  name collision (rename the old one to `external-integrations.md`); merge
  `AGENTS.md` ≈ `.context/READ-ME-FIRST.md`; bucket completed records under `docs/records/`.

Cleanup: delete the empty gitignored root `node_modules/` (`.vite` only — local cruft).

### 2D. Structure guard
Build the two guard tests in §1.4 **with the moves** so they enforce the new target state.

---

## 3. DEFERRED — specced now, build when that area is active

The owner directive: spec these now so the foundation is solid even though we don't build
them yet. Do each when its area is the active build (so the import churn lands where
someone is already working), not on the deploy boundary.

### 3A. Backend `reproduction/` package
**What:** fold the flat `reproduction*.py` family into a package.
```
reproduction/
  __init__.py        # re-exports the public surface of today's reproduction.py
  core.py            # (was reproduction.py) models + scoring spine
  drive.py           # (was reproduction_drive.py)
  runs.py            # (was reproduction_runs.py)
  fixtures.py        # (was reproduction_fixtures.py)
  guards.py          # (was reproduction_guards.py)  ← confirm live first
  diagnose.py        # (was reproduction_diagnose.py)  dev/diagnostic
  papers/
    rpgrip1.py jev.py hani.py dorgau.py   # per-paper ledgers
```
**Why deferred, not skipped:** correct domain boundary, but wide churn in Codex's files.
**Cost-control:** a **re-exporting `__init__.py`** keeps the ~14 `import reproduction as R`
consumers unchanged; only ~10 test files + ~6 sites change (`papers_api._LEDGER_MODULES`
string names → `"reproduction.papers.rpgrip1"`; sibling `from reproduction_drive import`
→ `from reproduction.drive import`). No deploy payoff → do it when reproduction is the
active build area.
**Pre-req checks:** confirm `reproduction_guards.py` is live (only its own test imports it
today) and decide whether `reproduction_dorgau.py` (not in the ledger registry) and the
`diagnose.py`/`skill_gaps.py` diagnostic cluster stay, move to a `scripts/`/`dev/` home, or
retire — Codex's call.

### 3B. Backend `companions/` package
**What:** group the figure-artifact builders `methods.py` + `legends.py` +
`provenance.py` + `guardrails.py` into `companions/` (they're called together in
`_execute_skill_run`/`jobs.queue` to build the "every figure ships with
methods+legend+provenance+guardrails" bundle).
**Cost:** ~6 import sites (`methods` is also imported by `litsynth/*` + `reproduction`).
Bundle this with 3A. `export.py` optionally folds into `figures/` if doing the figures
grouping; otherwise leave flat.

### 3C. Frontend `project-workspace.tsx` decomposition
**What:** the 1384-line core editor orchestrator already delegates rendering to panel
subcomponents; the bloat is **state + orchestration** (~20 `useState`, 12 `useEffect`,
~20 handlers). Extract cohesive hooks:
- `useFigureRun` — `runFlow` / `rerunFigure` / `runSweep` / `rerunFigureWithParams` +
  `running` / `error`.
- `useWorkspaceView` — `view` / `activeFigureId` / `activeDatasetId` / `compareIds`
  routing.
- `useFigureCrud` — open/delete figure & dataset.
**Why deferred:** highest maintenance value but it's the core editor with interdependent
state → its own focused task, leaning on existing tests + a real-browser smoke pass. Also
shrinks `next dev --webpack` HMR recompile surface. `workrail.tsx` (828) is **fine** — a
cohesive feature file with co-located private subcomponents; do **not** split it.

---

## 4. SKIP — with rationale

- **`src/` package move** — the codebase uses a flat-import style across ~80 files (incl.
  every test, `alembic/env.py`, `scripts/*`, the documented `PYTHONPATH` invocation). A
  `src/` move either rewrites all of them (massive, risky, Codex-lane, zero benefit) or
  keeps `src/` on `sys.path` (buys nothing). No packaging/distribution driver. Worst
  value/risk trade on the table.
- **150-line hard cap** — would shard cohesive single-responsibility modules
  (`reproduction.py` 1060, `methods.py` 750, `paper_metadata.py` 628, per-paper ledgers)
  into `_part1/_part2` shards that read *worse*. Keep ~150–300 lines as a *smell to look*,
  never a gate. (TSX is verbose; 300–600-line components are normal.)
- **Barrel `index.ts` re-export hubs** — would manufacture the very eager-import
  dev-server slowdown EAMOS warned about. The repo has zero today; keep it that way.

---

## 5. Execution order, verification, rollback

**Order:** (done now) conventions + foundation docs + stale-doc fixes + cruft → (gated on
go) FE Phase 0 → FE Phase 1 (one commit per cluster) → BE `main.py` router split → §2D
guards → verify → handoff.

**Verify:**
- FE: `npm run -s typecheck` (tsc) + eslint + `vitest run` + a real-browser smoke
  (`next dev --webpack`) per [[full-app-smoke-test-before-handoff]].
- BE: fast gate `pytest -m "not slow"` + `ruff check` via the uv-3.12 PY + PYTHONPATH
  (not `uv run` — EDR) per [[selom-backend-python-exec]].

**Rollback:** each logical change is its own lane-scoped commit (named-path staging, no
`git add -A`), so any step is revertible in isolation. The router split is the one Codex-
lane code change — coordinate via the handoff; it's mechanical and contract-frozen.

**Not in this effort but linked:** wire `obs.py` (CloudWatch JSON logging) during step 8;
it's the one structure item with real deploy value.
