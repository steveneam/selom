# Selom — CURRENT (Live State)

> **LIVE STATE ONLY.** The current state of the two-agent build. History lives in
> each agent's rolling log, not here. This file is **replaced, never stacked** —
> update at MAJOR boundaries only (rule 9 in `agent_handoff/README.md`).

_Last updated: 2026-06-10 23:18 +10:00 · Claude — no-code figure-editor framework (P1) built + verified in-browser against the MSW mock; FE uncommitted_

**Model:** stay on **Fable 5** for all Selom work — Selom carries no biology/security
flag. Only *reading the EAMOS build repo* escalates a session to Opus, and that
source is not needed here. Do not switch to Opus for Selom.

## Active Status

| Agent | Role | Lane | Status |
|---|---|---|---|
| Claude | Frontend (UI/design/product copy) | `app/frontend` + `plans/v2-frontend.md` | ACTIVE — no-code figure-editor framework (P1) built on the real dark-IDE brand + verified in-browser (upload→render→JSON-Patch live edit→undo, MSW mock, :8000 DOWN). `tsc --noEmit` clean. FE changes uncommitted. |
| Codex | Backend (APIs/skill runners/data/tests) | `app/backend` + `plans/v2-backend.md` | IDLE — skeleton scaffolded + committed; P0 not started |

Roles are explicit; any swap is written here before work proceeds.

## Log Edit-Lock

UNLOCKED

## Shared File Locks

None held.

## Cross-Agent Requests

- **GitHub: connected ✓** Pushed to **github.com/steveneam/selom** (private) on
  2026-06-10 21:15 +10:00 — `main` tracks `origin/main` (in sync). Commits: `4ccb6b6`
  scaffold + `e3dd7cd` CURRENT.md sync. Commit identity is local
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

- **Last:** Built the **no-code figure-editor framework (P1)** against the MSW mock, on the **real
  dark-IDE brand** (deep blue-black shell, cyan accent, glassy panels, molecular hex mark; the figure
  sits on a light "paper" artboard). Layers:
  - **Design system** — Tailwind v4 `@theme` brand tokens in `globals.css`, Geist + Geist Mono fonts,
    shadcn-style primitives on Radix in `components/ui/` (button/input/label/slider/select/switch/tabs/
    separator/tooltip/scroll-area/card), `components/brand/selom-mark.tsx`, `lib/cn.ts`.
  - **Core engine** — `lib/figure-spec.ts` (normalize + publication defaults + colourways), `lib/patch.ts`
    (RFC-6902 apply + `classifyPatch` client-vs-server boundary), `lib/skills-api.ts`,
    `hooks/use-figure-store.ts` (spec = source of truth + checkpoint undo/redo; same patch protocol the
    future LLM copilot will use).
  - **Editor** — `components/figure/*` (canvas = f(spec); tabbed Inspector Style/Axes/Legend/Data/Page,
    each control emitting JSON-Patch), `components/upload/upload-hero.tsx`, `components/app/top-bar.tsx`;
    `app/page.tsx` rewired into the workspace (+ ⌘Z/⌘⇧Z undo/redo).
  - Deps added: radix primitives, `fast-json-patch`, `class-variance-authority`/`clsx`/`tailwind-merge`,
    `lucide-react`, `geist`, `@types/react-plotly.js`. Added `app/frontend/.gitignore` (tsbuildinfo /
    next-env.d.ts / dev screenshots).
  **Verified in-browser** (chrome-devtools, `npm run dev:mock`, **:8000 DOWN**): upload `demo.csv` →
  editable UMAP renders → palette select recolours the live figure (Okabe-Ito↔Viridis) → **undo reverts**;
  live slider point-size 7→10. `tsc --noEmit` clean, zero console errors. **FE changes uncommitted.**
- **Next:** wire the **Export** action + journal `layout.template` presets; omics-specific panels (volcano
  threshold + label-top-N, color-by-gene → server recompute via `classifyPatch`); make the skill picker
  **registry-driven** from `GET /skills/{id}`. When Codex boots :8000 + confirms the P0 contract, run
  `npm run dev` (mock off) to verify LIVE. Owner decision still open: commit now or fold into first P0 commit.
- **Resume:**
  ```
  # Resume · 2026-06-10 23:18 +10:00 · Selom · Claude (frontend)
  Selom build repo D:/selom. CLAUDE.md auto-loads. Read agent_handoff/README.md (protocol) + CURRENT.md (this) + plans/v2-frontend.md.
  Delta: no-code figure-editor framework (P1) built on the real dark-IDE brand + verified in-browser (upload→render→JSON-Patch live edit→undo) against the MSW mock with :8000 DOWN (`npm run dev:mock`). spec=source-of-truth + RFC-6902 engine in lib/ + hooks/; shadcn-style UI on Radix. tsc clean. FE uncommitted.
  Next: Export + journal presets + omics panels + registry-driven skill picker; verify LIVE when Codex boots :8000 + confirms contract. Stay on Fable 5. End clear-safe.
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
