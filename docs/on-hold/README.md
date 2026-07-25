# On-hold — the parking lot (P6)

> **This folder is a registry, not a graveyard.** Items here are **parked, not
> deleted** — captured with a pointer so nothing is lost, and **not worked** until
> the shared engine spine (`docs/pillars/plan.md`, P1–P5) is solid. Existing spec
> folders for these items are **left in place**; this README is the canonical list
> of what is deliberately on hold.

**Rule for leaving the lot:** an item only becomes active again by an explicit owner
decision that names the pillar (P1–P5) it rejoins. Until then, if a task serves none
of P1–P5, it belongs here — write the pointer and move on.

> **THE ONE HOME (2026-07-25, plan `OH-15`).** There used to be two registers with overlapping
> rows: this parking lot and `agent_handoff/on-hold/README.md` ("Docker/WSL-gated work"). They are
> now **folded into this file**, per the Ratchet's one-durable-home rule; the other file is a
> pointer stub.
>
> Its framing was also **stale**, and so were several rows here (plan `OH-13`): the owner cleared
> Docker on this Linux box on 2026-07-23 (Engine v29.6 + Compose), and a Redis is already running
> on `:6380`. So "needs Docker/WSL" was no longer true for **any** row. Where an item is still
> correctly parked, the row below now states the **real** reason — usually off-thesis breadth or an
> open product question, which was the honest reason all along, wearing an infra excuse. A register
> that misstates its own reasons stops meaning anything.

---

## Graduated — left the lot (kept for the audit trail)

| Item | Outcome |
|---|---|
| **arq + Redis job-status store** | **UNPARKED 2026-07-25**, owner-decided at the Phase 0 founder gate. A Redis-backed `JobStore` so cross-process (arq) job *status* and errors are visible, not just success — a real gap in `jobs/worker.py` today. This **executes locked decision #6** (arq + Redis, ratified 2026-06-11), which was never built because it was Docker-gated on Windows; Redis now runs on `:6380`. Rejoins **P1/P3 (platform)**. Queued for the sprint **after** the approved 3-lane partition — it is deliberately in no lane. |
| **Journal style packs** | **UNPARKED 2026-07-25**, owner-decided at the Phase 0 founder gate. Installable export style packs; refactor `skills/theme.py` into a named style registry. The cheapest item on the board — `docs/journal-styles/spec.md` is **already written**. Rejoins **P4 (output)**. Queued for the sprint after the 3-lane partition. |
| **Kaleido journal export** | **DONE 2026-06-15 — and its gate had been wrong.** Kaleido v1 drives the already-installed Chrome over CDP (pure-Python, no container at runtime); `POST /figures/export` verified live in all three formats. Only the Linux *deploy image* needs a bundled browser, which is the deploy-image row below, not this feature. |
| **Multi-sample scRNA assemble → one AnnData + obs from filenames** | **SHIPPED 2026-07-23 in `11a115f`** as `POST /data/assemble-scrna`. This row was stale — the same error `OH-14` corrected in memory. **Shipped ≠ reachable:** it has no FE surface (plan `L2-05`), it zero-fills genes absent from a sample's reference (`L1-03`), and it re-declares the 10x detector instead of consulting `engine.ingest` (`L1-04`). [[selom-shipped-not-reachable]] |

---

## Parked

