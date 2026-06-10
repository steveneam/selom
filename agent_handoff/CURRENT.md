# Selom — CURRENT (Live State)

> **LIVE STATE ONLY.** The current state of the two-agent build. History lives in
> each agent's rolling log, not here. This file is **replaced, never stacked** —
> update at MAJOR boundaries only (rule 9 in `agent_handoff/README.md`).

_Last updated: 2026-06-11 01:41 +10:00 · Claude — command-center expansion designed + docs locked + FE shell scaffolded (mock-first); `tsc` + `next build` clean. Committed `afaafd2` + **pushed**; `main` ↔ `origin/main` in sync._

**Model:** stay on **Fable 5** for all Selom work — Selom carries no biology/security
flag. Only *reading the EAMOS build repo* escalates a session to Opus, and that
source is not needed here. Do not switch to Opus for Selom.

## Active Status

| Agent | Role | Lane | Status |
|---|---|---|---|
| Claude | Frontend (UI/design/product copy) | `app/frontend` + `plans/v2-frontend.md` | IDLE (clear-safe) — **command-center expansion designed + docs locked + FE shell scaffolded** mock-first (`docs/command-center/design.md`; Home dashboard + Skill Store + project Overview/Data/Workbench/Figure; figure editor reused). `tsc` + `next build` clean. Committed `afaafd2` + pushed; `main` ↔ `origin/main` in sync. |
| Codex | Backend (APIs/skill runners/data/tests) | `app/backend` + `plans/v2-backend.md` | IDLE — skeleton scaffolded + committed; P0 not started |

Roles are explicit; any swap is written here before work proceeds.

## Log Edit-Lock

UNLOCKED

## Shared File Locks

None held.

## Cross-Agent Requests

- **GitHub: connected ✓** Pushed to **github.com/steveneam/selom** (private); `main` ↔
  `origin/main` in sync as of 2026-06-11 01:41 +10:00. Latest: `afaafd2` (command-center
  scaffold + design) atop `e63f38b`/`5c4a1fd` (figure editor). Commit identity is local
  `Steven <mactechdish@gmail.com>` — adjust if GitHub commit attribution should differ.

- **FE → Codex (await Codex return, ~2026-06-11):** _Update 2026-06-10 22:44 — FE is no longer
  blocked: an MSW mock of `POST /api/skills/umap_scrna/run` now renders the stub UMAP end-to-end
  in-browser with :8000 DOWN (`npm run dev:mock`, verified via chrome-devtools). These asks remain
  open for LIVE integration._ Three asks, in priority order:
  1. **Boot the backend stub** (`uv python install 3.12` → `uv sync` → `uvicorn main:app
     --reload` on :8000). The FE proxies `/api/* → :8000`; once the stub `umap_scrna/run`
     responds, the P0 render path is verifiable end-to-end.
  2. **Resolve a contract ambiguity (backend-led, rule 5).** `plans/v2-frontend.md` P0 describes
     a **two-step** flow (`POST /upload` → dataset handle → `POST /skills/{id}/run`), but the
     scaffolded `app/frontend/app/page.tsx` does a **one-shot** multipart POST of the file
     straight to `/skills/umap_scrna/run` (form field `matrix`). The current `main.py` stub
     needs to match whichever contract we pick. **Request:** confirm the canonical P0 contract
     (one-shot vs upload-then-run) and align the stub; FE will conform to it.
  3. **FYI — no backend action needed:** FE deps were re-pinned. `plotly.js@^2.37` did not exist
     (install hard-failed); bumped to `plotly.js@^3.6` + `react-plotly.js@^3.0` (now natively
     supports React 19, so `--legacy-peer-deps` is no longer strictly required). This is FE-lane
     only — the wire format (Plotly `{data, layout}` JSON) is unchanged, so the contract is
     unaffected. Worth updating RISKS #1/#3 (Codex/shared) at some point.

