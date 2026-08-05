# Selom — Roadmap

> **HISTORICAL (2026-06-29; re-confirmed stale 2026-08-05).** This P0→v2 / C-B framing is
> superseded — **do not plan against anything below.** Kept for historical context only.
>
> **The live plans are:**
> - **`docs/pillars/plan.md`** — the engine spine, pillars P1–P5 (P1–P4 effectively complete)
> - **`docs/build-plan-2026-08/plan.md`** — product phases P-A…P-E + the measured status table
> - **`agent_handoff/CURRENT.md`** — live state + the NEXT board
> - `docs/aws-materialization/plan.md` — deploy (owner chose "this box first, AWS later")
>
> The infra named below (Supabase / Redis / R2 / Kaleido) is superseded by the AWS plan. The
> "Current: scaffold done, next gate P0 hello-UMAP" line was ~44 skills and ~15 sessions ago.

## Phases

| Phase | Goal | Exit |
|---|---|---|
| **P0** | hello-UMAP end-to-end | Biologist uploads `demo.h5ad` -> Scanpy runs -> Plotly spec -> editable UMAP renders -> a style change applies client-side without recompute |
| **P1** | Supabase + auth | `/run` endpoint gated by Supabase JWT; job rows persisted in Postgres (`projects` / `jobs` / `skill_runs`) |
| **P2** | Async queue (arq + Redis) | Full async path: POST -> 202 + job_id -> SSE status -> figure on completion |
| **P3** | Export (Kaleido) | Server-side PNG/SVG/PDF via Kaleido v1 + system Chrome; upload to R2; presigned download |
| **v2** | Extract-Skills | Drop a paper/repo -> auto-generate a reproducible custom skill (sandboxed). Do not start until v1 is live |

## Command-center expansion (C / B phases)

The P0–v2 line above ships the *engine* (one skill → editable figure). The **C/B
phases** turn it into the **project-first command center / IDE** the product is:
projects sidebar + Skill Store (browse/install ~600 bioSkills + ClawBio skills) +
guided LLM intake + auto-clean. Full design: `docs/command-center/design.md`.
FE (`C`) phases are mock-first and unblocked; BE (`B`) phases are owned by Codex
(filed in `CURRENT.md` → Cross-Agent Requests).

| Phase | Lane | Goal | Exit |
|---|---|---|---|
| **C1** | FE | Project-first shell: left rail, projects sidebar, Home dashboard, routing; `ProjectStore` mock (localStorage). Figure editor docked as Project ▸ Figure. | Create a project → see it in the sidebar → open it → reach the editor (all mock); `tsc` clean, browser-verified. |
| **C2** | FE | Skill Store: ingest the full catalog as `SkillCatalogEntry` (seed mock), browse/filter by omics/tier, skill detail, Install → project, tier/coverage honesty. | Browse ~600 skills, filter, install a Verified skill into a project. |
| **C3** | FE | Guided intake: adaptive questionnaire, `IntakeProposal` plan renderer, Workbench run flow; mock `POST /intake` + ingest/QC report. | Drop file → answer questions → editable proposed pipeline → Run (mock) → figure opens. |
| **B1** | BE | Skill registry API (`GET /skills`, `GET /skills/{id}`) from the real ingested manifest. | FE catalog reads the live registry; skill picker fully registry-driven. |
| **B2** | BE | Real ingest/QC (`POST /upload`) + real `IntakeProposal` (`POST /intake`) via the AI gateway. | Guided path works end-to-end against the live backend. |
| **B3** | BE | Generalize `/skills/{id}/run`; **Skill Foundry (manual)** ports the wedge + selected ClawBio skills; async via arq. | ≥6–8 Verified skills run live + return editable specs. |
| **B4** | BE | Swap `ProjectStore` mock for Supabase (schema in design §5 + RLS + auth). | Projects/datasets/figures persist per-user; mock retired. |
| **v2+** | BE | Community-skill **sandbox** executor (`engine: agent-sandbox`) + **LLM-assisted Foundry** (= Extract-Skills moat) to burn down the 500-skill backlog. | A Community skill runs in a sandbox; a paper/repo auto-generates a Verified skill. |

