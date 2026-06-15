# Pillar 1 — Liveness & Lineage · Research Brief

> **Phase process** (owner-set 2026-06-15): deep research → thorough owner interview →
> design → spec (`docs/pillar-1-liveness-lineage/spec.md`) → plan → build. This is the
> **research** step of the *hybrid* path (aim → brief → deep interview). It ends in the
> open questions that drive the interview; it is **not** a design or a commitment.
>
> _Filed: 2026-06-15 · Claude (FE+BE acting) · feeds the Pillar-1 interview._

---

## 0. Owner steering (pinned, from the aim-setting round)

The deep research was aimed by three owner answers (2026-06-15):

1. **Liveness model = stale-flag + explicit re-run.** When upstream data/params change,
   downstream figures are marked *out of date*; the user clicks to recompute. **Not**
   reactive auto-cascade (omics recompute is expensive). This is the *build-system* model.
2. **All four jobs matter** — catch staleness · retrace & defend choices · branch & compare
   variants · freeze the finals. None deprioritized; the brief covers the full surface.
3. **Freeze = immutable snapshot.** A locked copy that can never silently change; any edit
   *forks* a new version off it.

These three already cut the design space hard: we are building **a content-hashed dependency
graph with explicit recompute and immutable freeze points** — closer to dbt/Nextflow/git than
to Prism/Observable's live-recompute.

---

## 1. What "liveness & lineage" means for Selom

- **Lineage** — the directed graph of *how a figure came to be*: `dataset → cleaning → skill
  run(params) → figure → (edits) → published/frozen`. Edges already exist in the data model
  (`FigureRef.datasetId` + `.skillId`); the per-figure **provenance bundle** already records
  the node contents. What's missing is treating these as a *living, queryable graph* rather
  than detached point-in-time records.
- **Liveness** — keeping the graph *honest over time*: when a node's inputs change, everything
  downstream is **knowably stale** until re-run; frozen nodes are immune. Selom has **none** of
  this today (no staleness, no re-run-from-lineage, no freeze).

The product thesis ("is THIS the right, reproducible figure for my paper?") makes both
load-bearing: a stale figure is a *wrong* figure, and an un-retraceable figure is an
*indefensible* one.

---

## 2. Current Selom substrate (what we build on)

**Already have (the lineage skeleton + the staleness inputs):**