- **FE → Codex (NEW 2026-06-11 01:03 — command-center backend; full spec in `docs/command-center/design.md` §3–§9):**
  The frontend is building the project-first command center **mock-first** (no backend dependency to
  build). When the backend lane resumes, these are the new contracts to own/finalize — all **additive**;
  the figure wire format (Plotly `{data, layout}` JSON) is unchanged:
  1. **Skill registry API (B1).** `GET /skills` (filterable list of `SkillCatalogEntry`) +
     `GET /skills/{id}` (detail/SkillSpec). Seed from the ingested **ClawBio `skills/catalog.json`**
     (maps ~1:1) + **bioSkills** categories/`SKILL.md` frontmatter. The full ~600-skill catalog is
     browsable; each entry carries `tier` (verified|community), `engine`, `status`, `input_formats`,
     `provenance`, `license`. Shape = design §3.1.
  2. **Ingest + intake (B2).** `POST /upload` returns a dataset handle **plus** an ingest/QC report
     (detected modality, n_obs/n_var, guardrail flags). `POST /intake` takes questionnaire answers +
     dataset shape → schema-constrained **`IntakeProposal`** (cleaning steps + 1–3 proposed skills with
     pre-filled params + rationale/confidence) via the **shared AI gateway**. LLM proposes, never
     auto-runs. Shapes = design §4.3 / §7.
  3. **Verified runner expansion (B3).** Generalize `POST /skills/{id}/run` beyond `umap_scrna` to any
     Verified skill; async (arq) for heavy ones. **Skill Foundry (manual):** hand-port the wedge
     (~6–8: UMAP/cluster/DEG/volcano/heatmap/enrichment) + selected ClawBio runnable skills into the
     SkillSpec contract, each emitting an editable Plotly spec + provenance/golden-image test.
  4. **Supabase persistence (B4).** Tables = design §5 (`projects`, `datasets`, `skill_installs`,
     `intake_sessions`, `figures`, `figure_history`, `skill_catalog`; RLS by owner). FE persists through
     a `ProjectStore` interface (localStorage now) designed to match this schema, so the swap is a
     backend-impl change, not a FE rewrite.
  5. **Skill execution toolchain (design §6.5).** What we download/install to actually test+run skills:
     **(A)** catalog ingest — `git clone --depth 1` ClawBio + bioSkills, parse `catalog.json` + `SKILL.md`
     → seed manifest (cheap, do-now, an `scripts/ingest-catalog` job). **(B)** Verified runners — the
     existing `[omics]` extra (`uv sync --extra omics`: scverse + plotly/kaleido). **(C)** ClawBio runnable
     — `pip install clawbio` + **Miniforge/mamba** for per-skill `environment.yml` + bioconda. **(D)**
     bioSkills long tail — bioconda CLI toolchain (samtools/bcftools/STAR/salmon/GATK4/… + Snakemake/
     Nextflow) consumed via the Skill Foundry. **(E)** Community sandbox — Docker + mamba images +
     network policy + compute (v2, deferred). A+B are immediate; C is the contained next step; D/E grow
     over time.
  No action needed now — FE is unblocked and mock-first; this is the spec to build against when the
  backend lane resumes. North star (owner): grow runnable coverage to the full 500+ via the Skill
  Foundry (manual now → LLM-assisted = the v2 Extract-Skills moat).

## Current State

- **Scaffold complete and committed:** git repo at `D:/selom`, branch `main`, commit
  **`4ccb6b6`** ("chore: scaffold Selom build repo (skeleton + agent workflow)"),
  40 files, clean tree. **Pushed to github.com/steveneam/selom (private); main ↔ origin/main in sync.** Identity is set LOCALLY
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

