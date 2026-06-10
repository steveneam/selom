# v2 — Frontend lane (Claude owns `app/frontend/`)

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

## Notes
- Tailwind **v4** = CSS-first config (`@theme`, no `tailwind.config.js`).
- React Compiler auto-memoizes — don't over-hand-roll `useMemo`.
- The figure spec (Plotly JSON) is the single source of truth for the figure;
  the panel only ever mutates it via patches. Keep render = f(spec).
- Commercial/licensing gates are **deferred** (see `../LAUNCH-GATES.md`).
