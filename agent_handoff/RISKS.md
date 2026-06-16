# Selom — RISKS (Build Landmines)

> Seeded from the Selom Build Dossier §2 (Findings & landmines). These are the
> known traps that will silently break the P0 build if ignored. Each carries the
> fix. Add new risks as they surface; do not delete — supersede with a resolution
> note.

_Last updated: 2026-06-16 — **#6 CORRECTED**: `gseapy` is **BSD-3** (verified the LICENSE), NOT AGPL — removed from the AGPL list (it was conflated with MSigDB's restricted *data*); MSigDB-data restriction stays, decoupler re-checked separately. #9 note corrected to match (gseapy was simply unused, not AGPL surface). Prior: 2026-06-15 13:52 +10:00 — #2 RESOLVED for the feature (Kaleido export shipped native, no Docker; Docker only for the B8 deploy image). Prior: #5 R2 checksum fix APPLIED (B3, dormant); #9 `gseapy` DROPPED from `[omics]` (B3)._

| # | Risk | Impact | Fix / mitigation | Owner |
|---|---|---|---|---|
| 1 | **`react-chart-editor` is dead** (last publish Nov 2023, no React 18/19) | The assumed no-code figure-property-panel engine is unusable | Build a custom panel: `react-plotly.js` (render) + shadcn/ui (controls) -> RFC-6902 JSON-Patch. Same patch protocol as the LLM copilot. | Claude (FE) |
| 2 | **Kaleido v1 needs system Chromium** — v1 no longer bundles Chromium | Server-side PNG/SVG/PDF export fails | **RESOLVED for the feature (2026-06-15):** Kaleido drives the *installed* Chrome over CDP, so on any box with a browser it needs **no Docker** — `POST /figures/export` shipped + verified native on Windows (kaleido 1.3, plotly 6.8). **Deploy image only:** the Linux server has no browser → `apt-get install -y chromium` (+ `KALEIDO_CHROME_PATH` if not auto-discovered) in the **B8** image. So: not a runtime container dependency, just a deploy-image install. | Codex (BE) / B8 |
| 3 | **`react-plotly.js` is stale** (React <=18 peer-deps) | `npm install` fails without a flag | Always install with `--legacy-peer-deps`; monitor for a React 19 PR | Claude (FE) |
| 4 | **pandas 3.0 Copy-on-Write is default** | Chained assignment raises `ChainedAssignmentError` in skill code | Audit all skill runners; use `.copy()` explicitly before mutating slices | Codex (BE) |
| 5 | **boto3 >=1.36 breaks Cloudflare R2 checksums** | Uploads silently fail or error | Set `request_checksum_calculation='when_required'` (and `response_checksum_validation='when_supported'`) on the boto3 client `Config`. **APPLIED (B3, 2026-06-12)** in `R2ResultStore` (`app/backend/storage/results.py`) — dormant until R2 creds are set. | Codex (BE) |
| 6 | **AGPL / restrictive-license dep risk** (MSigDB gene-set **data**; re-check `decoupler`). _(Corrected 2026-06-16: **gseapy removed — it is BSD-3, not AGPL**; the earlier entry conflated gseapy=code with MSigDB=data.)_ | SaaS gap covers GPL but AGPL requires source disclosure for network-served apps; MSigDB's **data** license adds CC-BY + per-set restrictions (incl. a no-Docker clause) | **DEFERRED per owner** (build-for-self now) but FLAGGED for the **pre-launch SCA gate**: run `pip-audit`/`safety`, quarantine any true AGPL, prefer Reactome/GO over MSigDB **data**. `gseapy` (BSD-3) + `blitzgsea` (Apache-2.0) are **clean GSEA engines** over our from-GO library. Re-check `decoupler`'s license at the gate. Do not ship MSigDB-derived sets to external users until cleared. | Codex (BE) / pre-launch |
| 7 | **pyDESeq2 != DESeq2 bit-for-bit** | Gene-set overlap is very high but not numerically identical to R DESeq2 | Golden-image tests catch divergence; use R-in-a-box (limma) for small-n / microarray designs | Codex (BE) |
| 8 | **Next 16 proxy buffers request bodies at 10MB** (rewrites/`/api/*` → :8000) | Real `.h5ad` uploads (pbmc3k demo is ~21MB) are truncated → broken multipart → ECONNRESET → 500. Found closing the P0 gate. | **Dev/P0 fix applied:** `experimental.proxyClientMaxBodySize: "512mb"` in `next.config.ts`. But Next buffers the body in memory per request, so this won't scale to large datasets. **Production must move large uploads off the in-memory proxy** — direct-to-backend (CORS) or chunked/presigned upload. | Claude (FE) |
| 9 | **OmicVerse can't share the backend venv** + **GPL-3.0 / 50-tool SCA surface** | OmicVerse (the prime Skill-Foundry source) pins `pandas<3.0, scipy<1.12, anndata<0.12`; Selom deliberately runs `pandas>=3.0` + `anndata>=0.12`, so adding `omicverse` makes `uv` **unsolvable** (breaks even core `uv run`). Separately, it's GPL-3.0 and pulls 50+ tools transitively. | **Do NOT add `omicverse` to a shared extra** (left out of `[omics]`). Integrate it **out-of-process in an isolated env/container** (the §6.5C/E per-skill-env model) and call it over a thin RPC/MCP boundary; do not downgrade the main stack. GPL is fine server-side (DECISIONS #7), but SCA-gate the 50 transitive deps before launch. **`gseapy` was DROPPED from `[omics]` (B3, 2026-06-12)** — enrichment uses an in-house ORA (DECISIONS #9), so it was simply unused at the time. _(Corrected 2026-06-16: gseapy is **BSD-3**, not "AGPL surface" — it is now re-allowed as a GSEA engine, see DECISIONS #9.)_ | Codex (BE) / pre-launch |

## Notes

- Risk #6 is the one explicit **deferred** item: the owner has chosen build-for-self
  first, so AGPL / restrictive-license exposure does not block development — but it is a
  hard gate before any external user. (Scope corrected 2026-06-16: this is now the
  **MSigDB gene-set data** license + a `decoupler` re-check — **not** gseapy, which is
  BSD-3.) Keep it visible; do not let "deferred" become "forgotten".
- Cross-references: `DECISIONS.md` (deferred-gates policy), Selom Build Dossier §2.
