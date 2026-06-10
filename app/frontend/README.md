# Selom — frontend

Next.js 16 + React 19 + TypeScript + Tailwind 4 frontend for Selom, a no-code multi-omics figure SaaS.

## Quickstart

```bash
npm install --legacy-peer-deps   # react-plotly.js is stale (peer-deps cap React at <=18)
npm run dev                      # http://localhost:3000
```

The dev server runs on port **3000**. All `/api/*` requests are proxied to the FastAPI
backend on **http://localhost:8000** (see `next.config.ts` rewrites), so start the backend
separately (`uv run uvicorn main:app --reload` from `app/backend`).

## What's here

- `app/page.tsx` — minimal upload → run → render flow. Picks a `.h5ad`/`.csv` file, POSTs it
  to `/api/skills/umap_scrna/run`, and renders the returned Plotly spec via `react-plotly.js`
  (dynamic import, `ssr: false`).
- `app/layout.tsx` — root layout, Inter via `next/font/google`.
- `app/globals.css` — Tailwind v4 CSS-first (`@import "tailwindcss"`).

## Roadmap — the no-code figure editor

The future no-code figure editor is a **custom shadcn/ui property panel** bound to the
Plotly `layout`/`data` paths, emitting **RFC-6902 JSON-Patch** against the editable figure
spec (one patch protocol shared by the panel and the LLM copilot). Plotly's
`react-chart-editor` is **dead** (last publish Nov 2023, no React 18/19 support) — do **not**
build on it.

When doing UI work, invoke the **`ui-ux-pro-max`** and **`frontend-design`** skills.
