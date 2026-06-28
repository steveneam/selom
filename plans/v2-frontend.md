# v2 — Frontend lane (Claude owns `app/frontend/`)

> **HISTORICAL (2026-06-29).** Superseded by `docs/pillars/plan.md` +
> `docs/aws-materialization/plan.md`. Kept for the original P0 framing only.

Next.js 16 (App Router) + React 19 + Tailwind v4 + shadcn/ui. Renders the
editable Plotly figure the backend returns and lets the user edit it no-code.
Talks to the backend over `NEXT_PUBLIC_API_BASE` (default `http://localhost:8000`).

## P0 — first end-to-end figure

### 1. Upload UI
- A page that accepts an omics file (`.h5ad` / matrix), `POST`s it to `/upload`,
  and holds the returned dataset handle.
- Show upload state (idle → uploading → ready → error). No styling perfectionism
  yet — get the data in.

### 2. Render the editable figure
- Call `POST /skills/{skill}/run` (start with `hello-UMAP`) and render the
  returned Plotly JSON with **react-plotly.js**.
  - `react-plotly.js@2.6.0` + `plotly.js` need `--legacy-peer-deps` (peer-deps
    claim React ≤18; it still renders fine on 19).
- Integrate against the backend **stub** first (canned figure), so the render
  path is proven before the real UMAP runner lands.

## P1 — the no-code property panel

### 3. shadcn/ui control panel + JSON-Patch
- Build a custom property panel on **shadcn/ui** controls (sliders, color
  pickers, selects, inputs) bound to the live Plotly figure spec.
  - `react-chart-editor` is **dead** (no React 18/19) — do **not** use it. We
    build our own panel.
- Each control edits the figure spec by emitting **RFC-6902 JSON-Patch** ops;
  apply patches to the in-memory spec and re-render live.
- On save, send the patched spec back to the backend to validate/persist.
- Add an **Export** action → `POST /figures/{id}/export` → download PNG/SVG/PDF.

## C1–C3 — the command center (project-first IDE)

Turns the single upload→editor surface into a **project-first command center**.
Full design: `../docs/command-center/design.md`. Mock-first (no backend dependency);
the figure editor (P1) is **reused unchanged** as the Project ▸ Figure view.

### C1 — command-center shell
- Project-first IA: persistent **left rail** (Home, Skill Store, **Projects +**,
  Settings) + context **main stage** + contextual right inspector. Routes:
  `/` (Home dashboard), `/store`, `/p/{id}` (Overview/Data/Workbench/Figure).
- `ProjectStore` interface + **localStorage** impl in `lib/projects/` — designed to
  match the planned Supabase schema (design §5) so the later swap is mechanical.
  **No component touches Supabase directly** — everything goes through `ProjectStore`.
- Dock the existing figure editor as `/p/{id}/fig/{figId}`. Refactor `app/page.tsx`'s
  single flow into the shell, preserving upload→editor as Data → Workbench → Figure.

### C2 — Skill Store (the "App Store")
- Seed `lib/catalog/` with `SkillCatalogEntry` rows (design §3.1) mocking the full
  ~600-skill catalog (ClawBio `catalog.json` shape + bioSkills categories).
- Browse/filter by category/omics/tier; skill cards + detail; **Install → project**
  (adds a `skill_installs` row to the mock store). **Tier honesty:** Verified =
  installs+runs; Community = "Queued — runs in a future sandbox" (no silent caps).
- ✅ **DONE (B3, 2026-06-12) — registry-driven.** `lib/catalog/registry.ts` fetches live `GET /skills`, merges the
  Verified slice over the seed's Community tail, falls back to the seed offline; `CoverageMeter` shows the live
  runnable count; MSW mocks `/api/skills`. The seed now backs only the Community long-tail + `getSkill()` name lookups.

### C3 — guided intake
- Adaptive questionnaire (by detected modality) shown after upload **when no skills
  are pre-picked** (skippable otherwise): organism, cell type of interest,
  condition/disease, expected findings, design.
- `IntakeProposal` renderer (design §4.3): editable plan (cleaning steps + proposed
  skills + pre-filled params + rationale/confidence) with a prominent **Run**.
- Mock `POST /intake` (deterministic stub keyed off modality) + mock ingest/QC report
  with guardrail flags; swap for B2 when live. **LLM proposes, user approves.**

## B4 (charter) — publish-confidence panel · 🟡 SLICE-1 DONE 2026-06-12 (committed `84ae54e`, not pushed)
- `runSkill` (`lib/skills-api.ts`) now returns the full `{figure, provenance, methods}` bundle
  (typed `SkillProvenance`/`SkillMethods`, both optional so the figure still renders without them).
- `components/project/publish-confidence.tsx` — collapsed-by-default panel in the Figure tab
  (between the editor toolbar and the figure): **Methods** (prose + Copy[text+numbered citations] +
  citation list) + **Reproducibility** (skill+version, param chips, input filename/size/SHA-256, env
  Python + scientific-stack chips). `project-workspace` captures the bundle on run, clears on "New figure".
- MSW mock serves a representative bundle (`mocks/stub-bundle.ts`) so the panel renders offline.
- Verified: `tsc` + `next build` clean; browser-verified (mock :3010) — panel expands with methods + repro record.
- **Next (FE half of B4 remaining):** surface statistical guardrails when the bundle carries them; a
  journal-preset **Export** affordance once the backend Kaleido path exists.

## Notes
- Tailwind **v4** = CSS-first config (`@theme`, no `tailwind.config.js`).
- React Compiler auto-memoizes — don't over-hand-roll `useMemo`.
- The figure spec (Plotly JSON) is the single source of truth for the figure;
  the panel only ever mutates it via patches. Keep render = f(spec).
- Commercial/licensing gates are **deferred** (see `../LAUNCH-GATES.md`).
