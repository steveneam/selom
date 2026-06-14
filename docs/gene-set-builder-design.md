# Gene-Set Builder — design & plan (for owner sign-off)

> **Status: APPROVED 2026-06-14 (DECISIONS #11).** Owner idea: *"a user types what kind of
> list/features they want to include, Selom goes out to see what lists are available, compiles
> it, and has it ready to use/apply to their data."* This doc builds that license-cleanly on top
> of what Selom already has; the four §7 decisions are ratified. **Approved next step: §8 — Phase A
> + the WikiPathways (CC0) ingest.** Per-phase plans still presented before each phase is built
> (charter rule). _Filed · Claude (acting FE+BE)._

## 1. What the user is really asking for

A **gene set** (a named list of genes) is the unit that powers half of Selom's biology:
- `enrichment` / `pathway` / `go_graph` test a DE result *against* reference gene sets (ORA).
- `heatmap` / `violin` plot the expression of *a chosen list*.
- `volcano` can *highlight* a panel (e.g. "just the ciliopathy genes").

So "build me a list of X" serves two distinct jobs, and the design should do both:
- **(L) a flat LIST** — one curated set of genes for a topic ("phototransduction", "my retinal
  panel") → to subset / highlight / plot.
- **(C) a reference COLLECTION** — many named sets → the library `enrichment` scores against.

The owner's phrasing ("type what you want → find available lists → compile → apply") is mostly
(L) with a **discovery** step, but the same machinery yields (C). Build for both, list-first.

## 2. What Selom already has (so we don't reinvent)

- **GO library** — 7,727 license-clean sets (BP/MF/CC) built from GO GAF+OBO (CC-BY), plus the
  GO DAG (`scripts/build_gene_sets.py` → `gene_sets_go.json` / `go_dag.json`). Used by
  `enrichment` + `go_graph`. **This is already a searchable gene-set corpus.**
- **Reactome** — live AnalysisService + ContentService (CC0) in the new `pathway` skill.
- **Custom curated lists** staged from real data — Ciliopathy, Proteostasis (UPS / autophagy-
  lysosome / chaperones), plus Phototransduction / Cilia / Mitochondria (under `D:\selom-data`).
  **Provenance/licensing must be confirmed before shipping these as owned panels.**
- **In-house ORA** (hypergeometric + BH) + the publish-confidence **provenance** pattern — a
  compiled set should carry the same provenance discipline (sources, versions, query, license).
- The **DECISIONS #9** guardrail: **no gseapy / MSigDB** in the shipped product (license).

So a v1 can launch on **assets we already own or that are open**, with zero licensing risk.

## 3. The source landscape (the crux is licensing)

| Source | Content | License | Use in Selom |
|---|---|---|---|
| **GO** (GAF+OBO) | 7.7k ontology sets | CC-BY 4.0 | ✅ shipped already |
| **Reactome** | ~2.6k pathways | CC0 | ✅ live (`pathway`) |
| **WikiPathways** | curated pathways, GMT | **CC0** | ✅ strong add — open KEGG alternative |
| **HGNC gene groups** | gene families/groups | open (EBI) | ✅ "families" + symbol normalization |
| **HPO / Monarch** | phenotype → gene | open | ✅ "genes for phenotype/disease X" |
| **Open Targets** | gene–disease assoc. | CC0 | ✅ "genes associated with disease X" |
| **PanglaoDB / CellMarker** | cell-type markers | CC-BY / academic | ⚠️ per-source check; good for scRNA |
| **DisGeNET** | gene–disease | ⚠️ NC / paid tiers | gate or avoid |
| **MSigDB** (Hallmark/C2/KEGG-via-MSigDB/…) | the big GSEA corpus | **license-gated** | ❌ ship-blocked (DECISIONS #9); gate before launch |
| **KEGG** (bulk/REST) | pathways | academic-only; commercial-gated | ⚠️ gate before launch |
| **Enrichr / Harmonizome / Geneshot** (Ma'ayan) | aggregated libs + literature gene-finder | academic API; mixed per-lib | ⚠️ query-time only, not redistribution; Geneshot great for free-text→genes |
| **g:Profiler (g:GOSt / g:Convert)** | GO/Reactome/WP/HP + ID mapping | open (ELIXIR) | ✅ optional enrichment/oracle + ID convert |

**Takeaway:** an *open core* (GO + Reactome + WikiPathways + HGNC + HPO + Open Targets) gives broad
coverage with no licensing risk. Commercial sources (MSigDB, KEGG) stay behind the launch gate,
clearly labeled — consistent with build-now-gate-later.

## 4. Recommended shape — staged, open-core, provenance-first

### Phase A — Gene-Set catalog (small; mostly wiring existing assets)
Make gene sets a **first-class browsable/searchable thing** in the UI, sourced from what we own:
- Surface the existing GO library + Reactome + a few owned curated panels in a **"Gene Sets"**
  surface (a tab, or a Store category). Search by name/description; show size + source + license.
- Pick a set → **apply to data**: subset/highlight in `volcano`, plot in `heatmap`/`violin`, or
  use as the `enrichment` query/background. (Chains into skills we already have.)
- Add **WikiPathways (CC0)** as a one-time license-clean ingest (extends `build_gene_sets.py`).
- *Effort:* small. *Risk:* none (owned/open). *Ships the owner's idea in minimal form.*

### Phase B — the Builder (the owner's vision): keyword → compile → apply
A `gene_set` builder = a BE service + a small UI:
1. **Search** `POST /gene-sets/search?q="ciliopathy"` → ranked candidate **named sets** across the
   open sources, each with {name, source, size, license, a few member genes}.
2. **Select & compile** → union / intersect the chosen sets → **dedup to HGNC-approved symbols**
   (HGNC normalization), drop ambiguous/withdrawn.
3. **Provenance** — every compiled set records {query, sources+versions, set ids, dedup rule,
   license, n_genes} (the publish-confidence pattern). Reproducible + citable.
4. **Save & apply** — store as a Selom **GeneSet** object (schema-aligned to the future Supabase
   tables), immediately usable by `enrichment`/`heatmap`/`violin`/`volcano`/`pathway`.
- *Effort:* medium (source adapters + search + dedup + cache/offline bundle for the big libs).
- *Risk:* per-source licensing diligence; network/rate-limits → cache + bundle the open libs.

### Phase C — smart free-text → genes (a layer on B, not standalone)
"Type a concept, get genes" via the Selom **AI gateway** (or Geneshot's literature co-mention),
but **grounded**: every proposed gene is backed by an evidence set from Phase B sources and shown
with that evidence — never an ungrounded LLM list. Always **propose → user confirms** (same rule
as the intake LLM: the model proposes, never auto-applies). *Effort:* medium; *Risk:* hallucination
(mitigated by grounding) + LLM cost. Best after B exists.

## 5. Architecture fit
- New first-class object **`GeneSet`** {id, name, genes[], sources[], provenance, license,
  created_from(query)} in `ProjectStore` (localStorage now → Supabase later), mirroring how
  projects/figures already persist.
- BE: a `gene_sets/` module with **source adapters** (one per source, open-core first), a search
  index over set names/descriptions, a compile/dedup step (HGNC), and a provenance builder reusing
  `provenance.py` conventions. Endpoints `GET/POST /gene-sets...`. Big open libs ship as a bundled,
  versioned data file (like `gene_sets_go.json`) + a refresh script; live APIs only for breadth.
- FE: a "Gene Sets" surface (search → candidate cards with source/size/license → pick/union/
  intersect → save) that chains into the existing skill-apply flow. Desktop-only (per house rule).
- License labeling everywhere: each set/candidate shows its license; commercial sources are gated
  and visibly marked.

## 6. Why this is a genuine moat (not just a feature)
"Drop your data → describe the biology you care about → get a license-clean, **provenance-stamped**
gene set ready to apply, with auto-methods text" is exactly Selom's publish-confidence thesis applied
to gene sets. Competitors lean on MSigDB (license friction) or leave list-building to the user; an
open-core, reproducible, apply-in-one-click builder is differentiated and launch-safe.

## 7. Decisions — ratified by owner 2026-06-14 (DECISIONS #11)
1. **Primary job — RESOLVED: list-first UX, collection-capable architecture, built once.** The two
   jobs share ~90% of the machinery (sources, search, dedup, provenance); the only difference is
   presentation (one list vs many named sets). So we **don't choose** — we build the unified
   `GeneSet` object + open-core adapters once, **lead the UX with list-building** (the tangible,
   magical "type a topic → compile → apply" that matches the owner's framing), and expose the same
   corpus as the `enrichment`/ORA library underneath. *Future-proofing:* every open-core source
   added for the list-builder also expands the ORA library for free — they compound — and the
   provenance-stamped `GeneSet` is the durable abstraction Supabase persistence, sharing, and the
   Skill Foundry all build on. **(This is the recommended best-experience + future-proof path.)**
2. **Build order — RESOLVED: open-core first.** Ship the open-core builder before the LLM/literature
   free-text→genes layer (which lands later, grounded — propose, user confirms).
3. **Custom lists — RESOLVED: ship as our own.** The Fidelle-derived Ciliopathy / Proteostasis sets
   become **owned Selom curated panels** (no third party is claiming them).
4. **MSigDB / KEGG — RESOLVED: validation/oracle use only, dropped pre-launch.** Keep using them to
   validate Selom's ORA (the staged GSEA/GO oracle tables) **until our own open-core library reaches
   parity/capacity**, then drop them at the pre-launch gate (clean, easy removal — never wired into
   the shipped library).

## 8. Suggested first step (if approved)
Phase A + the **WikiPathways (CC0) ingest** — it's mostly wiring assets we already own, ships the
idea immediately, and de-risks Phase B by proving the GeneSet object + apply flow end-to-end. Then
build the Phase B builder over the open-core adapters.