**North star (owner directive, 2026-06-11):** every one of the 500+ catalog skills
eventually runs in Selom — hand-ported and/or sandboxed. Runnable-coverage is a
tracked, visible metric; the catalog is fully browsable from day one (browsable ≠
runnable shown honestly).

**Execution toolchain (design §6.5):** what we download/install to test+run skills —
**(A)** clone ClawBio + bioSkills, parse `catalog.json`/`SKILL.md` → seed manifest
(cheap, do-now); **(B)** Verified runners via the existing `[omics]` extra
(`uv sync`: scverse + plotly/kaleido) **+ OmicVerse as a second engine / primary
Skill-Foundry source, run OUT-OF-PROCESS in an isolated env** (it pins `pandas<3`, so it
can't share the backend venv — see `docs/records/external-integrations.md` + RISKS #9); **(C)** ClawBio
runnable via `pip install clawbio` + Miniforge/mamba per-skill `environment.yml` +
bioconda; **(D)** bioSkills long tail via the bioconda CLI toolchain (samtools/STAR/GATK4/
Snakemake/Nextflow…) promoted through the Skill Foundry; **(E)** Community sandbox via
Docker + mamba images (v2, deferred). A+B immediate, C next, D/E incremental. License-clean
primitives (sklearn — clustering-quality guardrails, hierarchical ordering) are in core.

**Integrations research:** `docs/records/external-integrations.md` — OmicVerse (engine/Foundry source,
isolated), scikit-learn (now core), R4DS/Quarto+ggplot2 (B4 methods-text/repro + R oracle),
Hermes (aggregator pattern + catalog-count true-up). MCP: context7 (docs), OmicVerse/JARVIS
(isolated worker boundary).

## First 10 Days (P0 detail, from build dossier section 10)

Goal: land the P0 gate — first end-to-end editable UMAP from a real h5ad file — by Day 10. Days 1-3 are mechanical setup; Days 4-10 wire the stack. P0 gate passes on Day 6; Days 7-10 are production hardening.

| Day | Focus | Exit criterion |
|---|---|---|
| 1 | Repo + toolchain (uv, Next.js, Docker/WSL2; verify scanpy import) | `uv sync` green; Next.js dev server starts; no import errors |
| 2 | Skill contract scaffold (SkillSpec + loader; `umap_scrna/run.py`) | `run_skill("umap_scrna", "demo.h5ad", {})` returns a Plotly dict in a REPL |
| 3 | Demo dataset (`sc.datasets.pbmc3k()` -> `demo.h5ad`; run `run.py`) | Plotly spec JSON on stdout; no Scanpy errors |
| 4 | FastAPI skeleton (`main.py`; POST `/skills/umap_scrna/run`) | FastAPI returns 200 with Plotly spec for the UMAP skill |
| 5 | Next.js frontend (`app/page.tsx`; proxy `/api/*` -> `:8000`; upload + render) | Interactive UMAP renders in the browser from a real h5ad upload |
| 6 | Editable spec + style panel MVP (shadcn/ui colour picker -> JSON-Patch, client-side) | One colour/title change applied client-side; **P0 gate passed** |
| 7 | Supabase wiring (`projects`/`jobs`/`skill_runs`; JWT middleware; gate `/run`) | Auth-gated run endpoint; Postgres records the job row |
| 8 | Async job queue (arq worker; move run off the handler; SSE status) | Full async path POST -> 202 + job_id -> SSE -> figure on completion |
| 9 | Kaleido export (Docker + chromium; `/jobs/{id}/export?format=png` -> R2) | Browser downloads a correct PNG of the UMAP from R2 |
| 10 | CI + SCA scan (Actions: `uv sync` + `pytest` + `npm run build`; AGPL/non-commercial dep scan) | CI green; license scan output triaged |

## P0 gate definition

A biologist uploads `demo.h5ad` -> backend runs Scanpy -> returns a Plotly spec -> frontend renders an interactive, editable UMAP coloured by Leiden cluster -> a style change is applied client-side without recompute.

## Sequencing note

Commercial/licensing gates are deferred (build now, gate before launch). Source of record: build dossier section 10 at
`C:/Users/seamegdool/Desktop/Claude code and website tips/EAMOS Web Tool/Selom/Wiki/product/selom-build-dossier.md`.
