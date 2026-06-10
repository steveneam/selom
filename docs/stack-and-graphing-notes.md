# Stack & graphing notes

Answers the owner's tooling question directly: **what draws Selom's figures, and
is the Python calc/graphing stack ready?**

## Production figure engine — Plotly + Kaleido (NOT matplotlib / ggplot2 / R-Shiny)

- **Render / edit:** **Plotly** is the figure engine. Skills emit a **Plotly JSON
  spec** — a serializable, editable artifact. The frontend renders it with
  react-plotly.js and the no-code panel edits it via RFC-6902 JSON-Patch. The
  editable JSON spec is the whole point: it is what makes the figures no-code
  editable post-generation.
- **Static export:** **Kaleido** turns the Plotly spec into static **PNG / SVG /
  PDF** server-side. (Kaleido v1 no longer bundles Chromium — it needs a system
  Chrome in the Docker image. EPS was dropped.)
- **NOT matplotlib:** matplotlib is **not** a Selom output engine. It only rides
  along **transitively inside scanpy** (some scanpy plotting helpers use it
  internally); we don't render product figures with it.
- **NOT ggplot2 / R-Shiny:** R (and ggplot2 / Shiny) is **validation-only** per
  ADR 0002 — used to cross-check numerical results from R-native methods
  (e.g. limma / MSstats behind the skill contract's `engine: r`), never as the
  product's graphing layer.

## Python calc / graphing readiness

- **CORE deps (always installed):** `numpy`, `pandas`, `scipy` — the numerical
  base for every skill. Ready.
- **`[omics]` extra:** `scikit-learn`, `statsmodels` (plus the scverse stack:
  scanpy, anndata, scvi-tools, decoupler, pydeseq2, gseapy; proteomics:
  alphastats, pyteomics). Installed on demand for the analysis skills.
- **Graphing:** `plotly` (spec) + `kaleido` (export) in the plotting deps.

## §1 version table (verified 2026-06-04 — re-verify at real build time)

> Source: Selom vault `Wiki/syntheses/build-setup-and-toolchain.md` §1. Versions
> were verified against PyPI/npm/GitHub mid-2026; **re-verify at real build time**
> before pinning.

### Python core
| Tool | Version | Gotcha |
|---|---|---|
| Python | 3.12 (target) / 3.13 OK | scanpy/scvi-tools need ≥3.12; avoid 3.11 |
| uv | 0.11.x | single-binary pip/venv/poetry replacement |
| NumPy | 2.4.x | NumPy 2.x ABI; don't pin `numpy<2` |
| pandas | 3.0.x | Copy-on-Write default; no in-place slice mutation |

### scverse / single-cell + bulk RNA-seq
| Tool | Version | Gotcha |
|---|---|---|
| scanpy | 1.12.x | scRNA workhorse (QC/normalize/PCA/UMAP/cluster) |
| anndata | 0.12.x | pin `<0.13` (0.13 is rc) |
| scvi-tools | 1.4.x | pulls PyTorch; install CPU torch first in CPU workers |
| decoupler | 1.9.x | pathway/TF activity |
| PyDESeq2 | 0.5.x | bulk RNA-seq DE; now scverse-maintained |
| gseapy | 1.2.x | GSEA/Enrichr, no R needed |

### Proteomics
| Tool | Version | Gotcha |
|---|---|---|
| alphastats | 0.7.x | label-free proteomics DE/volcano; quiet since Nov 2025 |
| pyteomics | 5.0 | low-level mzML/FASTA/pepXML parsing |

### Stats / ML / web / async
| Tool | Version | Gotcha |
|---|---|---|
| statsmodels | 0.14.x | required by PyDESeq2 |
| scikit-learn | 1.9.x | NumPy-2 compatible |
| FastAPI | 0.136.x | Pydantic v2 only (v1 shim removed) |
| uvicorn | 0.49.x | bundled in `fastapi[standard]` |
| pydantic | 2.13.x | v2 — skill `param_spec` validation |
| arq | 0.28.x | Redis async queue; maintenance-only mode |
| Redis | 8.x | broker for arq + cache |
| boto3 | 1.43.x | R2 client; set checksum `when_required` |

### Plotting / export
| Tool | Version | Gotcha |
|---|---|---|
| plotly (py) | 6.8.x | the figure-spec engine; skills emit Plotly JSON |
| kaleido | 1.3.x | v1 needs system Chrome for static export; EPS dropped |

### Frontend
| Tool | Version | Gotcha |
|---|---|---|
| Node.js | 24 LTS | 26 isn't LTS until Oct 2026 |
| Next.js | 16.x | App Router; explicit caching (opt in) |
| React | 19.2.x | React Compiler auto-memoizes |
| TypeScript | 6.0.x | don't use TS 7.0 beta in prod |
| Tailwind CSS | 4.x | CSS-first config (`@theme`, no config.js) |
| react-plotly.js | 2.6.0 | stale; needs `--legacy-peer-deps` (React ≤18 peer) |
| shadcn/ui | latest | control-panel components for the figure editor |

### DevOps / account CLIs
| Tool | Version | Note |
|---|---|---|
| Docker Desktop | 4.75 | WSL2 backend on Win11; bundles Engine 29 |
| GitHub CLI | 2.92.x | repo/PR/secrets automation |
| Supabase CLI | 2.104.x | migrate via `supabase db push` |
| Stripe CLI | 1.40.x | `stripe listen` for local webhooks |
| Vercel CLI | 54.x | pin `npx vercel@54` in CI |
