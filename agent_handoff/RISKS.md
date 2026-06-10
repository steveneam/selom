# Selom — RISKS (Build Landmines)

> Seeded from the Selom Build Dossier §2 (Findings & landmines). These are the
> known traps that will silently break the P0 build if ignored. Each carries the
> fix. Add new risks as they surface; do not delete — supersede with a resolution
> note.

_Last updated: 2026-06-10 20:46 +10:00_

| # | Risk | Impact | Fix / mitigation | Owner |
|---|---|---|---|---|
| 1 | **`react-chart-editor` is dead** (last publish Nov 2023, no React 18/19) | The assumed no-code figure-property-panel engine is unusable | Build a custom panel: `react-plotly.js` (render) + shadcn/ui (controls) -> RFC-6902 JSON-Patch. Same patch protocol as the LLM copilot. | Claude (FE) |
| 2 | **Kaleido v1 needs system Chromium in Docker** — v1 no longer bundles Chromium | Server-side PNG/SVG/PDF export fails | In the Docker image: `apt-get install -y chromium` + `ENV KALEIDO_CHROME_PATH=/usr/bin/chromium`; pin kaleido>=1.3 + plotly>=6.1.1 from day 1 | Codex (BE) |
| 3 | **`react-plotly.js` is stale** (React <=18 peer-deps) | `npm install` fails without a flag | Always install with `--legacy-peer-deps`; monitor for a React 19 PR | Claude (FE) |
| 4 | **pandas 3.0 Copy-on-Write is default** | Chained assignment raises `ChainedAssignmentError` in skill code | Audit all skill runners; use `.copy()` explicitly before mutating slices | Codex (BE) |
| 5 | **boto3 >=1.36 breaks Cloudflare R2 checksums** | Uploads silently fail or error | Set `request_checksum_calculation='when_required'` (and `response_checksum_validation='when_supported'`) on the boto3 client `Config` | Codex (BE) |
| 6 | **AGPL transitive-dep risk** (gseapy / MSigDB, decoupler) | SaaS gap covers GPL but AGPL requires source disclosure for network-served apps | **DEFERRED per owner** (build-for-self now) but FLAGGED for the **pre-launch SCA gate**: run `pip-audit`/`safety`, quarantine AGPL, prefer Reactome/GO over MSigDB. Do not ship to external users until cleared. | Codex (BE) / pre-launch |
| 7 | **pyDESeq2 != DESeq2 bit-for-bit** | Gene-set overlap is very high but not numerically identical to R DESeq2 | Golden-image tests catch divergence; use R-in-a-box (limma) for small-n / microarray designs | Codex (BE) |

## Notes

- Risk #6 is the one explicit **deferred** item: the owner has chosen build-for-self
  first, so AGPL exposure does not block development — but it is a hard gate before
  any external user. Keep it visible; do not let "deferred" become "forgotten".
- Cross-references: `DECISIONS.md` (deferred-gates policy), Selom Build Dossier §2.