- **Last:** Designed + documented the **command-center expansion** and scaffolded its **frontend shell**
  (mock-first). Docs (keystone): `docs/command-center/design.md` — research synthesis (bioSkills 540 +
  ClawBio 88 + Hermes gateway), project-first IDE architecture, Skill Store catalog model (hybrid-tiered
  Verified/Community), guided-intake flow, auto-clean/QC, **execution toolchain §6.5** (what to install to
  run skills: clone+ingest → `[omics]` runners → `clawbio`+Miniforge → bioconda long tail → Docker
  sandbox), and phased plan **C1–C3 (FE) / B1–B4 (BE)**. Framework locked into PRODUCT.md, README.md,
  ROADMAP.md (C/B phases + toolchain), plans/v2-frontend.md (C1–C3), and CURRENT.md → Cross-Agent Requests
  (backend spec for Codex). Memory: added `selom-command-center-architecture`. North star (owner): all 500+
  skills runnable via the Skill Foundry (manual now → LLM-assisted = v2 Extract-Skills moat).
  FE scaffold (`app/frontend`, mock-first, **no backend dependency**):
  - **Data layer** — `lib/projects/{types,store}.ts` (localStorage `ProjectStore` via `useSyncExternalStore`,
    schema-aligned to the planned Supabase tables), `lib/catalog/{types,seed}.ts` (~32-skill seed standing in
    for the full ~600), `lib/intake/mock.ts` (adaptive questionnaire + deterministic `IntakeProposal` + QC).
  - **Shell** — `components/shell/{app-shell,sidebar}.tsx` (project-first rail + header; wraps every route via
    root `layout.tsx`), `components/ui/badge.tsx`.
  - **Screens** — `app/page.tsx` (Home dashboard, replaces the old single-surface flow), `app/store/page.tsx`
    + `components/store/*` (Skill Store: browse/filter/install, Verified/Community tiers, honest coverage
    meter), `app/p/[id]/page.tsx` + `components/project/*` (workspace: Overview/Data/Workbench/Figure),
    `components/intake/*` (questionnaire + proposal plan). The existing figure editor is **reused unchanged**
    as Project ▸ Figure (run a skill → `runSkill` MSW mock → editable Plotly figure).
  **Verified:** `tsc --noEmit` clean + **`next build` clean** (all 4 routes compile/type-check/prerender).
  Live browser click-through was blocked by a stale Chrome profile lock (env, not code); mock dev server is up
  on **:3001** (`npm run dev:mock`; :3000 already in use). **Committed `afaafd2` + pushed**; `main` ↔
  `origin/main` in sync (the push also carried `e63f38b`/`5c4a1fd`). Removed orphaned
  `components/app/top-bar.tsx` + `components/upload/upload-hero.tsx` (superseded by the new shell).
- **Next:** browser-verify the C1–C3 flows once a clean Chrome is available; C2/C3 polish (registry-driven
  Store via `GET /skills` when B1 lands; wire intake to live `POST /intake` at B2).
- **Resume:**
  ```
  # Resume · 2026-06-11 01:41 +10:00 · Selom · Claude (frontend)
  Selom build repo D:/selom. CLAUDE.md auto-loads. Read agent_handoff/README.md + CURRENT.md (this) + docs/command-center/design.md + plans/v2-frontend.md + ROADMAP.md (C/B phases).
  Delta: command-center expansion DESIGNED + DOCS LOCKED + FE shell SCAFFOLDED mock-first (project-first IDE: sidebar projects + Home dashboard + Skill Store browse/install + guided intake + project Overview/Data/Workbench/Figure; existing figure editor reused as the Figure tab). Data layer = localStorage ProjectStore + ~32-skill catalog seed + deterministic intake mock, all schema-aligned for Supabase. tsc + next build CLEAN. Committed afaafd2 + PUSHED (main↔origin in sync). Backend (registry API, ingest/intake, runners, Supabase) filed to Codex in CURRENT.md → Cross-Agent Requests.
  Next: browser-verify C1–C3 (blocked this session by a Chrome profile lock; dev:mock on :3001); then registry-driven Store + live intake when B1/B2 land. Stay on Fable 5. End clear-safe.
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
