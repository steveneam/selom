# On-hold — the parking lot (P6)

> **This folder is a registry, not a graveyard.** Items here are **parked, not
> deleted** — captured with a pointer so nothing is lost, and **not worked** until
> the shared engine spine (`docs/pillars/plan.md`, P1–P5) is solid. Existing spec
> folders for these items are **left in place**; this README is the canonical list
> of what is deliberately on hold.

**Rule for leaving the lot:** an item only becomes active again by an explicit owner
decision that names the pillar (P1–P5) it rejoins. Until then, if a task serves none
of P1–P5, it belongs here — write the pointer and move on.

| Item | Why parked | Recover from | Rejoins pillar |
|---|---|---|---|
| **External skill audit — bioSkills / ClawBio / OmicVerse universe** | The whole "COLLABORATE, don't compete on breadth" / partner-host / OVERLAP / PLATFORM strategy from the s42 audit. Off-thesis until the spine is solid. OmicVerse is GPL-3.0 (in-process SaaS blocker → arms-length only). **Carve-out:** the audit's *native* picks are NOT parked — `proteomics_de` MNAR (done s42), is-my-data-clean (P1c), metabolomics_de (P4 on-demand). | `docs/records/skill-audit/external-skill-audit.md`, `graphify-out/scratch/skill-audit-inventory.md`, [[selom-clawbio-bioskills-shortlist]] | P4 (host, post-spine) |
| **Journal style packs** | Export-polish feature, not engine. | `docs/journal-styles/`, [[selom-journal-styles-feature]] | P4 (output) |
| **BAM ingest** | Needs large-file/async infra (ASK before Redis/Docker). | [[selom-bam-ingest]] | P1 (ingest) |
| **Ask-Selom AI chat** | Pillar-3 guided-trust UX; deferred, spec-before-build. | [[selom-ask-selom-chat]] | P3/UX (later) |
| **Reference-atlas reproductions** | Pre-launch hardening, not structure. | [[selom-hani-figure-reproduction]] (Cowan/Lu/Lukowski/Orozco/Yan) | P5 (regression set) |
| **External-tool builds (ARCHS4 / phylogenomics / eggNOG)** | Off-thesis breadth; ARCHS4 data non-commercial, the others AGPL. | `docs/records/external-tools-study.md`, [[selom-external-tools-study]] | — (mostly skip) |
| **ClawBio HOST / collaboration slice** | Partner-hosting; needs worker infra (ASK before Docker). | [[selom-clawbio-bioskills-shortlist]] | P4 (later, post-spine) |
| **Pipeline flow animation** | Landing/hero polish; in-app uses a static line. | git `cb813cf`, [[selom-pipeline-flow-animation]] | — (marketing) |
| **"Digitize this panel" bridge** | Standalone `/extract` ships; in-paper digitize deferred behind lit-synth Phase B. | [[selom-extract-reproduction-bridge]] | P5 (never feeds score) |
| **Gene-set builder — messy multi-header lists** | Phase A shipped clean lists; messy parsing deferred. | `docs/records/gene-set-builder-design.md`, [[selom-gene-set-builder]] | P4 (later) |
| **Command-center C/B platform** | Big platform build (Skill Store install backend, real intake). | `ROADMAP.md` C/B phases, [[selom-command-center-architecture]] | P3/P4 (after spine) |
| **Supabase / arq+Redis / Kaleido infra** | P1–P3 platform infra; build-now-gate-later; ASK before Docker/WSL. | `ROADMAP.md` P0–P3 | — (pre-launch) |
| **OSCA Gap E — reference annotation** | Last OSCA gap; owner deferred E1 vs E2. | [[osca-source-sc-workflow]] | P4 (a skill) |
| **pdf.js region-capture (Recover-data 4th stage)** | Umbrella remainder; only pull in if reproduction needs it. | `docs/workspace-library/umbrella-shell.md` | P5 (if needed) |
| **metabolomics_de skill** | New pillar, pure whitespace — *but* only build when a product needs it; otherwise breadth. | [[selom-clawbio-bioskills-shortlist]] (audit #2) | P4 (on demand) |
| **Accession AUTO-fetch + ingest (dogfood Slice 5 Phase B2)** | The network/large-file/async auto-download of deposited data (GEO-suppl heterogeneity: tar / mtx-triplet / per-sample → `engine.ingest`). **Owner decision s53:** put the infra on hold — instead ship the *manual* handoff (Slice 5B: a per-accession link + download instructions → user fetches → drops into the per-panel picker). Revisit auto-fetch only if the manual loop proves too slow. | `docs/records/reproduction-dogfood/spec.md` Slice 5 Phase B2, [[selom-accession-ingest]], [[ask-before-docker-wsl]] | P1/P5 (later, infra) |
| **Multi-sample scRNA assemble → one AnnData + obs from per-file provenance** | **Owner-flagged 2026-07-02 (RESTRUCTURE-04):** a real GEO scRNA deposit (e.g. Hani GSE201356) is per-sample 10x triplets with **no per-cell obs design** — the design (genotype/line, sample id) lives in the *filenames*. A skill/param that reads a set of per-sample matrices, concatenates them, and **materializes the filename-encoded design into obs** (`line`/`condition`, `sample_id`) would give the intake design path a real object to read — exactly what a bench analyst does by hand. Generalizes the shipped **`/data/combine`** (which already merges single-condition **ERG** files into one multi-condition table); the scRNA/10x-triplet version is the natural sibling. Needs multi-file upload UX + a filename→obs mapping step + possibly async for large concats. Prototype exists (this session's scratchpad `build_hani_obs.py`). | this file, `routers/data.py:/data/combine`, [[selom-data-substrate-decision]], [[selom-accession-ingest]] | P1 (ingest) |

> Note: `[[name]]` links resolve to the auto-memory under
> `C:\Users\seamegdool\.claude\projects\D--selom\memory\`. The `MEMORY.md` index there
> holds the one-line pointer for each.
