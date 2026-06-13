# Selom — CURRENT (Live State)

> **LIVE STATE ONLY.** The current state of the two-agent build. History lives in
> each agent's rolling log, not here. This file is **replaced, never stacked** —
> update at MAJOR boundaries only (rule 9 in `agent_handoff/README.md`).

_Last updated: 2026-06-13 · Claude (acting FE+BE) — **B4 publish-confidence slice-1 DONE (both lanes) and PUSHED** (`main` ↔ `origin/main` in sync): backend `2ab7c43` + frontend `84ae54e` (+ handoff `3d76bf1`). **What landed:** every figure now ships a **per-figure reproducibility bundle** (`provenance.py` — skill+version, resolved+typed params, input SHA-256+size, environment = python/platform/engine-policy + scientific-stack versions) and **auto methods-text** (`methods.py` — deterministic per-skill templates quoting the exact params + canonical citations Scanpy/Leiden/UMAP/PyDESeq2/DESeq2/BH/GO/Reactome/SciPy; generic fallback). Additive wire change: `POST /skills/{id}/run` + `GET /jobs/{id}/result` now return `{figure, provenance, methods}` (FE still reads `.figure`); jobs thread the upload filename + store the full bundle via the shared `execute_job`. New `contract.resolved_params()` (typed param coercion; runners untouched). FE: a collapsed **"Publish confidence"** panel (`components/project/publish-confidence.tsx`) in the Figure tab — Methods (copyable + citations) + Reproducibility (params chips / input hash / env chips); `runSkill` returns the bundle; MSW mock serves a representative bundle (`mocks/stub-bundle.ts`). **Verified:** backend `pytest` = **28 passed** (21 base + 7 new: provenance + methods + jobs-bundle); ruff clean; live uvicorn smoke (`/run` + job submit/result) returns the full bundle. FE `tsc` + `next build` clean (4 routes); **browser-verified** (mock :3010) — ran umap_scrna, panel expands with methods + repro record, Copy present, `POST /run` 200, console clean (only the pre-existing favicon 404). **Deferred B4 follow-ups:** statistical-guardrail expansion (silhouette already on `cluster`), **Kaleido journal export** (needs Docker+Chromium — RISKS #2), plus the standing integration backlog. Selom is **DESKTOP-ONLY**. **This session (2026-06-13):** pushed the held B4 commits; filed the OmicsBox competitor teardown (`docs/competitors/omicsbox.md`, `6a139ad`) + threaded its P1→P4 priorities into `docs/build-charter.md` (`7c3189e`) + landed **DECISIONS #10** (skill-scope bet); **model switched Fable 5 → Opus 4.8 (xhigh)**, owner-directed (`267ab50`, applies on restart). Then **B4 slice-2 — statistical guardrails** (`guardrails.py`: multiple-testing / FDR method checks + best-effort `.h5ad` data checks — low-cell, pre-normalized, uncorrected-batch) on every `/run` + job result, surfaced as the FE **"Quality checks"** panel section + a warn-count chip. `pytest` 40 passed; `next build` clean; browser-verified (mock :3010). Commits BE `edd3615` + FE `56da2a6`; guardrails since extended to **bulk/CSV** (`133fb79`) + a **backed-sparse read fix** (`78afdcb`, caught dogfooding). **Real data ingested:** a ShinyCell→AnnData converter (`5dc9750`, `scripts/shinycell_to_h5ad.py`, MIT `rdata`) merged Steven's RPGRIP1 scRNA-seq → `D:/selom-data/rpgrip1/processed/rpgrip1_merged.h5ad` (83,659 cells × 33,538 genes; 9 samples WT/C3/PT/FS; log-normalized) — B4 guardrails validated live on it (pre-normalized + uncorrected-batch fire). Also ingested a **2nd real dataset** — EYG_28 human-RO **bulk RNA-seq DE-results** (staged `D:/selom-data/eyg28`); fixed `volcano` gene-column detection (`8f832db`) for real DE tables, validated on RPGRIP1_cpdHet; landed a scRNA **skip-normalization** option (`7df4db6`) so pre-normalized real data analyzes honestly — **(a) real-data dogfooding now complete on both datasets**. **P1 underway** — `enrichment` now scores against a full **GO library (7,727 sets)** built license-clean from primary GO, validated on real RPGRIP1 (overlap 14→850, real terms); plus DE-table-aware enrichment, use-existing-embedding (stored t-SNE), and the **`go_graph`** skill (enriched GO terms as an editable DAG); 3 ALPK1 datasets scouted + key claims self-verified (`docs/real-datasets.md`). **push pending.** Docker/WSL-gated work is parked in **`agent_handoff/on-hold/`** (Kaleido export, arq Redis status store, OmicVerse worker, deploy image, community sandbox) — resume each with owner's go-ahead.**_

<!-- prior live-state: B4 publish-confidence slice-1 @ `4216935` (committed 2026-06-12 02:45, pushed 2026-06-13). Full history in git log + the Claude/Codex resume sections below. -->

**Model:** **Opus 4.8 (xhigh effort)** for all Selom work — owner-directed 2026-06-13,
pinned in `.claude/settings.json` (`model=claude-opus-4-8`, `effortLevel=xhigh`); applies on
session restart. Supersedes the prior Fable-5 default.

## Active Status

| Agent | Role | Lane | Status |
|---|---|---|---|
| Claude | **Frontend + Backend (acting)** — UI/design/product copy **and** APIs/skill runners/data/tests | `app/frontend` + `app/backend` + both plans | IDLE (clear-safe) — **B4 slices 1–2 DONE.** Per-figure reproducibility bundle (`provenance.py`) + auto methods-text (`methods.py`) + **statistical guardrails** (`guardrails.py`) on every `/run` + job result (now `{figure, provenance, methods, guardrails}`); FE **"Publish confidence"** panel = Methods · Reproducibility · **Quality checks** + warn-count chip. `pytest` 40 passed; FE `next build` clean; browser-verified (mock :3010). Slice-1 + the 2026-06-13 docs (OmicsBox teardown, P1→P4 charter, Decisions #5–#10) PUSHED; B4 slice-2 + bulk/CSV + the real-data work all PUSHED; **`main` ↔ `origin/main` in sync.** model → **Opus 4.8 (xhigh)**; Selom is **desktop-only**; Docker/WSL work parked in `agent_handoff/on-hold/`. |
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
- **Last (2026-06-12 02:45) — B4 publish-confidence slice-1 DONE (both lanes); COMMITTED locally, NOT pushed** (`main`
  ahead 2 of `origin/main` @ `4216935`). Two scoped commits:
  - **`2ab7c43` `feat(backend)` — reproducibility bundle + auto methods-text.** New `provenance.py` (per-figure bundle:
    skill+version, resolved+typed params, input **SHA-256**+size, environment = python/platform/engine-policy + scientific-stack
    versions via `importlib.metadata`) + `methods.py` (deterministic per-skill templates quoting the exact params + canonical
    citations — Scanpy/Leiden/UMAP/PyDESeq2/DESeq2/BH/GO/Reactome/SciPy; generic fallback). `contract.resolved_params()` does
    typed coercion (runners untouched). **Additive wire change:** `POST /skills/{id}/run` + `GET /jobs/{id}/result` now return
    `{figure, provenance, methods}` (same shape both paths); jobs thread the upload `filename` (new `Job.filename`) + store the
    full bundle via the shared `execute_job`; `result_store.put` param renamed figure→payload. `pytest` **28 passed** (21 + new
    `test_provenance.py` + `test_methods.py` + jobs-bundle asserts); ruff clean; live uvicorn smoke green.
  - **`84ae54e` `feat(frontend)` — "Publish confidence" panel.** `components/project/publish-confidence.tsx` (collapsed by
    default, in the Figure tab between toolbar + editor): **Methods** (prose + Copy[text+numbered citations] + citation list) +
    **Reproducibility** (skill v, param chips, input filename/size/sha, env Python + package chips). `runSkill` now returns the
    full bundle (`SkillProvenance`/`SkillMethods`, both optional); `project-workspace` captures it on run + clears on "New figure";
    MSW mock serves a representative bundle (`mocks/stub-bundle.ts`). `tsc` + `next build` clean (4 routes); **browser-verified**
    (mock :3010) — ran umap_scrna, panel expands with methods + repro record, Copy present, `POST /run` 200, console clean (only the pre-existing favicon 404).
- **Next (finish B4, then integration backlog). B4 remaining:** (a) **statistical-guardrail expansion** — silhouette already on
  `cluster`; add batch-effect / normalization / multiple-testing / low-cell warnings surfaced in the bundle (a `guardrails` field
  or figure subtitle), (b) **Kaleido journal export** — PNG/SVG/PDF presets; needs **Docker + system Chromium** (RISKS #2 / DECISIONS #7),
  so it lands with the deploy image (B8-adjacent) — scope a CPU-Docker path or defer. Integration backlog (`plans/v2-backend.md` →
  `docs/integrations.md`): **OmicVerse isolated worker** (RISKS #9), **arq cross-process job *status*** (Redis-backed JobStore — `jobs/worker.py`
  caveat), R4DS/Quarto + R-oracle (RISKS #7), full GO/Reactome GMT, catalog-count true-up (≈418 via a live ingest job), OmicVerse/JARVIS MCP
  (only AFTER its isolated env). `plans/v2-frontend.md` P0 still says two-step upload.
- **Last (2026-06-13) — pushed + research/planning, no lane code.** Pushed the held B4 slice-1 (BE `2ab7c43` + FE `84ae54e` +
  handoff `3d76bf1`) → `main` ↔ `origin/main` in sync. Filed the **OmicsBox competitor teardown** (`docs/competitors/omicsbox.md`,
  `6a139ad`); threaded its **P1→P4 skill priorities** into `docs/build-charter.md` as a prioritization lens (`7c3189e`); landed
  **DECISIONS #10** (skill-scope bet — win the editable-figure last mile + own the proteomics/metabolomics whitespace, don't chase
  upstream NGS). **Model switched off Fable 5 → Opus 4.8 (xhigh)**, owner-directed (`267ab50`; pinned in `.claude/settings.json`,
  applies on session restart). No app/ code touched (research/planning).
- **Last (2026-06-13) — B4 slice-2 (statistical guardrails) DONE, both lanes; committed, push pending.** New bundle-side
  `app/backend/guardrails.py` adds a `guardrails` list to every `/run` + job result: method/param checks (multiple-testing note
  + lax / no-FDR-filtering warnings for deg/volcano/enrichment) + best-effort `.h5ad` data checks (low-cell, pre-normalized-input,
  uncorrected-batch; backed read, handle released so the Windows temp-unlink works; CSV/stub skip cleanly). Cluster silhouette
  stays in the runner. FE: a **"Quality checks"** section in the Publish-confidence panel (warnings first, level icons) + an amber
  warn-count header chip; `runSkill` / bundle state / MSW mock all thread `guardrails`. `pytest` **40 passed** (28 + 12); ruff clean;
  real-engine smoke fired low-cell+batch / pre-normalized / clean-raw correctly; FE `tsc` + `next build` clean; browser-verified
  (mock :3010 — bulk DEG run → Quality checks shows the multiple-testing check, console clean). Commits BE `edd3615` + FE `56da2a6`;
  charter B4 updated. **Open: push the 3 local commits (+ this doc) on owner's word.** Kaleido export is the only B4 remainder
  (Docker+Chromium — RISKS #2; ASK OWNER before any Docker/WSL — see memory `ask-before-docker-wsl`).
- **Last (2026-06-13) — real RPGRIP1 data ingested + dogfooding caught a guardrail bug.** Owner re-interview set the
  direction: **build P1→P4**, **keep the staged order** (dogfood-first), validate on real data. The real data
  (`\\cmri.com.au\…\RPGRIP1_Hani`, owner-provided) is **ShinyCell exports**, not h5ad. Built `scripts/shinycell_to_h5ad.py`
  (dev tool; MIT pure-Python `rdata`, no R / no AGPL) → merged `.h5ad` (83,659 cells × 33,538 genes; 9 samples WT/C3/PT/FS;
  log-normalized) at `D:/selom-data/rpgrip1/processed/` (raw bundles copied to `…/raw/` as a share-loss hedge; the whole
  `D:/selom-data` tree is OUTSIDE the repo). Extended B4 guardrails to **bulk/CSV** (`133fb79`) and **fixed a backed-sparse
  h5ad read bug** (`78afdcb`) that only surfaced on real sparse scRNA; guardrails validated live on the real data
  (pre-normalized + uncorrected-batch fire). Commits `133fb79` / `78afdcb` / `5dc9750`. **Open: push the 6 local commits on
  owner's word.** Memory: `selom-rpgrip1-real-data`. **Next:** dogfood the existing skills on the merged h5ad (WT-vs-mutant
  DEG / UMAP / cluster), then build **P1** (pathway/go-graph + deg/enrichment breadth).
- **Last (2026-06-13) — 2nd real dataset (EYG_28 bulk) reviewed + dogfooded; volcano hardened.** EYG_28 = human retinal-organoid
  **bulk RNA-seq DE-results** (RUVseq/limma; PDE6B {FS/V/pt} + RPGRIP1_cpdHet vs Control across d120–d210; 5 norm methods incl.
  TMM-K0 baseline), staged at `D:/selom-data/eyg28/raw` (110 CSVs, 283.7 MB; ~840 MB HTML reports left on the share). **No raw
  counts exported** → Selom fit = **volcano + enrichment** (NOT `deg`, which would recompute). Tool fix: broadened `volcano`
  gene-column detection (GeneID/gene_name/gene_symbol/feature) so real DE tables label with gene symbols not the row index —
  `8f832db` + `test_volcano_columns.py`; validated on RPGRIP1_cpdHet/TMM-K0 (327 up / 962 down). **Dogfooding findings → hardening
  backlog:** (1) the scRNA skills assume raw counts + recompute embeddings, so **pre-normalized** ShinyCell data (rpgrip1) needs a
  **skip-normalization / use-existing-embedding** option before honest scRNA figures (the B4 guardrail already flags the input);
  (2) a multi-contrast **DE-table import** flow would help folders like EYG_28. Memory: `selom-eyg28-bulk-data`. **Open: push the
  9 local commits on owner's word.** **Next (P1, owner-directed):** start with broaden `deg`/`enrichment` + the pre-norm option
  (no new API, fully testable), then `pathway`/`go-graph` (KEGG/Reactome/GO APIs — scope first).
- **Last (2026-06-13) — scRNA skip-normalization landed; (a) dogfooding COMPLETE (both real datasets).** Added a `normalize`
  (bool, default true) param to umap_scrna/cluster/violin/deg (+ a real `bool` cast in `contract` via `_engine.to_bool`; UMAP
  methods-text reflects whether it ran) — `normalize=false` skips re-normalization for already-normalized inputs (`7df4db6`).
  Dogfooded `rpgrip1_merged.h5ad` with normalize=false: **DEG by genotype** → sensible retinal markers (NRL / RCVRN / RHO-axis),
  **RHO violin** across WT/C3/PT/FS; figure specs saved to `D:/selom-data/rpgrip1/processed/figures/`. Bulk EYG_28 already
  dogfooded via volcano. pytest 50; ruff clean. **All session commits PUSHED — `main` ↔ `origin/main` in sync; Docker/WSL work parked in `agent_handoff/on-hold/`.** **Next (b) P1:** broaden `deg` (no-rep /
  time-course) + `enrichment` (ORA) — no new API, build now; then scope `pathway`/`go-graph` (KEGG/Reactome/GO/QuickGO/STRING
  APIs) per charter before building new skills. Remaining scRNA nicety: use-existing-embedding (plot stored UMAP/t-SNE rather than recompute).
- **Last (2026-06-14) — P1 #1 DONE: `enrichment` full GO gene-set library (owner approved Decision #1 + the sequence).**
  Built `scripts/build_gene_sets.py` (dev-time, MIT `obonet`) → `gene_sets_go.json` (gitignored, ~5.2 MB, regenerable):
  **7,727 GO sets** (BP 5576 / MF 1346 / CC 805), 21,198 genes, from go-basic.obo + goa_human.gaf (CC-BY 4.0, license-clean —
  no gseapy/MSigDB per DECISIONS #9). `enrichment._load_gene_sets` prefers it, else the committed sample. Also broadened
  `volcano` + `enrichment` gene-column detection for real DE headers (`GeneID`). Validated on EYG_28 RPGRIP1_cpdHet Sig: overlap
  **14 → 850 / 1173**, real terms (ER lumen, basement membrane, V-ATPase, brush border) vs the prior immune noise. Commits
  `f01ddbc` / `a9d16f1` / `102d9ec` / `01d32c8`; scope in `docs/p1-skills-scope.md`. **3rd dataset assessed (owner-pointed): EYG_05**
  (`…/RNA seq/Analysis/20220318_…EYG_05`) — 2022 RUV/limma, PDE6B + RPGRIP1 **mutation** contrasts (NOT time-course); raw counts
  likely in its 478 MB `.RData` (→ could unblock pyDESeq2 `deg`); ships GO/KEGG enrichment results (= an enrichment oracle).
  **Open: push 5 commits.** **Next P1 (approved sequence):** DE-table import + use-existing-embedding (quick wins) → `pathway`
  (Reactome live API; KEGG academic-only) → `go-graph` → `deg` time-course (still blocked — no count+time dataset across the three).
- **Last (2026-06-14) — P1 quick wins DONE: DE-table-aware enrichment + use-existing-embedding (`fd8b3c2`).** `enrichment`
  now derives the query from the SIGNIFICANT rows of a full DE table (new fdr/fc params) — dogfooded on EYG_28 DEGs_All
  (16,760 → 6,266 sig@FDR0.05 → real GO terms). `umap_scrna` gained an `embedding` param to plot a stored UMAP/t-SNE with no
  recompute — dogfooded on rpgrip1 (`X_tsne_all` → the ShinyCell **retinal cell-type** t-SNE: Rods/Cones/Bipolar/Amacrine/Glial),
  saved to `…/rpgrip1/processed/figures/`. pytest 53; ruff clean. **Open: push 1 commit.** **Next P1 (bigger, NEW skills):**
  `pathway` (Reactome ContentService live; **open design Q** — Reactome pathway diagrams aren't natively editable-Plotly, so the
  render representation needs a decision) → `go-graph` (GO DAG node-link via obonet+networkx — cleaner to render). `deg`
  time-course still data-blocked; EYG_05's 478 MB `.RData` raw counts could unblock pyDESeq2 `deg` if extracted.
- **Last (2026-06-14) — `go_graph` skill DONE (`835f50e`) + ALPK1 datasets scouted & verified.** New **`go_graph`** draws the top
  enriched GO terms as an editable **DAG node-link** (ORA → transitive-reduced is_a/part_of hierarchy → networkx layout → Plotly);
  `build_gene_sets.py` also emits `go_dag.json` (gitignored). Validated on EYG_28 RPGRIP1 Sig (20 nodes / 10 edges); pytest 55; ruff
  clean. **3 ALPK1 folders scouted (subagents) + headline claims self-verified** → cataloged in **`docs/real-datasets.md`** (memory
  `selom-real-datasets`): biochemical = phospho-proteomics n=1 (not a fit; future proteomics fixture); single-cell = downstream-only
  (no cell object shared; 201 MB Seurat DEG CSV → volcano/heatmap/enrichment, no UMAP/cluster); **bulk = goldmine — the mouse
  P14/P30/P90 set has raw counts (verified 32,285 × 77 integer) + an 18-contrast DE table over 3 timepoints → UNBLOCKS `deg`
  time-course AND raw-count pyDESeq2.** NB real bulk data is `.xlsx`; skills read CSV (openpyxl now in the venv; xlsx-ingestion in
  skills is a follow-up — EYG29 has CSV raw-count pairs that work today). **Open: push `go_graph` + these docs.** **Next P1:**
  `pathway` (Reactome, approach A — last P1 skill) OR pivot to the now-unblocked `deg` raw-count / time-course on the mouse data.
- **Resume:**
  ```
  # Resume · 2026-06-13 · Selom · Claude (frontend + backend, acting)
  Selom build repo D:/selom. CLAUDE.md auto-loads. Read agent_handoff/README.md + CURRENT.md (this) + DECISIONS.md + RISKS.md + docs/build-charter.md + docs/competitors/omicsbox.md + DESIGN.md + plans/v2-backend.md + plans/v2-frontend.md + docs/integrations.md.
  ROLE: Codex away → Claude owns BOTH lanes. Keep BE drop-in-ready: accurate `## Codex` section, explicit per-lane scoped commits (never git add -A). Selom is DESKTOP-ONLY.
  Delta: B4 publish-confidence slice-1 DONE (both lanes) and PUSHED — main ↔ origin/main in sync (BE 2ab7c43 + FE 84ae54e). 2026-06-13 (research/planning, no lane code): filed OmicsBox teardown docs/competitors/omicsbox.md (6a139ad); threaded P1→P4 priorities into docs/build-charter.md (7c3189e); landed DECISIONS #10 (skill-scope bet: win the editable-figure last mile + own proteomics/metabolomics whitespace, don't chase upstream NGS); switched model Fable 5→Opus 4.8 (xhigh) (267ab50, applies on restart). Per-figure reproducibility bundle (provenance.py: skill+ver, resolved+typed params, input SHA-256+size, env=python/platform/engine-policy+pkg versions) + auto methods-text (methods.py: per-skill templates + canonical citations; generic fallback) + contract.resolved_params(). /run + /jobs/{id}/result now return {figure, provenance, methods} (jobs thread filename + store full bundle via execute_job). FE: collapsed "Publish confidence" panel (components/project/publish-confidence.tsx) — Methods (Copy+citations) + Reproducibility; runSkill returns the bundle; MSW mock serves it (mocks/stub-bundle.ts). pytest 28 passed; ruff clean; uvicorn smoke green; FE tsc+next build clean; browser-verified (mock :3010, POST /run 200, console clean bar favicon 404).
  FIRST: nothing pending push — main ↔ origin/main in sync (all session work pushed 2026-06-13); push only when asked. Docker/WSL-gated items are parked in agent_handoff/on-hold/ (ask owner before any Docker/WSL). Env: backend on user-managed py3.12 (uv at C:/Users/seamegdool/.local/bin/uv.exe); system py3.10 IT-locked. Run via `uv run --directory app/backend python -m pytest` / `-m uvicorn`. Jobs default inline+local; SELOM_QUEUE=arq + R2_* + [jobs] extra flip on Redis/R2. Skills stub vs real via SELOM_SKILLS_ENGINE; golden tests pin stub. FE dev `npm run dev:mock -- --port 3010`. demo.h5ad gitignored — regen via scripts/make_demo.py.
  Next: finish B4 — Kaleido journal export ONLY (guardrail expansion DONE, guardrails.py; Kaleido needs Docker+Chromium, RISKS #2 → lands with deploy image; ASK OWNER before any Docker/WSL work). Then integration backlog (OmicVerse isolated worker, arq Redis status store, R-oracle, full GMT, catalog true-up). Stay on Opus 4.8 (xhigh). End clear-safe.
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
- **Last (done by Claude, acting BE, 2026-06-12 02:45) — B4 publish-confidence backend slice-1 DONE; COMMITTED `2ab7c43`, NOT pushed**
  (`main` ahead 2 of `origin/main`). New `provenance.py` = per-figure reproducibility bundle (skill+version, resolved+typed params,
  input **SHA-256**+size, environment = python/platform/engine-policy + scientific-stack versions via `importlib.metadata`). New
  `methods.py` = auto methods-text (deterministic per-skill templates quoting params + canonical citations; generic fallback).
  `contract.resolved_params()` = typed param coercion (runners untouched). **Additive wire change:** `POST /skills/{id}/run` +
  `GET /jobs/{id}/result` now return `{figure, provenance, methods}` (same shape both paths); `Job` gained `filename`, `submit`/
  `execute_job` thread it, the shared `execute_job` stores the full bundle (`result_store.put` param figure→payload). `pytest` =
  **28 passed** (21 + `test_provenance.py` + `test_methods.py` + jobs-bundle asserts); ruff clean; live uvicorn smoke green.
  **No new deps** (stdlib hashlib/platform/importlib.metadata). FE half is committed separately (`84ae54e`).
- **Next (finish B4, then integration backlog):** **B4 remaining** — (a) **statistical-guardrail expansion DONE** by Claude
  (`guardrails.py` adds a `guardrails` list to the bundle: multiple-testing / FDR method checks + best-effort `.h5ad` low-cell /
  pre-normalized / uncorrected-batch; cluster silhouette stays in the runner; commit `edd3615`), (b) **Kaleido journal export**
  PNG/SVG/PDF — needs **Docker + system Chromium** (RISKS #2 / DECISIONS #7), so it lands with the deploy image (B8-adjacent);
  scope a CPU-Docker path or defer — **ASK OWNER before any Docker/WSL work**. **Integration backlog (`docs/integrations.md` + `plans/v2-backend.md`):**
  OmicVerse **isolated** 2nd engine/Foundry source — pins `pandas<3`, CANNOT share this venv (RISKS #9); run out-of-process (its MCP
  server / a worker), SCA-gate 50 deps; the **arq Redis status store**; R4DS/Quarto + R-oracle (RISKS #7); full GO/Reactome GMT;
  catalog-count true-up (≈418). sklearn is core (silhouette in `cluster`). Explicit staging only (never `git add -A`); `feat(backend:)` scope.
- **Resume:**
  ```
  # Resume · 2026-06-12 02:45 +10:00 · Selom · Codex (backend) — reclaiming from Claude
  Selom build repo D:/selom. CODEX.md auto-loads. Read agent_handoff/README.md + CURRENT.md + DECISIONS.md + RISKS.md + docs/build-charter.md + plans/v2-backend.md + docs/integrations.md + git status.
  Delta: B1 + B2 + B3 + B4-slice-1 backend DONE by Claude, ALL PUSHED (main ↔ origin/main in sync; B4 backend 2ab7c43 + FE half 84ae54e). B4 = provenance.py (per-figure reproducibility bundle: skill+ver, resolved+typed params, input SHA-256+size, env=python/platform/engine-policy+pkg versions) + methods.py (auto methods-text, per-skill templates + citations) + contract.resolved_params(). /run + /jobs/{id}/result now return {figure, provenance, methods}; Job.filename added; shared execute_job stores the full bundle; result_store.put param figure→payload. No new deps. pytest 28 passed; ruff clean; uvicorn smoke green.
  Open BE items: (1) arq cross-process job STATUS needs a Redis-backed JobStore (jobs/worker.py caveat). Next: finish B4 — Kaleido export ONLY (guardrail expansion DONE — guardrails.py edd3615; Kaleido needs Docker+Chromium, RISKS #2 — ASK OWNER before any Docker/WSL) — then integration backlog (OmicVerse isolated worker, R-oracle, full GMT, catalog true-up). Env: user-managed py3.12 (uv); system 3.10 IT-locked; `uv run --directory app/backend python -m pytest`/`-m uvicorn`. Stay on Opus 4.8 (xhigh). End clear-safe.
  ```
