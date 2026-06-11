# Selom — CURRENT (Live State)

> **LIVE STATE ONLY.** The current state of the two-agent build. History lives in
> each agent's rolling log, not here. This file is **replaced, never stacked** —
> update at MAJOR boundaries only (rule 9 in `agent_handoff/README.md`).

_Last updated: 2026-06-12 01:48 +10:00 · Claude (acting FE+BE) — **B3 (skills-as-a-service) LANDED + integration-backlog quick wins; ALL PUSHED.** `main` ↔ `origin/main` @ `5138aec` (the 7 prior B2/audit/integration commits were pushed first). **B3 = 4 commits:** (1) live **`GET /skills`** registry — `skills/registry.py` maps each `skill.json` + a new optional `catalog` block to the FE `SkillCatalogEntry` shape, so adding a skill dir shows it in the Store with no FE edit; (2) **async jobs API** — `POST /skills/{id}/jobs` → `GET /jobs/{id}` (poll) / `/jobs/{id}/events` (SSE) / `/jobs/{id}/result`; one `execute_job` shared by the inline executor and the arq worker. Infra is **OFF by default** (jobs run **inline**, results on the **local filesystem**) so a fresh `uv sync` + uvicorn runs the whole job API with zero infra; `SELOM_QUEUE=arq`+Redis (DECISIONS #6) and `SELOM_R2_*`+Cloudflare R2 (boto3 with the RISKS #5 checksum fix) flip on the distributed/cloud path — **wired but dormant** pending infra (arq cross-process *status* is a documented follow-up in `jobs/worker.py`); new optional `[jobs]` extra. (3) **FE registry-driven Store** — `lib/catalog/registry.ts` fetches `/api/skills`, merges the live Verified slice over the static seed's Community tail, falls back to the seed offline; `CoverageMeter` shows the **live** runnable count; MSW mocks `/api/skills`. (4) **Integration backlog quick wins:** heatmap **hierarchical row-ordering** (scipy correlation-distance linkage, real-engine only) + **dropped `gseapy`** from `[omics]` (DECISIONS #9 / RISKS #6/#9; `uv` re-locked). **Verified:** backend `pytest` = **21 passed** (14 base + 3 registry + 4 jobs); ruff clean; live uvicorn smoke (skills/submit/poll/result/SSE) green; FE `tsc` + `next build` clean; **browser-verified** (mock :3010) — `/api/skills` 200, meter live 13/~628, 32 shown, phantom `proteomics_volcano` correctly dropped from Verified, console clean. Selom is **DESKTOP-ONLY**. Next: **B4 publish-confidence** + the remaining integration backlog (OmicVerse isolated worker, R4DS/Quarto + R-oracle, full GO/Reactome GMT, catalog-count true-up, OmicVerse/JARVIS MCP)._

**Model:** stay on **Fable 5** for all Selom work — Selom carries no biology/security
flag. Only *reading the EAMOS build repo* escalates a session to Opus, and that
source is not needed here. Do not switch to Opus for Selom.

## Active Status

| Agent | Role | Lane | Status |
|---|---|---|---|
| Claude | **Frontend + Backend (acting)** — UI/design/product copy **and** APIs/skill runners/data/tests | `app/frontend` + `app/backend` + both plans | IDLE (clear-safe) — **B3 LANDED + integration quick wins; ALL PUSHED** (`main` ↔ `origin/main` @ `5138aec`). Live `GET /skills` registry; async jobs API (inline+local active, arq+R2 wired/dormant); FE registry-driven Store; heatmap row-ordering; `gseapy` dropped. `pytest` 21 passed; FE `next build` clean; browser-verified. Decisions #5–#9 locked. Selom is **desktop-only**. |
| Codex | Backend (APIs/skill runners/data/tests) | `app/backend` + `plans/v2-backend.md` | **AWAY** (busy on another project). Backend role **temporarily covered by Claude** as of 2026-06-11 22:10. B1 + **B2 backend done by Claude** in the interim (see `## Codex` section). May reclaim at any time — state is drop-in-ready; review the arq #6 lock + the B1/B2 commits on return. |

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
  to 512mb (RISKS #8). **Pushed: `main` ↔ `origin/main` @ `7d58e92`.**
- **Still NOT done (by scope):** no cloud (`.env` + `.mcp.json` are TODO placeholders),
  no Docker, no Supabase/arq, no Kaleido export. Those are later buckets.
- **Next milestone = B2 (Steven's real skills) — SIGNED OFF 2026-06-11, not started.** Build 6
  backend runners (cluster · violin · DEG · volcano · heatmap · GSEA/enrichment), each a pure-Python
  skill emitting an editable Plotly spec + a golden-image snapshot test. Locked: public proxy
  datasets now (real data later); GSEA via Reactome/GO (DECISIONS #9). Then B3 (jobs/queue) / B4
  (publish-confidence). See `docs/build-charter.md`.

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
- **B1 (done 2026-06-11):** P0 hello-UMAP closed end-to-end — real scanpy UMAP behind the one-shot
  `POST /skills/umap_scrna/run`, browser-verified; pushed (`main` @ `7d58e92`). See git history `6e37829`/`396ca66`.
- **Last (2026-06-12 00:44) — FRONTEND AUDIT + B2 DONE locally (NOT pushed).**
  - **Frontend audit** (all 3 skills): ran `/impeccable init` → wrote **`DESIGN.md`** + `.impeccable/design.json`
    sidecar (captured the existing dark-IDE token system). Audited Home / Store / project tabs / intake /
    figure editor across ui-ux-pro-max + frontend-design + impeccable, **browser-verified on the live app**
    (mock mode, :3010). Fixes applied (commit `506d1e6`): removed the banned skill-card left side-stripe; made
    the skill-card detail keyboard-operable (`role=button` + Enter/Space + focus ring); skill-detail modal focus
    management; bumped a low-contrast meta line; friendlier run-error copy (no raw "HTTP 500"); rail collapses
    to a drawer below `lg` so the **desktop** app degrades gracefully in narrow/split windows. The FE was already
    strong (landmarks, focus rings, role=dialog/alert, tabular nums, guardrails-first IA, light artboard).
  - **B2 — all 6 wedge skills** (`feat(backend:)` `eded0db`): `cluster · violin · deg · volcano · heatmap ·
    enrichment`, each `skills/<slug>/{skill.json, run.py (dep-free stub) + run_real.py}`, dispatched by
    `SELOM_SKILLS_ENGINE` (auto/stub/real) via new `skills/_engine.py`; all emit the editable plain-array Plotly
    spec via the shared **`skills/_plotly.jsonable`** (factored out of run_scanpy; umap now reuses it). DEG does
    scRNA `rank_genes_groups` + bulk pyDESeq2 (CPM-log2FC fallback when pydeseq2 absent). **Enrichment = in-house
    hypergeometric ORA + BH FDR** against a bundled GO/Reactome gene-set sample (`gene_sets.json`) — NO
    gseapy/MSigDB (DECISIONS #9). Golden-image tests `tests/test_skills_golden.py` (+ `tests/golden/*.json`, regen
    via `tests/regen_golden.py`) — `python -m pytest` = **14 passed**; real engines smoke-verified on synthetic
    h5ad/CSV (all 8 paths). `main.py` generalized: run-endpoint takes any Verified skill (query-string params +
    preserved upload suffix). FE `selom.violin` entry added (`feat(frontend:)` `d1b9533`; coverage → 14/628).
- **Last (2026-06-12 01:48) — B3 DONE + integration quick wins; ALL PUSHED (`main` @ `5138aec`).** Pushed
  the 7 prior commits first, then landed B3 in 4 scoped commits:
  - **`021af8c` `feat(backend)` — live `GET /skills` + async jobs API.** Registry: `skills/registry.py` maps each
    `skill.json` (+ a new optional `catalog` block on `SkillSpec`) to the FE `SkillCatalogEntry` shape; `GET /skills`
    returns the live Verified set. Jobs: `POST /skills/{id}/jobs` → `GET /jobs/{id}` (poll) / `/events` (SSE,
    `text/event-stream`) / `/result` ({figure}, same shape as `/run`). New modules `config.py` (pydantic-settings),
    `jobs/{store,queue,worker}.py`, `storage/results.py`. **One `execute_job`** is shared by the inline executor and
    the arq worker. Default = **inline + local filesystem result store** (zero infra); `SELOM_QUEUE=arq`+Redis and
    `SELOM_R2_*`+R2 (boto3 + RISKS #5 checksum fix) are **wired but dormant**. New optional `[jobs]` extra.
  - **`5b38f9e` `feat(backend)` — heatmap hierarchical row-ordering** (scipy correlation-distance + average linkage,
    real-engine only; stub/golden unchanged) **+ dropped `gseapy`** from `[omics]` (DECISIONS #9 / RISKS #6/#9; uv re-locked).
  - **`5138aec` `feat(frontend)` — registry-driven Store.** `lib/catalog/registry.ts` fetches `/api/skills`, merges live
    Verified over the seed's Community tail, falls back to seed offline; `CoverageMeter` shows the live count; MSW mocks
    `/api/skills`; seed `enrichment` relabelled MIT (DECISIONS #9).
  - **Verified:** `pytest` 21 passed; ruff clean; live uvicorn smoke (skills/submit/poll/result/SSE) green; FE `tsc` +
    `next build` clean; browser (mock :3010) — `/api/skills` 200, meter live **13/~628**, 32 shown, `proteomics_volcano`
    dropped, console clean (only an unrelated favicon 404).
- **Next (B4 publish-confidence + integration backlog).** B4 = per-figure reproducibility bundle, statistical
  guardrails, auto methods-text, Kaleido journal export (RISKS #2/#5). Integration backlog (`plans/v2-backend.md` →
  `docs/integrations.md`): **OmicVerse isolated worker** (RISKS #9 — own env/container, call its MCP/RPC out-of-process;
  SCA-gate its 50 deps), **arq cross-process job *status*** (Redis-backed JobStore — see `jobs/worker.py` caveat),
  R4DS/Quarto for B4 + the R-oracle harness (RISKS #7), full GO/Reactome GMT, catalog-count true-up (≈418 via a live
  ingest job), OmicVerse/JARVIS MCP (add only AFTER its isolated env exists). `plans/v2-frontend.md` P0 still says two-step upload.
- **Resume:**
  ```
  # Resume · 2026-06-12 01:48 +10:00 · Selom · Claude (frontend + backend, acting)
  Selom build repo D:/selom. CLAUDE.md auto-loads. Read agent_handoff/README.md + CURRENT.md (this) + DECISIONS.md + RISKS.md + docs/build-charter.md + DESIGN.md + plans/v2-backend.md + plans/v2-frontend.md + docs/integrations.md.
  ROLE: Codex away → Claude owns BOTH lanes. Keep BE drop-in-ready: accurate `## Codex` section, explicit per-lane scoped commits (never git add -A). Selom is DESKTOP-ONLY.
  Delta: B3 DONE + pushed (main @ 5138aec). Live GET /skills registry (skills/registry.py + catalog block on skill.json); async jobs API (POST /skills/{id}/jobs, GET /jobs/{id}|/events|/result; inline+local active, arq+R2 wired/dormant; [jobs] extra). FE registry-driven Store (lib/catalog/registry.ts + CoverageMeter, seed fallback). heatmap scipy row-ordering; gseapy dropped from [omics]. pytest 21 passed; FE next build clean; browser-verified (mock :3010).
  Env: backend on user-managed py3.12 (uv at C:/Users/seamegdool/.local/bin/uv.exe); system py3.10 IT-locked. Run via `uv run --directory app/backend python -m pytest` / `-m uvicorn`. Jobs default inline+local (no infra); SELOM_QUEUE=arq + SELOM_R2_* + the [jobs] extra flip on Redis/R2. Skills stub vs real via SELOM_SKILLS_ENGINE; golden tests pin stub. FE dev `npm run dev:mock -- --port 3010` (mock; 3000/3001 are other projects). demo.h5ad gitignored — regen via scripts/make_demo.py.
  Next: B4 publish-confidence (repro bundle, guardrails, methods-text, Kaleido) + integration backlog (OmicVerse isolated worker, arq Redis status store, R-oracle, full GMT, catalog true-up). Stay on Fable 5 (xhigh). End clear-safe.
  ```

## Codex — Last Task & Resume

> **Role coverage (2026-06-11 22:10):** Codex is away on another project; **Claude is acting backend owner.**
> This section is maintained by Claude *on Codex's behalf* and kept accurate to true backend state so Codex (or
> any agent) can drop in and take over from the `**Next**` line below with zero re-derivation. When Codex
> returns, take this section back and review the backend-lane decisions locked in the interim (arq #6).

- **Last (done by Claude, acting BE, 2026-06-12):** **B1 + B2 backend complete.** B1 = real scanpy UMAP behind
  the one-shot `POST /skills/umap_scrna/run` (`6e37829`). **B2 = all 6 wedge skills** (`eded0db`):
  `cluster · violin · deg · volcano · heatmap · enrichment`, each `skills/<slug>/{skill.json, run.py (stub) +
  run_real.py}`, dispatched by `SELOM_SKILLS_ENGINE` (auto/stub/real) via `skills/_engine.py`; output via the
  shared `skills/_plotly.jsonable` (factored out of `run_scanpy`). DEG: scRNA `rank_genes_groups` + bulk pyDESeq2
  (CPM fallback). **Enrichment: in-house hypergeometric ORA + BH FDR vs a bundled GO/Reactome `gene_sets.json` —
  NO gseapy/MSigDB (DECISIONS #9).** `main.py` run-endpoint generalized to ANY Verified skill (query params +
  preserved upload suffix). Tests `tests/test_skills_golden.py` + `tests/golden/*.json` (regen `tests/regen_golden.py`)
  → `python -m pytest` = 14 passed; real engines smoke-verified on synthetic data.
- **Last (done by Claude, acting BE, 2026-06-12) — B3 backend DONE + integration quick wins; ALL PUSHED (`main` @ `5138aec`).**
  **Registry:** `skills/registry.py` maps each `skill.json` (+ a new optional `catalog` block on `SkillSpec`) to the FE
  `SkillCatalogEntry` shape; `GET /skills` returns the live Verified set. **Async jobs API:** `POST /skills/{id}/jobs` →
  `GET /jobs/{id}` (poll) / `/events` (SSE) / `/result`; new `config.py`, `jobs/{store,queue,worker}.py`,
  `storage/results.py`; one `execute_job` shared by the inline executor and the arq worker. **Default = inline + local
  filesystem result store (ZERO infra).** `SELOM_QUEUE=arq`+Redis (DECISIONS #6) and `SELOM_R2_*`+R2 (boto3 + the RISKS #5
  checksum fix) are **wired but DORMANT**; new optional `[jobs]` extra. **heatmap** got scipy hierarchical row-ordering
  (real-engine only); **`gseapy` DROPPED** from `[omics]` (DECISIONS #9 / RISKS #6/#9; uv re-locked). `pytest` = **21 passed**.
  arq #6 confirmed in your absence — review on return. **`/run` stays synchronous** (the proven light-skill path); only
  heavy skills use `/jobs`. The one open BE item: **arq cross-process job *status*** needs a Redis-backed JobStore
  (`jobs/worker.py` documents the caveat — success propagates via the shared result store, but queued/running/error states don't yet).
- **Next (B4 + integration backlog):** **B4** publish-confidence — reproducibility bundle, statistical guardrails, auto
  methods-text, Kaleido journal export (RISKS #2/#5). **Integration backlog (`docs/integrations.md` + `plans/v2-backend.md`):**
  OmicVerse as an **isolated** 2nd engine/Foundry source — pins `pandas<3` so it CANNOT share this venv (RISKS #9); run
  out-of-process (its MCP server / a worker), SCA-gate its 50 deps; the **arq Redis status store**; R4DS/Quarto for B4 +
  the R-oracle harness (RISKS #7); full GO/Reactome GMT; catalog-count true-up (≈418 via a live ingest job). sklearn is a
  core dep (silhouette in `cluster`). Explicit staging only (never `git add -A`); `feat(backend:)` scope.
- **Resume:**
  ```
  # Resume · 2026-06-12 01:48 +10:00 · Selom · Codex (backend) — reclaiming from Claude
  Selom build repo D:/selom. CODEX.md auto-loads. Read agent_handoff/README.md + CURRENT.md + DECISIONS.md + RISKS.md + docs/build-charter.md + plans/v2-backend.md + docs/integrations.md + git status.
  Delta: B1 + B2 + B3 backend DONE by Claude; ALL PUSHED (main @ 5138aec). B3 = live GET /skills registry (skills/registry.py + a catalog block on skill.json) + async jobs API (POST /skills/{id}/jobs, GET /jobs/{id}|/events|/result; config.py + jobs/ + storage/; one execute_job for inline+arq). Default inline + local filesystem result store (zero infra); arq+Redis (DECISIONS #6) and R2 (boto3 + RISKS #5 fix) wired but dormant; new [jobs] extra. heatmap scipy row-ordering; gseapy dropped from [omics]. pytest 21 passed.
  Open BE item: arq cross-process job STATUS needs a Redis-backed JobStore (jobs/worker.py caveat). Next: B4 publish-confidence + integration backlog (OmicVerse isolated worker, R-oracle, full GMT, catalog true-up). Env: user-managed py3.12 (uv); system 3.10 IT-locked; `uv run --directory app/backend python -m pytest`/`-m uvicorn`. Stay on Fable 5. End clear-safe.
  ```
