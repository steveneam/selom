# Selom — DECISIONS (Locked)

> Binding decisions for the Selom build. Agents treat these as authoritative.
> Supersede by append (with a new stamp), never silently overwrite. Deep ADRs
> live in the research vault; this file is the build-side quick reference.

_Last updated: 2026-06-11 23:40 +10:00 — added #9 (GSEA gene-set source = Reactome/GO) at B2 sign-off (Claude, owner-approved)._

| # | Decision | Rationale | Source |
|---|---|---|---|
| 1 | **Stack = Python (FastAPI) backend + Next.js frontend.** R is **validation-only** — never on the hot path; used to produce golden reference outputs the Python skills are tested against. | Single production language (Python) for skill runners; R kept as a correctness oracle only. | ADR 0002 |
| 2 | **The build repo lives at `D:/selom`** — separate from the research vault. | Code stays in `D:/selom`; the vault holds research + operational mirrors only. Clean separation of build vs. knowledge. | Project layout |
| 3 | **Commercial / licensing gates are intentionally DEFERRED** for build-for-self. | Owner directive: build the product first, apply commercial/licensing gates before launch. Gates never block in-lane build work. See `RISKS.md` #6 (AGPL) for the one item that must clear the pre-launch gate. | Owner directive |
| 4 | **Git staging is explicit** — never `git add -A` after the initial scaffold commit. | Disjoint two-agent lanes mean blanket staging risks committing the other agent's in-flight work. Stage named paths only. | Coordination protocol |
| 5 | **No-code figure editor = a custom panel, NOT `react-chart-editor`.** `react-plotly.js` (render) + shadcn/ui controls → RFC-6902 JSON-Patch; the same patch protocol the LLM copilot emits against the editable Plotly spec. | `react-chart-editor` 0.46.1 is abandoned (no React 18/19); the editable-spec + shared-patch loop is the product wedge ("AI navigator, not analyst"). **Already built** in `app/frontend` — this ratification locks existing truth. Lane: Claude (FE). | ADR 0002 · build-setup-and-toolchain §7 · `RISKS.md` #1 |
| 6 | **Async job queue = arq + Redis** (not Dramatiq). | arq is asyncio-native and matches the FastAPI async stack + every vault manifest/schematic; Dramatiq (heavier, broker-flexible) was considered and is not needed. **Backend-lane (Codex-owned)** — locked to the vault's recommended default under the owner's "ratify all 5" directive; Codex confirms, or supersede-by-appends if a Dramatiq-specific need surfaces. See `CURRENT.md → Cross-Agent Requests`. | build-ledger §3 · selom-build-kickoff §2 |
| 7 | **Distribution = web-first SaaS for v1.** No consumer desktop (Electron/Tauri); on-prem / BYO-cloud is reserved as a later enterprise tier (pharma data-residency). | The only model where the GPL SaaS-gap holds (server-side use ≠ distribution → no copyleft re-trigger), compute is metered, and there's nothing to pirate; bundling copyleft into a desktop app would re-trigger GPL. | distribution-web-vs-desktop · ADR 0002 |
| 8 | **IP strategy = trade-secret + copyright, NOT patents.** | The Extract-Skills method is best kept secret (patents force disclosure and are hard to enforce on a method); the durable moat is curation / UX / verified-reproducibility — protected by copyright (compilation) + trade-secret, with an open-core boundary for public parts. | commercialisation-ip-trademark §B |
| 9 | **GSEA / pathway-enrichment gene-set source = Reactome / GO** (license-clean), NOT gseapy + MSigDB. | MSigDB and gseapy carry AGPL / restrictive-license constraints (`RISKS.md` #6) that would have to clear the pre-launch SCA gate; Reactome + GO are openly licensed, so the `selom.enrichment` skill stays launch-safe with no copyleft cleanup. Owner-approved at B2 sign-off. Lane: Codex (BE). | Owner directive · `RISKS.md` #6 · build-charter B2/B4 |

## Notes

- Decision #1 (Python + Next.js, R validation-only) defines the lane split:
  Codex owns Python `app/backend`; Claude owns Next.js `app/frontend`.
- Decision #3 is the policy behind `RISKS.md` #6: deferred does not mean
  cancelled — the AGPL / commercial gate must be cleared before any external user.
- Decision #4 binds both agents: after the scaffold commit, every commit stages
  explicit paths so the disjoint lanes never cross-contaminate.
- **Ratification (2026-06-11):** the kickoff listed **5** pending vault `[DECISION]`s to
  formalise. Reconciled against this register: *repo = `D:/selom`* was already locked as
  **#2**, so only four were newly added — **#5** (custom figure editor), **#6** (arq vs
  Dramatiq), **#7** (web-first), **#8** (trade-secret IP). All five are now ratified.
- **#6 (arq) is backend-lane:** Codex owns the implementation. It is recorded here per the
  owner's "ratify all 5" directive using the vault's recommended default; Codex confirms or
  supersedes-by-append. Flagged in `CURRENT.md → Cross-Agent Requests`.
- **Vault mirror TODO (wiki agent):** the deep ADRs for #5–#8 (vault numbering `0004`–`0007`)
  should be filed into the research vault's `Selom/Wiki/decisions/` by the wiki agent — this
  build session is **read-only** in the vault, so it cannot write them. This file is the
  authoritative build-side reference until then.
