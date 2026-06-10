# Selom — Roadmap

**Current:** scaffold done (repo skeleton + agent-boot files). Next gate: P0 hello-UMAP.

## Phases

| Phase | Goal | Exit |
|---|---|---|
| **P0** | hello-UMAP end-to-end | Biologist uploads `demo.h5ad` -> Scanpy runs -> Plotly spec -> editable UMAP renders -> a style change applies client-side without recompute |
| **P1** | Supabase + auth | `/run` endpoint gated by Supabase JWT; job rows persisted in Postgres (`projects` / `jobs` / `skill_runs`) |
| **P2** | Async queue (arq + Redis) | Full async path: POST -> 202 + job_id -> SSE status -> figure on completion |
| **P3** | Export (Kaleido) | Server-side PNG/SVG/PDF via Kaleido v1 + system Chrome; upload to R2; presigned download |
| **v2** | Extract-Skills | Drop a paper/repo -> auto-generate a reproducible custom skill (sandboxed). Do not start until v1 is live |

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
