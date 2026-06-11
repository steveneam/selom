# Selom — CURRENT (Live State)

> **LIVE STATE ONLY.** The current state of the two-agent build. History lives in
> each agent's rolling log, not here. This file is **replaced, never stacked** —
> update at MAJOR boundaries only (rule 9 in `agent_handoff/README.md`).

_Last updated: 2026-06-11 23:25 +10:00 · Claude (acting FE+BE) — **B1 COMPLETE: the P0 hello-UMAP gate is CLOSED end-to-end.** Real scanpy engine wired behind the one-shot `POST /skills/umap_scrna/run`; pbmc3k `demo.h5ad` fixture generated; verified in-browser (upload → run → real editable Plotly UMAP, 11 Leiden clusters / ~2700 cells, MSW off, live :8000). Committed in scoped commits: `feat(backend:)` `6e37829`, `feat(frontend:)` `396ca66`, `docs:` `680557a` (charter + decisions #5–#8). NOT yet pushed. Two contract asks resolved (one-shot confirmed; backend booted on user-managed py3.12). New risk #8 (Next proxy 10MB body cap) found + fixed for dev. Wiki agent still to mirror the charter + file deep ADRs 0004–0007. Prior boundary (22:02): owner APPROVED the build charter → `docs/build-charter.md`; 5 [DECISION]s ratified._

**Model:** stay on **Fable 5** for all Selom work — Selom carries no biology/security
flag. Only *reading the EAMOS build repo* escalates a session to Opus, and that
source is not needed here. Do not switch to Opus for Selom.

## Active Status

| Agent | Role | Lane | Status |
|---|---|---|---|
| Claude | **Frontend + Backend (acting)** — UI/design/product copy **and** APIs/skill runners/data/tests | `app/frontend` + `app/backend` + both plans | IDLE (clear-safe) — **B1 DONE: P0 hello-UMAP gate CLOSED end-to-end** (real scanpy UMAP renders in-browser from an uploaded `.h5ad`, live :8000). Committed (not pushed): BE `6e37829`, FE `396ca66`, docs `680557a`. Charter `docs/build-charter.md` (B0–B9); decisions #5–#8 ratified. **Next bucket = B2 (Steven's skills) — not started.** |
| Codex | Backend (APIs/skill runners/data/tests) | `app/backend` + `plans/v2-backend.md` | **AWAY** (busy on another project). Backend role **temporarily covered by Claude** as of 2026-06-11 22:10. B1 backend done by Claude in the interim (see `## Codex` section). May reclaim at any time — state is drop-in-ready; review the arq #6 lock + the B1 commit on return. |

Roles are explicit; any swap is written here before work proceeds.

> **Role swap (2026-06-11 22:10 +10:00).** Codex is away on another project; **Claude is acting backend owner** in addition to frontend, so a single agent now drives both lanes. **Takeover discipline (so Codex or any new agent can drop in cleanly):** (1) keep the `## Codex — Last Task & Resume` section accurate to *true* backend state — what's done, the exact next command, the resume pointer; (2) **explicit git staging only** — never `git add -A`; stage `app/backend/**` and `app/frontend/**` in **separate commits** with `feat(backend:)` / `feat(frontend:)` scopes so lane history stays cleanly attributable; (3) keep `plans/v2-backend.md` current as the BE backlog; (4) honour the backend-lane decisions already locked (arq #6) until Codex reclaims and reviews. The disjoint-lane locks in `README.md` still apply — when wearing the BE hat I follow the BE rules.

## Log Edit-Lock

UNLOCKED

## Shared File Locks

None held.

## Cross-Agent Requests

> **Coverage note (2026-06-11 22:10):** while Codex is away, the **FE → Codex** asks below are now **Claude's own backend backlog** (acting BE) — I action them in-lane rather than waiting. They're kept here verbatim as the running BE contract/spec so Codex can read the full thread and reclaim cleanly. No new cross-lane asks are needed while one agent holds both lanes.

- **GitHub: connected ✓** Pushed to **github.com/steveneam/selom** (private); `main` ↔
  `origin/main` in sync as of 2026-06-11 01:41 +10:00. Latest: `afaafd2` (command-center
  scaffold + design) atop `e63f38b`/`5c4a1fd` (figure editor). Commit identity is local
  `Steven <mactechdish@gmail.com>` — adjust if GitHub commit attribution should differ.

- **FE → Codex — ✅ RESOLVED 2026-06-11 23:25 (B1, Claude acting BE):** asks 1 & 2 below are done.
  1. **✅ Backend booted + real engine wired.** `uv python install 3.12` + `uv sync --extra scrna`
     (light scRNA path, no scvi-tools/torch) on the user-managed py3.12; `uvicorn main:app` on :8000.
     `run_scanpy.py` now runs the real pipeline behind `umap_scrna/run` and returns an editable
     Plotly spec. Verified: real 2700-point / 11-cluster UMAP, direct and through the FE proxy.
  2. **✅ Canonical P0 contract = ONE-SHOT** multipart `POST /skills/{id}/run` (field `matrix` +
     params as query). The two-step upload-then-run idea is dropped for P0; `plans/v2-frontend.md`
     should be updated to match. `run.py` dispatches stub vs. real via `SELOM_UMAP_ENGINE`.
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

- **FE → Codex (NEW 2026-06-11 21:56 — decision ratified, BE-lane confirm needed):** the owner directed
  ratifying all 5 pending vault `[DECISION]`s. One is backend-lane: **DECISIONS.md #6 — async job queue =
  `arq` + Redis (not Dramatiq).** It's locked to the vault's recommended default (asyncio-native, matches the
  FastAPI stack + every manifest/schematic); recorded by FE per the owner directive so it isn't left
  un-ratified. **Codex: confirm this, or supersede-by-append in `DECISIONS.md` if a Dramatiq-specific need
  surfaces** when the queue goes load-bearing (charter Bucket B3 / ledger P2). No action needed before then.
  _Update 2026-06-11 22:10 — Codex away; Claude (acting BE) proceeds on **arq** as locked; left for Codex to review on reclaim._

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
- **P0 hello-UMAP = DONE (B1, 2026-06-11).** Backend venv built (`uv sync --extra scrna`
  on user-managed py3.12); `run_scanpy.py` real engine wired behind one-shot
  `POST /skills/umap_scrna/run`; `scripts/make_demo.py` writes the pbmc3k `demo.h5ad`
  fixture (gitignored, ~21MB). Verified in a real browser: upload → run UMAP → editable
  Plotly figure (11 Leiden clusters / ~2700 cells) renders against live :8000 (MSW off).
  Backend contract test green (`python -m pytest`, stub-pinned). FE proxy body cap raised
  to 512mb (RISKS #8). Committed `6e37829`/`396ca66`/`680557a` — **not pushed yet.**
- **Still NOT done (by scope):** no cloud (`.env` + `.mcp.json` are TODO placeholders),
  no Docker, no Supabase/arq, no Kaleido export, no push. Those are later buckets.
- **Next milestone = B2 (Steven's real skills)** then B3 (jobs/queue) / B4 (publish-confidence:
  guardrails / methods-text / Kaleido export). See `docs/build-charter.md`.

## Claude — Last Task & Resume

- **Last (2026-06-11 21:56):** Re-oriented from the research vault (Me.md · Business/selom.md · Selom/Wiki
  semantic-index + selom-build-kickoff + build-ledger + SESSION). Confirmed the staged goal (personal tool →
  EAMOS engine → SaaS) and pinned the **core decision = publish-confidence** ("is THIS the right, trustworthy,
  reproducible figure to put in my paper?"). Presented a **build charter (B0–B9)** that reorders the P0–P8
  ledger to honour both, folding already-built work in as done; **owner APPROVED it → filed to `docs/build-charter.md`.**
  **Ratified the 5 pending build [DECISION]s** into `DECISIONS.md`: #5 custom figure editor · #6 arq+Redis
  (BE-lane, flagged to Codex) · #7 web-first · #8 trade-secret IP (repo = `D:/selom` was already #2). Then presented the **Bucket-1 plan** (close the P0 gate) for owner review — not started. The
  charter + deep ADRs `0004–0007` still need mirroring into the vault by the wiki agent (read-only here).
- **Prior session:** Designed + documented the **command-center expansion** and scaffolded its **frontend shell**
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
- **Last (2026-06-11 23:25) — B1 DONE, P0 gate CLOSED.** Built BOTH lanes: (BE) `uv sync --extra scrna` on
  user-managed py3.12 + wired `run_scanpy.py` (real filter→normalize→PCA→neighbors→Leiden→UMAP) behind the
  one-shot `POST /skills/umap_scrna/run`; `scripts/make_demo.py` writes the pbmc3k `demo.h5ad`. Fixed two real
  bugs en route: Plotly 6 base64 typed-array encoding (decode → plain JSON arrays so live matches the stub
  shape) and the Next 16 proxy 10MB body cap (RISKS #8 → 512mb). (FE) added `runtimeSkillId()` to map catalog
  ids `selom.umap_scrna` → backend `umap_scrna`. Browser-verified the full flow on :3010 (killed an orphan MCP
  Chrome from the crash to unblock). Committed scoped: BE `6e37829`, FE `396ca66`, docs `680557a`. Resolved
  FE→Codex asks #1/#2 (one-shot contract confirmed).
- **Next:** push the three commits, then **B2 (Steven's real skills)** per `docs/build-charter.md` — hand-port
  the wedge (cluster/DEG/volcano/heatmap/enrichment) into the SkillSpec contract, each emitting an editable
  Plotly spec + a golden-image test. Keep BE drop-in-ready for Codex. Wiki agent still to mirror the charter +
  file deep ADRs 0004–0007. (Optional cleanup: `plans/v2-frontend.md` P0 still says two-step upload — update to
  one-shot.)
- **Resume:**
  ```
  # Resume · 2026-06-11 23:25 +10:00 · Selom · Claude (frontend + backend, acting)
  Selom build repo D:/selom. CLAUDE.md auto-loads. Read agent_handoff/README.md + CURRENT.md (this) + DECISIONS.md + RISKS.md + docs/build-charter.md + docs/command-center/design.md + plans/v2-frontend.md + plans/v2-backend.md.
  ROLE: Codex is away → Claude owns BOTH lanes. Keep BE drop-in-ready: accurate `## Codex` section, explicit per-lane scoped commits (never git add -A).
  Delta: B1 DONE — P0 hello-UMAP gate CLOSED end-to-end. Real scanpy UMAP renders in-browser from an uploaded .h5ad against live :8000 (MSW off). Committed BE 6e37829 / FE 396ca66 / docs 680557a — NOT pushed. New RISKS #8 (Next proxy 10MB body cap → fixed 512mb). FE→Codex asks #1/#2 resolved (one-shot contract).
  Env notes: backend on user-managed py3.12 (uv), system py3.10 is IT-locked — do not use. demo.h5ad is gitignored (~21MB), regenerate via `uv run --directory app/backend python scripts/make_demo.py`. Use `python -m pytest`/`python -m uvicorn` (Windows blocks fresh .exe shims). FE dev port 3010 (3000/3001 used by other projects). To run real engine set SELOM_UMAP_ENGINE=scanpy (auto also works when scanpy installed).
  Next: push the 3 commits → B2 (Steven's real skills: cluster/DEG/volcano/heatmap/enrichment into SkillSpec + golden-image tests). Stay on Fable 5 (xhigh). End clear-safe.
  ```

## Codex — Last Task & Resume

> **Role coverage (2026-06-11 22:10):** Codex is away on another project; **Claude is acting backend owner.**
> This section is maintained by Claude *on Codex's behalf* and kept accurate to true backend state so Codex (or
> any agent) can drop in and take over from the `**Next**` line below with zero re-derivation. When Codex
> returns, take this section back and review the backend-lane decisions locked in the interim (arq #6).

- **Last (done by Claude, acting BE, 2026-06-11):** **B1 backend complete — P0 gate closed.** venv built via
  `uv sync --extra scrna` (new light scRNA extra in `pyproject.toml`; `[omics]` now supersets it) on the
  user-managed py3.12; `run_scanpy.py` wired as the real engine behind the one-shot
  `POST /skills/umap_scrna/run`; `run.py` dispatches stub vs. real via `SELOM_UMAP_ENGINE`; `scripts/make_demo.py`
  + `uv.lock` added; contract test pinned to the stub. Committed `feat(backend:)` `6e37829`. **arq #6 was locked
  in your absence — review on return.**
- **Next (B2 → B3 → B4):** **B2** hand-port Steven's wedge skills (cluster/DEG/volcano/heatmap/enrichment) into
  the SkillSpec contract, each emitting an editable Plotly spec + a golden-image test; **B3** Supabase + arq async
  queue; **B4** publish-confidence — guardrails / methods-text / Kaleido export (RISKS #2/#5). Full spec in
  `docs/build-charter.md` + Cross-Agent Requests. Explicit staging only (never `git add -A`); `feat(backend:)` scope.
- **Resume:**
  ```
  # Resume · 2026-06-11 23:25 +10:00 · Selom · Codex (backend) — reclaiming from Claude
  Selom build repo D:/selom. CODEX.md auto-loads. Read agent_handoff/README.md + CURRENT.md + DECISIONS.md + RISKS.md + docs/build-charter.md + plans/v2-backend.md + git status.
  Delta: B1 backend DONE by Claude — real scanpy UMAP wired behind one-shot POST /skills/umap_scrna/run, verified end-to-end in-browser. Committed 6e37829 (not pushed). New light [scrna] extra; demo.h5ad gitignored. arq #6 locked in your absence — review it.
  Next: B2 (port wedge skills to SkillSpec + golden-image tests). Env: user-managed py3.12 (system 3.10 IT-locked); use `python -m pytest`/`-m uvicorn`. Stay on Fable 5. End clear-safe.
  ```
