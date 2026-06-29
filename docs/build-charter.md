# Selom — Build Charter (B0–B9)

> **What this is.** The approved, dependency-ordered build plan for Selom, reordering the
> research vault's **P0–P8 ledger** to honour the **staged goal** and the **publish-confidence
> core decision**, with already-built repo work folded in as *done*. It does **not** invent new
> scope — every bucket maps back to a ledger phase (`⟵P#`).
>
> **Status:** APPROVED by owner 2026-06-11. **Source of truth for sequencing.** Per-bucket plans
> are presented + reviewed before each bucket is built (no bucket starts without owner sign-off).
> **Authoritative decisions:** `agent_handoff/DECISIONS.md`. **Live state:** `agent_handoff/CURRENT.md`.
> **Keystone design:** `docs/command-center/design.md`. **Phased detail:** `ROADMAP.md`.
>
> **Vault mirror (wiki-agent TODO):** mirror this charter into `Selom/Wiki/operational/` and file the
> deep ADRs `0004`–`0007` for `DECISIONS.md` #5–#8 into `Selom/Wiki/decisions/`. This build session is
> read-only in the vault and cannot write them.
>
> _Filed: 2026-06-11 22:02 +10:00 · Claude (FE lane), owner-approved._

---

## Staged goal (Steven, 2026-06-11)

The goal is **sequenced, not single** — earliest buckets serve Stage 1:

1. **Personal research tool first** — dogfood Steven's own omics figures (RPGRIP1 organoid DEG/GSEA + retinal-atlas scRNA UMAP/clustering/violin/DEG). Earliest skills = the figure types Steven actually needs on his real data.
2. **Then an engine for EAMOS** — share the skill-contract + AI-gateway + the **PS3/BS3 functional-evidence figure bridge**; the shared substrate is built EAMOS-reusable.
3. **Then a standalone revenue SaaS** — academic/biotech freemium + per-seat + metered credits; the broader skill library + Extract-Skills v2 monetised here.

**Throughout:** feed **bones** (transplantable → Forj) + **meat** (Selom-specific) to Forj after each bucket.

## Core decision (pinned 2026-06-11)

**Publish-confidence:** *"Is THIS the right, trustworthy, reproducible figure to put in my paper?"*
The product exists to let the user answer **yes** with justified confidence. This is why the ledger's
*trust + reproducibility + methods-text + journal-export* work (old "P5") is **promoted into the
Stage-1 critical path** (Bucket B4): a figure isn't "done" until it's paper-ready. Guided intake /
method-navigation is in **service of** publish-confidence, not the end itself.

---

## Reconciled repo baseline — what's already built (do NOT rebuild)

