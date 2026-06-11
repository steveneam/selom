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

**B1 · Close the P0 gate — real hello-UMAP end-to-end** 🔴 `[BE-led, FE conforms]` `⟵P0-exit+P3-gate`
Install deps; wire `run_scanpy.py` behind the run endpoint; resolve the one-shot-vs-upload contract; `demo.h5ad` → real Scanpy UMAP → editable Plotly spec → client-side recolour, no recompute. FE: browser-verify the shell so "done" is truly done.
*Forj:* bones (skill-contract round-trip) · meat (umap). *Forces:* confirm the canonical P0 contract (open Codex ask).

**B2 · Steven's Stage-1 skills (his real figure types)** 🟡 `[BE-led, FE registry exists]` `⟵P1 (reprioritized)`
scRNA UMAP/cluster/violin/DEG (retinal atlas) + bulk DEG/volcano/heatmap + **GSEA** (RPGRIP1 organoid) — each a pure-Python skill emitting an editable spec + **golden-image snapshot test**.
*Forj:* meat (the skills) · bones (golden-image harness). *Forces:* pick the demo datasets (the `[GAP]`).

**B3 · Skills as a service (jobs + storage)** 🟡 `[BE-led, FE swaps mocks→live]` `⟵P2`
Generalize the run endpoint to all Verified skills; async **arq+Redis** for heavy jobs; R2 result store + presigned URLs; SSE/poll status; FE Store becomes **registry-driven from real `GET /skills`**.
*Forj:* **bones** (job/queue substrate = EAMOS spine). *Forces:* DECISIONS.md **#6** (arq) goes load-bearing — Codex confirms.

**B4 · The publish-confidence layer** 🔴 *(core decision, made tangible)* `[FE+BE]` `⟵P5 + P3-export, RISEN into Stage 1`
Per-figure **reproducibility bundle** (skill id+version+params+data-hash+env) · **statistical guardrails** (batch-effect / normalisation / multiple-testing / low-cell) · **auto methods-text** · **journal-preset export** (Kaleido PNG/SVG/PDF).
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
Paper/repo → reproducible custom skill; Firecracker/gVisor sandbox; grow runnable coverage toward the full 500+ (manual Foundry now → LLM-assisted = the moat).
*Forj:* meat now / BONES-pattern later. *Forces:* DECISIONS.md **#8** (trade-secret IP).

---

## What changed vs the raw P0–P8 ledger (the reorder rationale)

- **P5 (guardrails/methods-text) rose into Stage 1 (B4)** — forced by the publish-confidence core decision.
- **P4 billing + P6 launch dropped to Stage 3 (B7/B8)** — single-user dogfood doesn't need them.
- **A Stage-2 pair (B5/B6) was inserted** — not new scope; it's the existing skill-contract + AI-gateway *hardened as shared substrate* + the documented EAMOS bridge.
- **The command-center FE folded into B0 as done/ahead.**

## Lane reality

Two agents, disjoint lanes (`agent_handoff/README.md`): **Claude = FE** (`app/frontend`), **Codex = BE** (`app/backend`). Critical-path buckets **B1–B3, B7 are BE-led (Codex)** — filed via `CURRENT.md → Cross-Agent Requests`; FE conforms. FE-owned: B0 (done — needs browser-verify), the **FE halves of B3/B4** (registry-driven Store, reproducibility-bundle/guardrail/export UI), B5 copilot, B9 foundry UI.

## Active bucket

**B1 — close the P0 gate.** Per-bucket plan presented for owner review (2026-06-11); not yet started.

---

*Links: `agent_handoff/DECISIONS.md` · `agent_handoff/RISKS.md` · `ROADMAP.md` · `docs/command-center/design.md` · `plans/v2-frontend.md` · `plans/v2-backend.md`. Vault (read-only) source: `Selom/Wiki/product/selom-build-kickoff.md` (P0–P8) + `Selom/Wiki/syntheses/v1-build-plan-and-roadmap.md`.*
