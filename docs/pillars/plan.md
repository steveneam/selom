# Selom — Pillars Plan (the shared engine spine + its two products)

> **Status: APPROVED structure** (owner, 2026-06-21, session 43). This is the
> organizing document for the next phases. It supersedes the ad-hoc
> session-to-session sequencing the build drifted into across s25–s42 and
> reorients everything around **one shared engine**.
>
> ### ⚑ PILLAR STATUS — re-measured 2026-08-05
>
> **The spine (P1–P4) is effectively COMPLETE.** P1 all four slices · P2 in substance (L3 Tier A+B,
> 16 synthesizers, reader↔synthesize integrated, `proteomics_de` native) · P3 3a+3b · P4 all three.
> **What is genuinely left is small and named:** P2 **2d** (data-matching robustness) and P3 **3c**
> (honest "we're not sure → here are options").
>
> **P5 is the constraint, and it is NOT engineering.** 5a shipped; the ledger's reading-provenance
> gap closed 2026-08-05 (`docs/provenance-stamping/spec.md`). 5b/5c/5d are **data-availability
> bound** — dogfooding more papers needs more staged papers+data, not more code
> [[selom-live-reproduction-drive]].
>
> **Where the sessions have actually gone since ~2026-08-03 is NOT on this map**: a
> reachability/honesty thread (unreachable knobs, multi-table contract, prose↔param truthfulness,
> ledger provenance). Tracked in `agent_handoff/CURRENT.md` NEXT and the backlogs named in
> `docs/build-plan-2026-08/plan.md` §0. **Naming the pillar still applies** — most of that work
> serves **P4** (contract uniformity / honest output) and **P5** (score credibility).
>
> Keystone first move (owner-picked): the engine-structure spec — `docs/engine-spine/spec.md`.
> Parked sidetracks: `docs/on-hold/README.md` (cataloged, never deleted).
> **Active hardening tracker (2026-07-02 audit):** `docs/restructure/plan.md` — the
> Product-A-first architecture/process hardening slices (WS1–WS6) map onto these pillars
> and are the task-of-record for that initiative.
> Companions: `docs/reproduction-engine/live-reproduction-spec.md` (P5),
> `docs/records/table-synthesis/spec.md` (P2/L3), [[layered-deterministic-extraction]],
> [[selom-figure-repro-mission]], [[compound-capability-each-task]].

---

## 0. The diagnosis (why we re-planned)

The pieces of the engine **all exist** — but they were built *inside* the paper-reproduction
feature as private plumbing (`reproduction_drive.py`, `extract/readers.py`, `extract/golden.py`,
`extract/routing/`), never factored as a clean, product-agnostic **engine** that both products
call. Across s25–s42 the build accreted **breadth** (OSCA hardening, Melody/Harmony2, 4 paper
ledgers, external-tools studies, the skill audit) and **product surfaces** (workspace library,
umbrella shell, Skill Match FE, journal styles) faster than the **shared spine** got named and
consolidated.

The fix is structural, not more features: **lift the spine out into a named, reusable engine**,
then let both products consume it.

---

## 1. The shared engine (the spine)

```
  INGEST                JOIN / MATCH            ROUTE / GUIDE          ANALYZE
  (layered data    →    (tables: data↔     →   (which analysis    →   (skills →
   sources)             analysis, merge,        for this input)        figure + table)
                        synthesize)
                                                                          │
        OUTPUT          ◄──   [ GRADE ]    ◄──   READ-BACK   ◄────────────┘
   (editable figure         (reproduction      (layered tables:
    + table + methods)       only)              L1/L2 readers + L3 synth)
```

Your own words map straight onto it: **"layered data source"** = INGEST (P1);
**"table joining"** = JOIN/MATCH + READ-BACK + L3 synthesis (P2); **"data-driven
analysis"** = ANALYZE (P4).

### The two products that ride the spine

- **Product A — "my own data"** (the daily product; the s42 own-data steer). A
  non-bioinformatician drops *their* data → Selom **cleans + guides + analyzes** → the
  output they want. Uses the spine **without** grading. **Currently under-built** — the
  spine has only ever had one real consumer (reproduction), so it looks reproduction-shaped.
- **Product B — "reproduce a paper"** (the proving ground; [[selom-figure-repro-mission]]).
  Drop a paper + its data → route → drive → **grade** → two-axis Score. Uses the spine **+ grading**.

"Get the structure right first" = make the spine product-agnostic so Product A is a first-class
consumer, not an afterthought.

---

## 2. The pillars