- **Backend skeleton** ✅ — FastAPI (`GET /skills/{id}`, `POST /skills/{id}/run`, `/health`) + `SkillSpec` contract loader + `umap_scrna` (`skill.json` + offline **stub** `run.py` + real `run_scanpy.py`, *unwired*) + `[omics]` extra + `test_contract.py`. **Not installed/wired.**
- **Frontend** ✅ — Next 16 / React 19 / TS / Tailwind 4 shell + **editable-Plotly figure editor** (property panel + RFC-6902 JSON-Patch) + **MSW mock harness** (renders the P0 path with `:8000` down) + **command-center shell** (Home, Skill Store browse/install ~32-of-600 with Verified/Community tiers + coverage meter, project Overview/Data/Workbench/Figure, guided intake → `IntakeProposal`) + localStorage `ProjectStore` (Supabase-schema-aligned). `tsc` + `next build` clean.
- **Reconciliation insight:** the **FE raced ahead** of the ledger (editable-spec editor + command-center = ledger-P3-and-beyond, built mock-first) while the **BE is still at P0 skeleton**. The real critical path is *wiring the existing BE to the already-built FE*, not net-new UI.
- **Caveat:** FE "done" is build-clean but **not yet browser-verified** (last session's live click-through was blocked by a Chrome profile lock).

---

## The buckets

**Legend:** `⟵P#` = ledger phase · `[FE]`/`[BE]`/`[FE+BE]` lane (BE = Codex via handoff) · ✅ done · 🔴 now/critical · 🟡 next · ⚪ later. Forced decisions reference the now-ratified `DECISIONS.md` entries.

### Stage 1 — Personal research tool (dogfood; the publish-confidence loop)

**B0 · Scaffold & command-center shell** ✅ `[FE+BE]` `⟵P0(partial)+P3(FE ahead)`
Repo, GitHub push, BE skeleton, editable-spec editor, command-center shell — *done, folded in.*
*Forj:* **bones** (project-first IDE shell + editable-spec/JSON-Patch editor + skill-contract) · meat (catalog seed).
*Decisions realized here:* DECISIONS.md **#5** (custom editor) + **#2** (repo) — ratified.

**B1 · Close the P0 gate — real hello-UMAP end-to-end** ✅ `[BE-led, FE conforms]` `⟵P0-exit+P3-gate`
Done 2026-06-11 (Claude, acting both lanes). `uv sync --extra scrna` + `run_scanpy.py` wired behind the one-shot `POST /skills/umap_scrna/run`; `demo.h5ad` (pbmc3k) → real Scanpy UMAP → editable Plotly spec; browser-verified end-to-end (upload → run → editable figure renders, live :8000, MSW off). One-shot contract confirmed. Fixed Plotly-6 base64 typed-arrays + Next-16 proxy 10MB body cap (RISKS #8). Commits `6e37829`/`396ca66`.
*Forj:* bones (skill-contract round-trip) · meat (umap). *Forces:* canonical P0 contract = **one-shot** (resolved).

**B2 · Steven's Stage-1 skills (his real figure types)** ✅ *(DONE 2026-06-12, local — not yet pushed)* `[BE-led, FE registry exists]` `⟵P1 (reprioritized)`
Built all 6 backend runners (UMAP done in B1): **cluster · violin (new) · DEG (scRNA + bulk) · volcano · heatmap · GSEA/enrichment** — each `skills/<slug>/{skill.json, run.py (dep-free stub) + run_real.py}`, dispatched by `SELOM_SKILLS_ENGINE`, emitting an editable plain-array Plotly spec via the shared `skills/_plotly.jsonable`, with a **golden-image snapshot test** (`tests/test_skills_golden.py` + `tests/golden/`, `python -m pytest` = 14 passed; real engines smoke-verified). `main.py` run-endpoint generalized to any Verified skill. FE conformed with the one new `selom.violin` catalog entry. GSEA via in-house hypergeometric ORA over a bundled GO/Reactome sample (DECISIONS #9 — no gseapy/MSigDB). Commits `eded0db` (BE) / `d1b9533` (FE).
*Owner sign-off (2026-06-11):* (1) **all 6** approved; (2) **public proxy datasets now** (pbmc3k scRNA + a public bulk set + a sample ranked list), real retinal-atlas/RPGRIP1 data dropped in later for hardening/validation; (3) **GSEA = Reactome/GO** (license-clean) — see DECISIONS.md **#9**.
*Follow-ups (later):* full GO/Reactome GMT ingestion to replace the bundled sample; real-engine numerical golden tests vs an R oracle (RISKS #7); **OmicVerse as a second Verified engine + the primary Skill-Foundry source — run out-of-process in an isolated env** (`pandas<3` conflict, RISKS #9; see `docs/records/external-integrations.md`); sklearn cluster-quality guardrails landed (silhouette in `cluster`), heatmap hierarchical row-ordering next.
*Integration research (owner-directed 2026-06-12):* OmicVerse · scikit-learn (now core) · R4DS/Quarto+ggplot2 (B4 reference) · Hermes (pattern + catalog-count true-up 540/88→≈385/33). Full assessment: `docs/records/external-integrations.md`.
*Forj:* meat (the skills) · bones (golden-image harness + stub/real engine split). *Forces:* DECISIONS.md **#9** (GSEA source). Demo-data `[GAP]` resolved → public proxies.

**B3 · Skills as a service (jobs + storage)** ✅ *(core landed 2026-06-12, pushed)* `[BE-led, FE swaps mocks→live]` `⟵P2`
Done: live **`GET /skills`** registry (`skills/registry.py` + a `catalog` block on `skill.json`) → FE Store is **registry-driven** (`lib/catalog/registry.ts` merges live Verified over the seed's Community tail, seed fallback offline); **async jobs API** (`POST /skills/{id}/jobs` → `GET /jobs/{id}` poll / `/events` SSE / `/result`) with one `execute_job` shared by the inline executor and the arq worker. Default = **inline + local filesystem result store (zero infra)**; **arq+Redis** (DECISIONS #6) + **R2 presigned URLs** (boto3 + RISKS #5 fix) are **wired but dormant** behind `SELOM_QUEUE=arq` / `SELOM_R2_*` + the optional `[jobs]` extra. 🟡 *Remaining:* stand up Redis/R2 for real + a **Redis-backed JobStore** so arq cross-process job *status* (not just success) is visible (`jobs/worker.py` caveat).
*Forj:* **bones** (job/queue substrate = EAMOS spine). *Forces:* DECISIONS.md **#6** (arq) confirmed; goes fully load-bearing when the infra lands (B7/B8).

**B4 · The publish-confidence layer** 🟡 *(slices 1–2 DONE; slice-1 pushed, slice-2 committed 2026-06-13)* `[FE+BE]` `⟵P5 + P3-export, RISEN into Stage 1`
Per-figure **reproducibility bundle** (skill id+version+params+data-hash+env) · **statistical guardrails** (batch-effect / normalisation / multiple-testing / low-cell) · **auto methods-text** · **journal-preset export** (Kaleido PNG/SVG/PDF).
**Slice-1 ✅:** the **reproducibility bundle** (`app/backend/provenance.py` — skill+version, resolved+typed params, input SHA-256+size, environment snapshot) + **auto methods-text** (`app/backend/methods.py` — per-skill templates + canonical citations) ride on every `/run` + job result as `{figure, provenance, methods}`; FE shows them in a collapsed **"Publish confidence"** panel (`components/project/publish-confidence.tsx`). `pytest` 28 passed; FE `next build` clean; browser-verified. Commits BE `2ab7c43` + FE `84ae54e` (pushed 2026-06-13).
**Slice-2 ✅ (2026-06-13):** statistical guardrails — bundle-side `app/backend/guardrails.py` adds a `guardrails` list to every `/run` + job result (multiple-testing / FDR-threshold method checks + best-effort `.h5ad` data checks: low-cell, pre-normalized-input, uncorrected-batch; cluster-silhouette stays in the runner). FE shows them as a **"Quality checks"** section + a warn-count header chip in the panel. `pytest` 40 passed; `next build` clean; browser-verified. Commits BE `edd3615` + FE `56da2a6`. 🟡 *Remaining:* **journal-preset Kaleido export** only (needs Docker+Chromium — RISKS #2; lands with the deploy image; **ask owner before any Docker/WSL work**).
*Forj:* **bones** (reproducibility-bundle + methods-text + export) · meat (omics guardrails). *Forces:* DECISIONS.md **#7** (web-first; Kaleido needs server-side Chromium) + the **AGPL SCA hard gate** begins to bite (gseapy/MSigDB → prefer Reactome/GO).

> **Stage-1 exit = dogfood-complete:** Steven produces trustworthy, reproducible, paper-ready figures on his own data — single-user, no auth, no billing.

### Stage 2 — Engine for EAMOS (shared, EAMOS-reusable substrate)

**B5 · Harden the shared substrate** ⚪ `[BE-led, FE copilot]` `⟵skill-architecture + AI-gateway`
Factor the `SkillSpec` contract + the intake/copilot **AI-gateway** into a clean transplantable boundary EAMOS can adopt; enforce *LLM-proposes-never-auto-runs*.
*Forj:* **BONES** (the point — shared with EAMOS).

**B6 · PS3/BS3 functional-evidence figure bridge** ⚪ `[BE-led, FE export]` `⟵selom-eamos-integration`
Export functional-evidence figures (RPGRIP1-style DEG/GSEA evidence) in a form EAMOS's variant interpretation consumes (PS3/BS3).
*Forj:* meat (Selom↔EAMOS) · bones (export-contract shape). *Forces:* uses #7.

### Stage 3 — Standalone revenue SaaS (multi-tenant, billing, moat)

**B7 · Account & persistence layer** ⚪ `[BE-led, FE surfaces]` `⟵P4 + design B4`
Supabase Auth (OIDC) + tier RLS + the schema-aligned tables `ProjectStore` already mirrors + Stripe/MoR + metered credits + pre-run cost preview.
*Forj:* **BONES** (Supabase/Stripe/RLS = EAMOS spine). *Forces:* multi-tenant makes #7 fully load-bearing.

**B8 · Launch v1 (public)** ⚪ `[FE+BE+ops]` `⟵P6`
Deploy (Render CPU + Modal GPU + Vercel); freemium + academic tiers; broaden curated skills; **AGPL SCA scan clean (hard gate)**; research-use-only ToS.
*Forj:* bones (deploy pattern) · meat (tiers). *Forces:* #7 ratified; the licensing gate.

**B9 · Extract-Skills beta + Skill Foundry** ⚪ *(the v2 moat)* `[BE-led, FE foundry UI]` `⟵P7 + design north-star`
Paper/repo → reproducible custom skill; Firecracker/gVisor sandbox; grow runnable coverage toward the full 500+ (manual Foundry now → LLM-assisted = the moat). **OmicVerse (isolated worker) is the prime manual-Foundry source** — ~1000 `ov.*` functions map ≈1:1 onto SkillSpec runners (`docs/records/external-integrations.md`).
*Forj:* meat now / BONES-pattern later. *Forces:* DECISIONS.md **#8** (trade-secret IP).

---

## Competitor-driven skill priorities (OmicsBox teardown, 2026-06-12)

The OmicsBox (BioBam) teardown — `docs/records/competitors/omicsbox.md` — reverse-engineers the
incumbent no-code suite to the tool/format level and yields a prioritized last-mile skill
backlog (§7). It is a **prioritization lens on the existing skill scope, not a new bucket** —
every item lands inside **B2** (broaden), **B8** (broaden curated skills) or **B9** (Skill
Foundry). The binding strategic call is drafted as **DECISIONS.md #10** (pending owner
ratification — *not yet locked*).

**Strategic bet:** win the **analysis→editable-figure last mile** (Selom starts from the count
matrix / AnnData / feature table; `h5ad`-native is their Seurat weakness) and own the
**proteomics / metabolomics whitespace** (OmicsBox is NGS-only, zero mzML). **Do not** get drawn
upstream into alignment / assembly / variant-calling — heavy, commodity, compute-metered even for them.

| Pri | What | Maps to | Note |
|---|---|---|---|
| **P1** | broaden `deg` (no-rep + time-course) + `enrichment` (ORA); new `pathway` (KEGG/Reactome) + `go-graph` figure skills | broadens **B2** + 2 new Verified skills | nearest gap; `pathway`/`go-graph` need the **KEGG · Reactome · GO/QuickGO · STRING** APIs eamos lacks → **printing-press CLI candidates** |
| **P2** ✅ | single-cell depth — `markers` · `annotate` · `trajectory` (SHIPPED 2026-06-14; + `pca`/`composition`) | **B8 / B9** library growth | `h5ad`-native = their Seurat weakness; annotate validated 7/7 vs published RPGRIP1 labels |
| **P3** | `coexpression` (WGCNA) · `venn` · `pcoa` | **B8 / B9** | leapfrogs their 4.0 WGCNA |
| **P4** 🆕 | proteomics + metabolomics (mzML) | **B9** Foundry + new-modality ingest | the long-term moat — OmicsBox can't match |

**API reuse (don't rebuild):** eamos already ships VEP · UniProt · NCBI E-utilities · PubMed ·
LitVar2 · gnomAD as live tools — NCBI + PubMed feed **B4** auto-methods citations; UniProt feeds
the **P4** proteomics module. The genuine new-API gaps (→ printing-press CLIs) are the
pathway/enrichment ones above. Full tool→skill→porting-source mapping: `docs/records/competitors/omicsbox.md §7–§8`.

## What changed vs the raw P0–P8 ledger (the reorder rationale)

- **P5 (guardrails/methods-text) rose into Stage 1 (B4)** — forced by the publish-confidence core decision.
- **P4 billing + P6 launch dropped to Stage 3 (B7/B8)** — single-user dogfood doesn't need them.
- **A Stage-2 pair (B5/B6) was inserted** — not new scope; it's the existing skill-contract + AI-gateway *hardened as shared substrate* + the documented EAMOS bridge.
- **The command-center FE folded into B0 as done/ahead.**

## Lane reality

Two agents, disjoint lanes (`agent_handoff/README.md`): **Claude = FE** (`app/frontend`), **Codex = BE** (`app/backend`). Critical-path buckets **B1–B3, B7 are BE-led (Codex)** — filed via `CURRENT.md → Cross-Agent Requests`; FE conforms. FE-owned: B0 (done — needs browser-verify), the **FE halves of B3/B4** (registry-driven Store, reproducibility-bundle/guardrail/export UI), B5 copilot, B9 foundry UI.

## Active bucket

**B4 — slices 1–2 DONE (2026-06-13). Active.** B0–B3 done (B3 pushed @ `4216935`). **B4 so far:** per-figure
**reproducibility bundle** (`provenance.py`) + **auto methods-text** (`methods.py`) + **statistical guardrails** (`guardrails.py`
— multiple-testing/FDR checks + best-effort `.h5ad` data checks) on every `/run` + job result; the FE **"Publish confidence"**
panel surfaces all three (Methods · Reproducibility · Quality checks + a warn-count chip). `pytest` 40 passed; FE `next build`
clean; browser-verified (mock :3010). Slice-1 pushed; slice-2 commits BE `edd3615` + FE `56da2a6`. **Next (finish B4):**
**journal-preset Kaleido export** only (needs Docker+Chromium, RISKS #2 → lands with the deploy image; **ask owner before any
Docker/WSL work**). Then the integration backlog (OmicVerse isolated worker, arq Redis status store, R-oracle, full GMT,
catalog true-up). Owner steer: Selom is **desktop-only**; model = **Opus 4.8 (xhigh)**.

---

*Links: `agent_handoff/DECISIONS.md` · `agent_handoff/RISKS.md` · `ROADMAP.md` · `docs/command-center/design.md` · `plans/v2-frontend.md` · `plans/v2-backend.md`. Vault (read-only) source: `Selom/Wiki/product/selom-build-kickoff.md` (P0–P8) + `Selom/Wiki/syntheses/v1-build-plan-and-roadmap.md`.*