| Item | Why parked (real reason) | Recover from | Rejoins pillar |
|---|---|---|---|
| **External skill audit — bioSkills / ClawBio / OmicVerse universe** | The whole "COLLABORATE, don't compete on breadth" / partner-host / OVERLAP / PLATFORM strategy from the s42 audit. Off-thesis until the spine is solid. OmicVerse is GPL-3.0 (in-process SaaS blocker → arms-length only). **Carve-out:** the audit's *native* picks are NOT parked — `proteomics_de` MNAR (done s42), is-my-data-clean (P1c), metabolomics_de (P4 on-demand). | `docs/records/skill-audit/external-skill-audit.md`, `graphify-out/scratch/skill-audit-inventory.md`, [[selom-clawbio-bioskills-shortlist]] | P4 (host, post-spine) |
| **OmicVerse isolated worker** | **Reason restated 2026-07-25.** The *isolation* need is real and unchanged — OmicVerse pins `pandas<3` against our pandas-3 stack (RISKS #9), so it can only run out-of-process. But the blocker is **licence + thesis, not Docker**: GPL-3.0 makes in-process use a SaaS blocker (arms-length only, decision #7), and ~1000 `ov.*` functions is exactly the breadth decision #10 says not to chase. Docker becoming available changes nothing here. | RISKS #9, [[selom-clawbio-bioskills-shortlist]] | B9 / P4 (post-spine, arms-length) |
| **Deploy image (B8)** | **Reason restated 2026-07-25.** No longer infra-gated. It now **overlaps the public-Selom-backend-on-syd2 work** (backend Dockerfile + GHCR image-CI + the AGPL SCA scan as a hard gate) and should be tracked **there, once** — not in two places. | `docs/build-charter.md` B8, `agent_handoff/FROM-SWORDFISH.md` | B8 launch (fold into the syd2 lane) |
| **Community skill sandbox** | **Reason restated 2026-07-25.** Container sandbox + mamba images + network policy. Docker is cleared; this stays parked purely because it is **v2 scope** — the Skill Foundry community tier does not exist yet. | `docs/command-center/design.md` §6.5 E | B9 (v2) |
| **Supabase persistence** | Pre-launch platform infra; build-now-gate-later. *(Row split 2026-07-25: the old "Supabase / arq+Redis / Kaleido infra" row bundled three unrelated things — Kaleido shipped, arq+Redis is unparked, only Supabase is still parked.)* | `ROADMAP.md` P0–P3 | — (pre-launch) |
| **BAM ingest** | **Reason restated 2026-07-25.** The infra gate is cleared, and decision #10's refinement already accepts BAM as an input type. It stays parked on a **product** question, not an infra one: no current product goal needs BAM→count-matrix, and it is GB-scale work (direct/chunked upload + an async job). Unpark when a real user file forces it. Test set: 20 GRCh38 iRPE-control BAMs (~38 GB) on the CMRI share. | [[selom-bam-ingest]], DECISIONS #10 refinement | P1 (ingest, on demand) |
| **Accession AUTO-fetch + ingest (dogfood Slice 5 Phase B2)** | **Reason restated 2026-07-25 — this was never really infra-gated.** The owner decided at s53 to ship the *manual* handoff instead (per-accession link + download instructions → user fetches → drops into the per-panel picker), and that shipped. Auto-fetch is a deliberate **product** decision, not blocked work. Revisit only if the manual loop proves too slow. | `docs/records/reproduction-dogfood/spec.md` Slice 5 Phase B2, [[selom-accession-ingest]] | P1/P5 (only if the manual loop hurts) |
| **ClawBio HOST / collaboration slice** | **Reason restated 2026-07-25.** Partner-hosting needs worker infra, which Docker now covers — so the real reasons are that it is **off-thesis until the spine is solid** and depends on a partner relationship that does not exist yet. | [[selom-clawbio-bioskills-shortlist]] | P4 (post-spine) |
| **Ask-Selom AI chat** | Pillar-3 guided-trust UX; deferred, spec-before-build. | [[selom-ask-selom-chat]] | P3/UX (later) |
| **Reference-atlas reproductions** | Pre-launch hardening, not structure. | [[selom-hani-figure-reproduction]] (Cowan/Lu/Lukowski/Orozco/Yan) | P5 (regression set) |
| **External-tool builds (ARCHS4 / phylogenomics / eggNOG)** | Off-thesis breadth; ARCHS4 data non-commercial, the others AGPL. | `docs/records/external-tools-study.md`, [[selom-external-tools-study]] | — (mostly skip) |
| **Pipeline flow animation** | Landing/hero polish; in-app uses a static line. | git `cb813cf`, [[selom-pipeline-flow-animation]] | — (marketing) |
| **"Digitize this panel" bridge** | Standalone `/extract` ships; in-paper digitize deferred behind lit-synth Phase B. | [[selom-extract-reproduction-bridge]] | P5 (never feeds score) |
| **Gene-set builder — messy multi-header lists** | Phase A shipped clean lists; messy parsing deferred. | `docs/records/gene-set-builder-design.md`, [[selom-gene-set-builder]] | P4 (later) |
| **Command-center C/B platform** | Big platform build (Skill Store install backend, real intake). | `ROADMAP.md` C/B phases, [[selom-command-center-architecture]] | P3/P4 (after spine) |
| **OSCA Gap E — reference annotation** | Last OSCA gap; owner deferred E1 vs E2. | [[osca-source-sc-workflow]] | P4 (a skill) |
| **pdf.js region-capture (Recover-data 4th stage)** | Umbrella remainder; only pull in if reproduction needs it. | `docs/workspace-library/umbrella-shell.md` | P5 (if needed) |
| **metabolomics_de skill** | New pillar, pure whitespace — *but* only build when a product needs it; otherwise breadth. | [[selom-clawbio-bioskills-shortlist]] (audit #2) | P4 (on demand) |
| **OneDrive / Microsoft cloud provider** | Owner on hold pending a machine that logs into Azure cleanly; Google Drive + Dropbox are live. **Lane 2 must keep the provider list flag-driven** so OneDrive drops in with no code change — the frozen `GET /cloud/providers` contract already guarantees this. | `docs/cloud-providers-contract/spec.md` | P1 (intake) |
| **WS6 AWS deploy** | Owner chose "this box first, AWS later". | [[selom-aws-materialization-decision]] | — (later) |

> Note: `[[name]]` links resolve to the auto-memory index at
> `/home/deploy/.claude/projects/-home-deploy-work-selom/memory/MEMORY.md`
> (one line per memory). _Path corrected 2026-07-25 — it had still pointed at the
> pre-migration Windows location._