| Asset | Where | What it gives Pillar 1 |
|---|---|---|
| Figure→source edges | `lib/projects/types.ts` `FigureRef{datasetId, skillId}` | the graph's edges (shallow) |
| Per-figure provenance bundle | `app/backend/provenance.py` | **the rerun-trigger manifest** — input **SHA-256** + bytes, resolved+typed params, skill **id+version**, env (interpreter + scientific-stack versions) |
| Methods prose + guardrails | `methods.py`, `guardrails.py` | the "defend choices" half already exists |
| Pipeline visual | `components/pipeline.tsx` | a **static** Data→Skill→Figure→Publish stage tracker (not reactive, not per-artifact) |
| Figure edit history | `hooks/use-figure-store.ts` | intra-figure undo/redo (one figure's edit lineage) |
| Async jobs + result store | charter B3 (`POST /skills/{id}/jobs`) | the substrate explicit re-run runs on |
| Supabase-aligned schema | `docs/command-center/design.md §5` | `figure_history` table is **speced but unrealized** |

**Gaps (the Pillar-1 work):**
- No **staleness signal** — nothing diffs a figure's stored bundle against the current
  (dataset, params, skill version, env) to know it's out of date.
- No **re-run-from-lineage** — can't say "recompute this figure against the new data" from the
  figure itself; the user re-drives the whole Workbench flow.
- No **freeze/lock** — no immutable snapshot; edits mutate in place.
- No **lineage rail** — no per-artifact "family" view; the pipeline component is project-global
  and static.
- No **versioning / branch** — `figure_history` unrealized; the figure store keeps undo/redo but
  nothing durable, named, or comparable.

**The core insight:** the provenance bundle is *already* the multi-factor manifest the best
build systems hash for staleness. Liveness is mostly **surfacing a diff of records we already
keep**, not new capture.

---

## 3. Prior art (what to borrow, what to avoid)

### 3.1 GraphPad Prism — "everything is hot-linked" + the family workrail  *(closest analog)*
Prism keeps data → analyses → graphs **linked**; editing data auto-updates every downstream
result and graph. The left **navigator** organises every project into a fixed, vertically
ordered set of **section types** — the spine the scientist navigates:

> **Data tables** (Excel-like sheets, one per dataset) → **Analyses / Results** (the statistics
> a table feeds, e.g. a t-test or ANOVA, listed under their source table) → **Graphs** (the
> figure each analysis/data feeds, editable) → **Layouts** (a page canvas that composes
> multiple graphs into a publication multi-panel figure).

**Owner steer (2026-06-15, explicit):** *replicate this flow.* The owner specifically values how
the workrail makes the **connection between raw data and the final output figure obvious and
seamless** — Data → (Statistics) → Figure → Layout, each section feeding the next, top to
bottom in the left rail. He flagged the **Statistics** section (between Data and Figure) and the
**Layout** section (canvas multiple figures) as parts he wants. This largely answers open
question **B1** (the lineage rail *is* a Prism-style sectioned workrail) and adds the **Layout**
node type, which Selom does not have today.

- **Borrow:** the **sectioned family workrail** (Data → Stats/Analysis → Figure → Layout) as the
  primary IA, scoped per project; the rail itself *is* the visible lineage.
- **Diverge (deliberately):** Prism *auto-recomputes* because its analyses are cheap (small
  tables). Selom's are not → the owner picked **stale-flag + explicit re-run**. This is the
  defining Selom-vs-Prism distinction to document: *same linkage, honest about cost.*
- **New scope it surfaces:** a **Layout / multi-panel composition** capability (canvas N figures
  into Fig 1A–F). It belongs *in* the lineage flow (a Layout node depends on its Figure nodes,
  so it inherits staleness + freeze), but the layout *editor* is editor-pillar work — note the
  seam now, scope the editor later.
- Prism has **no** methods-text/repro-bundle and **no** real freeze — Selom's opening.

### 3.2 dbt (Slim CI: `state:modified` + `defer`)  *(staleness via manifest diff)*
Every dbt run emits a **manifest** describing each model's SQL, config, and dependencies.
Comparing the PR manifest against production's identifies *exactly what changed*; `defer`
reuses unchanged upstream artifacts instead of rebuilding them.
- **Borrow:** **state comparison via a stored manifest.** Selom's provenance bundle *is* that
  manifest. Diff the live (dataset-hash, params, skill-version, env) against the figure's stored
  bundle → the stale set. Reuse unchanged upstream (don't recompute a UMAP to refresh a
  downstream volcano if the UMAP's inputs are unchanged).

### 3.3 Snakemake `--rerun-triggers` + Nextflow `-resume`  *(content-hash rerun triggers)*
Snakemake reruns a job when any of **{input, params, code, mtime, software-env}** changes (all
on by default). Nextflow hashes **{input values, files+timestamps, command string, container
id, script content}** per task; a matching hash = cache hit = skip.
- **Borrow:** the **multi-factor trigger set** — staleness ≠ "data changed" alone. Selom's
  bundle already records the analogous factors: input **sha256** (≈ input+mtime), **resolved
  params**, **skill version** (≈ code), **env packages** (≈ software-env). So Selom can compute
  a Snakemake-grade "would re-run because: *params changed*" signal, with the *reason* shown.
- **Borrow:** **content-addressed identity** — a figure's identity = hash of its full trigger
  set; equal hash ⇒ no recompute needed (a free cache/idempotence story for re-run).

### 3.4 git + Figma version history  *(branch & compare, freeze)*
git: immutable content-addressed commits, branches for divergent variants, tags for "this is
the release." Figma: named version history + "duplicate as draft."
- **Borrow for "branch & compare":** forking an analysis (two clustering resolutions, two DE
  contrasts) = a **branch**; keep both, compare side by side.
- **Borrow for "freeze = immutable snapshot":** a frozen figure = a **commit/tag** — an
  immutable, content-addressed copy; editing it **forks** (exactly the owner's model). The
  unrealized `figure_history` table is the object store.

### 3.5 W3C PROV + noWorkflow  *(retrace & defend, interop)*
W3C **PROV-DM** models provenance as **Entity / Activity / Agent** relations for traceability,
reproducibility, and FAIRness; **noWorkflow** transparently captures Python-script provenance.
- **Map:** Selom's lineage is a PROV graph — Entity = dataset/figure/gene-set, Activity = skill
  run, Agent = user. The bundle is a proto-PROV record. **PROV is the export/interop target**
  if lineage ever leaves Selom (a FAIR/repro selling point), not an internal must-have now.

### 3.6 Observable / reactive notebooks  *(the road NOT taken — useful contrast)*
Observable's runtime builds a dependency graph and **auto-recomputes** downstream cells on
change. Jupyter's *lack* of this is the infamous "stale cell / hidden state" reproducibility
trap.
- **Lesson:** auto-reactivity is delightful on cheap cells and dangerous on expensive ones.
  Selom's stale-flag model is the **deliberate middle**: keep Observable's *honesty about the
  dependency graph* (you always know what's stale) without its *automatic* (and here,
  expensive) recompute, and without Jupyter's *silent* staleness.

---

## 4. Synthesis — the shape Pillar 1 wants to take

> **One sentence:** *Promote the per-figure provenance bundle into a project-level lineage
> graph, diff each node's stored trigger-set against the live one to flag staleness with a
> reason, recompute on explicit click (reusing unchanged upstream), let users branch variants,
> and freeze figures as immutable content-addressed snapshots.*

Concretely, the pieces (to be designed after the interview):

1. **Lineage graph + sectioned workrail** — make `FigureRef` edges + bundles a queryable
   per-project DAG, and surface it as a **Prism-style sectioned left workrail** (owner steer):
   **Data → Statistics/Analysis → Figure → Layout**, each section feeding the next so the
   raw-data→output connection is obvious. The rail *is* the visible lineage; nodes carry the
   pipeline colours. (Selom's current `pipeline.tsx` is the embryo; today it lacks the per-node
   Data/Stats/Figure/Layout sections and the lineage edges.)
2. **Staleness engine** — a pure function `isStale(figure) = diff(figure.bundle, live trigger
   set)` returning `{stale, reasons[]}` (reasons = which of {data hash, params, skill version,
   env} diverged — Snakemake-grade). Mostly **already computable** from stored data.
3. **Explicit re-run** — a "Re-run" affordance on a stale figure that replays its bundle's
   (skill, params) against the current dataset via the B3 jobs path; **defer/reuse** unchanged
   upstream.
4. **Branch & compare** — fork a figure/analysis into a named variant; a compare view.
5. **Freeze** — an immutable snapshot (content-addressed); edits fork. Realizes `figure_history`.
6. **Retrace/defend** — the bundle + methods + guardrails already serve this; lineage makes it
   *navigable* (click any node → its receipts), and PROV export is the stretch.

**Cheapest-first ordering hypothesis** (for the plan, not yet decided): staleness signal (2)
is highest value / lowest cost because the data is already captured → it's a *display* of a
diff. Freeze (5) and branch (4) need the `figure_history` object store. Re-run (3) leans on B3.

---

## 5. Key tensions & open questions → for the deep interview

These are the decisions the brief deliberately leaves open; the **deep owner interview** resolves
them before any design/spec.

**Liveness / staleness**
- A1. Granularity of the trigger set — should *which* factor changed gate the signal? (e.g. an
  env package bump: stale, or ignore patch versions? A param tweak vs a whole new dataset?)
- A2. When data is *replaced* vs *appended* — same dataset id, new hash. Is that always "stale,"
  or do some edits (relabeling samples) not invalidate?
- A3. Does staleness propagate **transitively** (re-run UMAP → every downstream marker/DEG figure
  flags) and is that shown as a cascade or per-figure?

**Lineage rail / IA**  *(B1 largely answered by the owner steer — see §3.1)*
- B1. ✔ Direction set: a **Prism-style sectioned left workrail** (Data → Statistics → Figure →
  Layout). Remaining: does it *replace* the current tab bar (Overview/Data/Workbench/Figure) or
  sit beside it? How do the existing tabs map onto the four sections?
- B2. Granularity — does each section list items per *figure*, per *analysis*, or per *dataset
  lineage*? (Prism: a Data table → its Analyses → their Graphs.) What's the unit you think in?
- B3. The **Statistics/Analysis** section — in Selom many skills *are* the analysis-and-figure in
  one (a volcano both computes and plots). Does Stats become its own node (e.g. a DE table you
  can inspect *before* the figure), or is it folded into the skill run? (Ties to Pillar 3's
  Analysis Checklist.)
- B4. **Layout** section — is multi-panel composition (Fig 1A–F) in scope for Pillar 1's flow, or
  captured now as a node type and built as a later editor feature? How does a Layout's staleness
  /freeze relate to its member figures?

**Branch & compare**
- C1. What's the real branching trigger in your work — parameter sweeps (clustering resolution,
  DE thresholds), alternative datasets, or alternative skills for the same question?
- C2. Compare = side-by-side figures, a params/stats **diff**, or both?

**Freeze**
- D1. Freeze granularity — a single figure, or a whole "figure family" (data+analysis+figure) as
  one immutable unit? (Matters for a multi-panel paper figure.)
- D2. On re-run of a frozen figure's lineage, what happens — a new *unfrozen* fork beside the
  frozen original, with a visible "frozen vs current differs" badge?

**Scope / sequencing**
- E1. Single-user dogfood reality: is this mostly **your** workflow on RPGRIP1/Fidelle/ALPK1
  data, or are you designing for the eventual multi-user SaaS already?
- E2. Which of the four jobs is the *wedge* to ship first if we slice Pillar 1? (Hypothesis:
  staleness signal — cheapest, built on existing data — but your call.)

---

## 6. Sources

- [GraphPad Prism — Everything is hot linked](https://www.graphpad.com/guides/prism/latest/user-guide/everything_is_hot_linked.htm) · [Working with families of sheets](https://www.graphpad.com/guides/prism/latest/user-guide/families_of_sheets.htm)
- [dbt — Defer](https://docs.getdbt.com/reference/node-selection/defer) · [Slim CI via state comparison + deferred refs (issue #2641)](https://github.com/fishtown-analytics/dbt/issues/2641) · [Airbyte: How to use dbt defer](https://airbyte.com/data-engineering-resources/how-to-use-dbt-defer)
- [Snakemake CLI — `--rerun-triggers` (code/input/mtime/params/software-env)](https://snakemake.readthedocs.io/en/stable/executing/cli.html)
- [Nextflow — Caching and resuming (task hash)](https://www.nextflow.io/docs/latest/cache-and-resume.html)
- [W3C PROV family of specifications](https://dl.acm.org/doi/10.1145/2452376.2452478) · [noWorkflow (VLDB)](https://dl.acm.org/doi/abs/10.14778/3137765.3137789)