**Engine spine = P1–P4 (shared). Reproduction = P5 (reuses P1–P4 + grading). Product A = P1–P4
with P3's guidance. Everything off-thesis = P6 parking lot.**

Each pillar lists **agile slices** sized to roughly one scoped commit / session.

### P1 — Layered Ingest & Clean  ·  "layered data source"
**Goal:** any input (h5ad / csv / xlsx-sheet / 10x-mtx / ShinyCell / mzML / paper-supplement) →
**one canonical, QC'd, honestly-flagged data object**. The shared entry for both products.
**Today:** scattered & paper-centric — `extract/ingest.py` (`PaperBundle`), per-dataset loaders,
`normalization_qc` (QC + doublets + adaptive-MAD). No single canonical data representation.
**Slices:**
- **1a** Spec + build the canonical `DataBundle` + an ingest **registry** (one loader per input type). *(→ `docs/engine-spine/spec.md`)* **DONE (s43).**
- **1b** Unify paper-supplement ingest and own-data ingest onto `DataBundle`. **DONE (s48):** the runner takes a `DataBundle` (`skills.contract.run_bundle`/`run_bundle_with_table` + `DataBundle.path`), and **both products now load through `engine.ingest` → bundle → run end-to-end** — reproduction's `_default_runner` and `POST /skills/{id}/run`. Byte-identical (E4). *(The cheap paper-side sheet inventory in `extract/ingest.py` stays as the routing complement — it finds ST2/ST6 by name without a full read.)*
- **1c** "Is-my-data-clean?" pass — adaptive QC + **honest "your data has a problem" flags** (wrong shape, NaNs, non-integer counts where counts are required, batch≈condition confound), as a structured report per modality. *(s42 native-moat pick #2.)* **DONE:** the report (`engine/qc.py`, s43) + the **guardrail on the run path** (s48) — `POST /skills/{id}/run` blocks a `block`-severity problem unless `override=true` (D-e5, structured 422 + fix hints) and surfaces the verdict as `data_check`.
- **1d** Modality / shape detection (raw counts vs DE-results vs proteomics matrix vs metabolomics vs generic) — feeds P3 routing.

### P2 — Table Joining & Synthesis  ·  "table joining"
**Goal:** everything that joins / matches / synthesizes tables — data↔analysis matching, merging
the routed skeleton + extracted goldens + computed results into one ledger, and **L3** so *every*
skill emits a canonical Statistics table.
**Today:** `reproduction_drive.py` merge + `data_map` (heuristic); `skills/_table.py`; the **L3
spec is written but awaiting sign-off** (`docs/records/table-synthesis/spec.md`, 4 decisions).
**Slices:**
- **2a** Sign off the L3 spec (D-t1…D-t4) → build L3 **Tier A** (`pca, composition, cluster, pvca, regression, umap_scrna, annotate, integration, trajectory`). **DONE.**
- **2b** Reader ↔ synthesize integration — `extract/readers.py` tries `synthesize_table` when the native table is absent (tagged lower confidence); re-verify a drive panel end-to-end. **DONE — and the "tagged lower confidence" half was only HALF true until 2026-08-05:** the `Reading` carried `layer`/`source`/`confidence` but `panel_extractor` dropped all three, so a synthesized read scored on the ledger as a native one (VERIFIED / 100). Closed by `docs/provenance-stamping/spec.md` — the provenance now rides `MetricValue`/`ValidationResult`, badges the panel, and caps `selom_confidence` at 75.
- **2c** `proteomics_de` native `de_table` at source (the one real source-fix; closes the Foundry gap). **DONE.**
- **2d** Data-matching robustness — a per-panel "which file feeds this?" picker + a better heuristic; honest `data_unmatched`. **← OPEN (one of the two real P2 remainders).**
- **2e** L3 **Tier B** (`corr_heatmap, sankey, upset, scorecard, boxplot, violin, heatmap`), each gated by a faithfulness check. **DONE — 16 synthesizers registered in `extract/synthesize.py`.**

### P3 — Routing & Guidance  ·  "which analysis to run"
**Goal:** given a paper **or** raw data, suggest the right skill(s) / pipeline — the **guided**
half of Product A.
**Today:** the paper→skill router is strong (skill-keyword-index, 4-layer, `extract/routing/`).
**RAW-data routing does not exist.**
**Slices:**
- **3a** RAW-data router — data shape/modality (from 1d) → suggested skills + a proposed pipeline ("raw counts + 2 conditions → `deg` → `volcano`"). **DONE:** `engine/route.py` `route_data` (s43, registry-validated), now **surfaced for own data** on every run (`POST /skills/{id}/run` → `data_check.routing`) + `POST /data/inspect`, s48.
- **3b** Surface suggestions in the workbench (the guided own-data flow; the C3 intake idea, real). **DONE (s49):** the workbench reads `data_check` on every run — a `DataCheckPanel` shows the modality + QC flags (with fix hints) + the suggested pipeline (clickable to set up the next step), and a `block`-severity verdict (HTTP 422) renders a block card with a "Review & run anyway" override. Browser-verified vs the live BE.
- **3c** Honest "we're not sure → here are options" + the skill-gap signal (reuse the unmatched-term pattern, for data).

### P4 — Analysis & Editable Output
**Goal:** skills run on real data → **uniform `{figure, table}`** → the editor as the universal
sink + paste-ready methods.
**Today:** ~30 skills, the figure editor, the publication theme, lit-synth methods (~70%). Strong;
the gap is contract uniformity + the methods/legend wiring.
**Slices:**
- **4a** Skill-contract uniformity audit — every in-scope skill emits `{figure, table}` (via L3 where native is absent); fill only the gaps the two products actually hit. **DONE, and it grew:** the wire is now `StatsTable | StatsTable[] | null` (a figure may carry MORE than one Statistics table — DECISIONS #15, `docs/stats-tables/spec.md`, five slices), narrowed at exactly one site per side. ⚑ **The audit's own by-product was the sharpest reachability finding to date: 17 of 27 native-table skills declared `outputs:["figure"]` — the CATALOG told users they emit no table while they do.**
- **4b** Editor-as-sink hardening (any `{figure, table}` renders + edits anywhere — the chart-extractor already proved the sink). **DONE.**
- **4c** Methods / figure-legend layer wiring (umbrella §11 remainder, ~70% on lit-synth) — paste-ready methods + legend for any run. **DONE (s47):** the methods half already shipped (lit-synth); the legend half is new — `legends.py` (the per-skill caption sibling of `methods.build_body`, params-honest + result-enriched via the canonical `readers.de_counts`), wired onto `/skills/{id}/run` as `figure_legend`, plus `litsynth/legends_from_ledger.compose_ledger_legends` + `GET /papers/{slug}/legends` (the reproduction twin of `/methods`).

### P5 — Reproduction & Scoring  ·  the proving ground (consumes P1–P4)
**Goal:** paper + data → route → drive → grade → two-axis Score. **The floor shipped (s41/s42).**
Now harden **credibility**.
**Today:** `reproduction_drive` + `reproduction_runs` + Phase-3 FE + 4 validated ledgers + the
two-axis Score.
**~~ACTIVE PHASE (s50, owner-picked)~~ — SUPERSEDED as the active phase (see the status block at the
top; the live sequencing is `docs/build-plan-2026-08/plan.md` + `agent_handoff/CURRENT.md` NEXT).**
The *Reproduction — dogfood-ready* plan (**`docs/records/reproduction-dogfood/spec.md`**, covering
**5b/5c/5d + P2 2d + P3 3c**) is still the task-of-record **for those slices**, and the owner's why
still holds: dogfood many papers to *train the engine*, given limited own omics data.
⚑ **What changed is the blocker, not the intent** — the dogfood drive is **data-availability bound**
([[selom-live-reproduction-drive]]): more staged papers+data, not more engine work. Do not read the
slices below as shovel-ready.
**Slices:**
- **5a** Metric-type-aware tolerance grader — tie the band to known engine deltas ([[selom-gsea-engine-sensitivity]], Melody↔Harmony) so **engine-delta ≠ irreproducible** in `validate_panel`. **DONE (s46):** `metric_type` on `Golden` → family band (`METRIC_TYPE_TOLERANCES` + `infer_metric_type`/`resolve_tolerances`); explicit per-golden tolerance still wins; the drive auto-types its goldens; 4 ledgers byte-identical.
- **5b** Generic-extractor coverage (more metrics readable without a hand ledger; rides P2/L3).
- **5c** The 4 validated ledgers (RPGRIP1/JEV/Hani/Dorgau) become **regression fixtures** over the auto-drive — catch engine drift.
- **5d** Live-repro edge hardening (`data_unmatched` / `needs_recipe` honesty under more real papers).

### P6 — Parking Lot  ·  on-hold
**Goal:** capture every off-thesis sidetrack so nothing is lost, and **stop working it** until the
spine is solid. Registry: `docs/on-hold/README.md` (pointer + why-parked + recover-from + which
pillar it would rejoin). Nothing deleted, nothing moved out of its existing home.

### Architecture-audit slices (2026-07-02) — tracked in `docs/restructure/plan.md`

The audit added these slices to the master backlog; detail + acceptance bars live in the
restructure tracker (WS ids in parens). Ordered Product-A-first per the owner.

- **Honesty (gates deploy):** `_stub_figure()` prod guard — no fabricated figures off-dev
  (WS1.1) · methods-text ↔ `param_spec` accuracy guard (WS1.2) · unify the run-path error
  taxonomy (WS2.6).
- **P1 (ingest & clean):** QC coverage vs deliberately-broken real data — extends 1c (WS2.5) ·
  messy-input ingest robustness — extends 1d (WS2.4) · converge the two ingest/classify paths
  onto a shared primitive — extends 1b (WS3.1).
- **P3 (routing & guidance):** honest "we're not sure → here are options" — 3c (WS2.4) ·
  surface the data-fit verdict on own-data (WS2.3) · intake "correct the detection"
  affordances (WS2.2).
- **P4 (analysis & output):** close the upload→run→save loop so an own-data run is a saved
  Library artifact — the reachability gap (WS2.1).
- **Cross-cutting dedup (NEXT#1):** column-override → one resolver (WS3.2) · param validation
  → drop the redundant gate (WS3.3).
- **Process (solo trim):** slim `CURRENT.md` (WS5.1) · solo-mode handoff note (WS5.2) · prune
  the docs load (WS5.3).

---

## 3. Sequencing (dependencies, not a fixed calendar)

1. **P1a — engine-structure spec** *(keystone, in progress)* names the spine + `DataBundle` so
   the rest builds *to* a structure. `docs/engine-spine/spec.md`.
2. Then the **two structure-bearing tracks** can proceed largely in parallel:
   - **P2a/2b/2c** (L3 + table joining) — already specced; the clearest "table joining" wins.
   - **P1c/1d + P3a** (clean + route raw data) — the Product-A path that the spine has been missing.
3. **P5a** (tolerance grader) **DONE (s46)**; **P4a** (contract uniformity) rides on top once P2/L3 lands.
4. **P6** stays parked throughout; an item only leaves the lot by an explicit owner decision that
   names the pillar it rejoins.

**Discipline going forward:** before starting any task, name the pillar it serves. If it serves
none of P1–P5, it is a P6 item — write the pointer and move on. This is the guardrail against the
s25–s42 drift.

---

## 4. Inventory snapshot (s25–s42)

| Status | Items |
|---|---|
| **Done — engine-relevant** | ~30 analysis skills · clean-room Melody + Harmony2 · `ingest_paper`/`PaperBundle` · routing (skill-keyword-index 4-layer) · `extract/golden` · L1/L2 readers · `reproduction_drive` (merge+match+drive+grade) · `reproduction_runs` + Phase-3 FE · two-axis Score · figure editor + publication theme · lit-synth methods (~70%) · 4 validated ledgers |
| **Done — surfaces** | Workspace Library · umbrella shell (`/paper/[id]`) · Skill Match FE · chart extractor (`/extract`) · paper metadata + auto-rename · gene-set builder Phase A |
| **Not done — engine-core** | _(All engine-core skeletons now exist. DONE s43–s48: canonical `DataBundle` + unified ingest registry · is-my-data-clean? QC **+ the run-path guardrail** · RAW-data routing **surfaced for own data** · runner-takes-a-`DataBundle` (both products load through `engine.ingest` end-to-end) · `engine/match.py` · L3 table-synthesis · metric-type tolerance grader · `proteomics_de` native `de_table` · P4 methods/figure-legend wiring.)_ **Remaining = the circle-back FE pass only:** the guided-workbench panel (`data_check` surfaced, P3b) · the L3 FE Statistics-node wiring · the methods/legend FE panel · the async `…/jobs` QC gate (small BE follow-up). |
| **On-hold (P6)** | journal styles · BAM ingest · Ask-Selom chat · atlas reproductions · external-tool builds (ARCHS4/phylo/eggNOG) · ClawBio HOST slice · pipeline flow animation · digitize-this-panel bridge · gene-set messy lists · command-center C/B platform · Supabase/arq/Kaleido infra · OSCA Gap E · pdf.js region-capture |
| **Good to do (serves P1–P5)** | _(The engine-core backlog is cleared — RAW-data router P3a, is-my-data-clean P1c + guardrail, runner-takes-`DataBundle` P1§1b all DONE s43–s48.)_ **The circle-back FE/UX pass landed s49: P3b guided workbench (data-check verdict + block/override), L3 Statistics node ("Computed by Selom"), methods/legend panel — all browser-verified vs the live BE.** Remaining FE polish: the Pro/AI legend-polish tier; an own-data run isn't yet a saved Library artifact. |
