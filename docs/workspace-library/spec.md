# Workspace Library — spec

> Status: **DRAFT — awaiting owner sign-off on the model** (§Decisions). Spec-first per the owner
> direction (2026-06-20, s35). Build only after the open decisions are resolved.
> Lane: the **client store + FE is Claude's lane**; the real account/DB persistence is a later
> **backend** contract (§Persistence seam). No backend work is in scope for v1.

## 1. Why

Today every reusable asset a user accumulates hangs off a **project**:

- **Gene sets** save into a project (`projectStore.saveGeneSet(projectId, …)`; the Gene Sets surface
  picks a `target` project, defaulting to `projects[0]` or creating one).
- **Skill installs** are `projectId`-scoped (`installSkill(projectId, skillId)`).
- **Saved papers don't exist yet** — Skill Match routes a paper but you can't keep the result; you
  re-drop the PDF every time.

The owner's framing: *"those things should be available for different datasets, project- and
data-agnostic."* A gene panel you curated, a skill you verified, a paper you've already matched to
skills — none of these are *about* one dataset. They're account-level assets. The current coupling
forces a project context onto things that outlive any single project.

**Goal:** one **project- and data-agnostic Workspace Library** — a home for saved papers, gene sets,
and skills that's reusable across every project and dataset, built behind a clean persistence seam so
the localStorage mock swaps for a real account/DB+auth later without callers changing.

This is the convergence point [[selom-command-center-architecture]] gestures at (Skill Store + gene
sets + the Foundry) and the provenance-first, reusable ethos of [[selom-gene-set-builder]].

## 2. Scope (v1)

In:
- A new **`workspaceStore`** (localStorage-backed mock) mirroring `projectStore`'s shape and SSR-safe
  hydration, exposing `subscribe`/`getSnapshot`/`hydrate` + typed mutators + selectors + a
  `useWorkspace()` hook.
- Collections: **`papers: SavedPaper[]`**, plus whichever of `geneSets` / `skills` the owner promotes
  (§Decisions D1).
- **Skill Match → Save**: a "Save to Library" action that writes a `SavedPaper` (idempotent on DOI /
  filename) — the result becomes revisitable without re-dropping the PDF.
- A **Library FE surface** (§5): a rail entry + a page with one tab per collection; each row reusable
  (re-open a paper's summary, apply a gene set, open a skill in the Store).
- A **one-time migration** that lifts existing project-scoped gene sets (and installs, if promoted)
  into the workspace on first hydrate (§6), so nothing already saved is lost.

Out (deferred / later contract):
- Real backend persistence + auth (the seam is designed for it; the impl is a BE contract).
- Cross-device sync, sharing, team libraries.
- Re-running a saved paper's routing live (v1 stores the summary; re-drop to re-route).

## 3. Data model

```ts
// lib/workspace/types.ts  (new)

/** A saved Skill-Match result — the paper's metadata + its routed skill summary, kept so the user
 *  can revisit "what skills does this paper need" without re-dropping the PDF. Compact by design
 *  (no PDF bytes, no object URL — those are session-only). */
export interface SavedPaper {
  id: string;
  // identity / dedup
  filename: string;
  doi?: string | null;
  pmid?: string | null;
  // bibliographic (from paper_metadata — any field may be absent)
  title?: string | null;
  authors?: string[] | null;
  venue?: string | null;
  year?: number | null;
  volume?: string | null;
  issue?: string | null;
  pages?: string | null;
  isPreprint?: boolean;
  // routed summary (the L3 inventory + per-figure rollup, NOT the live FeasibilityMap object)
  skills: string[];               // bare slugs (resolve to catalog names at render, as the chips do)
  outOfScope: string[];           // oos reason slugs
  figureCount: number;
  tierSummary: { structured: number; recovered: number };
  savedAt: number;
}

/** The full denormalized workspace snapshot (mirrors ProjectState's shape + discipline). */
export interface WorkspaceState {
  papers: SavedPaper[];
  geneSets: GeneSet[];      // promoted out of project scope (D1) — GeneSet.projectId becomes vestigial
  skills: WorkspaceSkill[]; // workspace-level installs (D1)
}

/** A workspace-level skill install (replaces per-project SkillInstall if installs are promoted). */
export interface WorkspaceSkill {
  id: string;
  skillId: string;          // catalog id, e.g. "selom.deg"
  installedAt: number;
}
```

`SavedPaper` deliberately stores the **summary**, not the full `FeasibilityMap` (D3): the per-figure
candidate arrays are large and re-derivable from the PDF; the summary is what the Library shows.

## 4. Store shape (the seam)

`lib/workspace/store.ts` — a near-copy of `projectStore`'s proven pattern so the swap to a backend is
an impl change, not a caller rewrite:

```ts
export const workspaceStore = {
  subscribe(cb): () => void,
  getSnapshot(): WorkspaceState,
  getServerSnapshot(): WorkspaceState,   // SSR seed === first client snapshot (no hydration mismatch)
  hydrate(): void,                       // load localStorage once on the client; run the migration
  // papers
  savePaper(p: Omit<SavedPaper,"id"|"savedAt">): SavedPaper,   // idempotent on doi || filename
  removePaper(id): SavedPaper | undefined,
  restorePaper(p): void,                                       // Undo
  // gene sets (if promoted)
  saveGeneSet(set): GeneSet,
  removeGeneSet(id): void,
  // skills (if promoted)
  installSkill(skillId): void,
  uninstallSkill(skillId): void,
};
export function useWorkspace(): WorkspaceState;   // useSyncExternalStore hook
export const wselect = { /* pure selectors */ };
```

**Persistence seam (the cross-lane boundary).** Callers only ever touch `workspaceStore` /
`useWorkspace`. v1 backs it with `localStorage` (key `selom.workspace.v1`). When the backend lands, a
`WorkspaceStore` interface gets a Supabase/DB impl (owner accounts, RLS) — same method names, so no
component changes. This mirrors litsynth's injected-Fetcher seam and the projectStore→Supabase plan
([[selom-paper-metadata]] discipline).

## 5. FE surface

- **Rail:** a new top-level **"Library"** entry (Phosphor/lucide bookmark icon) under the primary nav,
  near Gene Sets / Skill Store.
- **`/library` page:** a header + a tabbed view — **Papers · Gene sets · Skills** (counts on tabs).
  - *Papers:* each row = metadata line (title · authors · citation · DOI/PMID) + a compact skill
    summary (N skills · M figures) + actions: re-open the summary (reuse `SkillMatchResults` read-only
    with the saved summary), Export (the same Copy/CSV from this session), Remove (with Undo).
  - *Gene sets:* the saved panels, each Apply-able to the active project's data (reuses the gene-set
    apply intent) — now sourced from the workspace, not a single project.
  - *Skills:* workspace-installed skills, linking to the Store detail.
- **Skill Match:** a **"Save to Library"** button beside Copy/CSV. Saving builds the `SavedPaper`
  summary from the current `meta` + `map` (the data already on the client) and writes it via
  `workspaceStore.savePaper`. Idempotent; shows a saved/-✓ state.

## 6. Migration (mock)

On first `workspaceStore.hydrate()` with no `selom.workspace.v1` key:
- Read `selom.projects.v1`; lift **all** `geneSets` across projects into `workspace.geneSets` (dedup on
  `createdFrom`), and (if installs promoted) the union of `installs` skillIds into `workspace.skills`.
- Write the workspace key. The projectStore copies are left in place (non-destructive); selectors stop
  reading them once callers point at the workspace (a follow-up, tracked, not a big-bang rewrite).

## 7. Decisions (RESOLVED by owner 2026-06-20)

- **D1 — Promotion scope → papers + gene sets + skill installs ALL move to the workspace** (single
  home). Plus the owner expanded the vision: saved **recovered figures** (Recover data) and
  **reproduction** artifacts also belong in the Library — see §10 (the unified Paper workflow). v1
  ships papers + gene sets + skills; the Paper anchor is designed to extend to figures/reproduction.
- **D2 — Single workspace home.** The workspace is the one source of truth; Gene Sets / Store stop
  asking "which project". No project-level override layer.
- **D3 — Compact summary.** `SavedPaper` stores the routed summary (metadata + inventory + per-figure
  counts/tiers), not the full `FeasibilityMap`. Re-drop the PDF to see exact per-figure rows again.

## 8. Invariants

- **I1** No component imports `localStorage` or a backend SDK directly — everything goes through
  `workspaceStore` / `useWorkspace` (the seam holds).
- **I2** SSR seed === first client snapshot (deterministic ids; no `Date.now()`/`Math.random()` in the
  seed) — no hydration mismatch, same rule as `projectStore`.
- **I3** Saving a paper is **idempotent** on `doi || filename` (re-saving updates, never duplicates).
- **I4** Migration is **non-destructive** (projectStore data is read, never deleted by v1).
- **I5** `SavedPaper` holds **no PDF bytes / object URLs** (session-only; the Library is text + ids).

## 9. Build plan (after sign-off)

1. `lib/workspace/types.ts` + `lib/workspace/store.ts` + `useWorkspace` + selectors + vitest (seed,
   hydrate, idempotent save, migration).
2. Skill Match **Save to Library** button (builds the summary from `meta`+`map`).
3. `/library` page + rail entry + the three tabs (Papers re-open/Export/Remove first).
4. Re-point Gene Sets (and Store, if installs promoted) at the workspace; wire the migration.
5. (Later, BE contract) the real `WorkspaceStore` persistence + auth.

## 10. North star — the unified Paper workflow (owner vision, 2026-06-20)

The owner's bigger idea: **fold Skill Match + Reproduction + Recover data into one umbrella** over a
single first-class **Paper** object. You drop a PDF once and it flows through stages:

1. **Skill Match** (have) — drop PDF → metadata + the routed skills the paper needs. Deterministic,
   free. This is the *entry point*.
2. **Reproduction** (have, separate surface) — add the **supplementary** data → reproduce the figures
   + numbers with real skills, scored. The paper carries over from stage 1 (no re-drop).
3. **Recover data** (have, separate `/extract`) — a **side action in the PDF viewer**: a "grab figure"
   button → region-select a figure in the viewer → save it; repeat for every figure → "Recover data"
   opens `/extract` pre-loaded with the saved figures for the normal calibrate-and-run.

The **Workspace Library is the connective tissue**: the `SavedPaper` becomes the *Paper anchor* that
all three stages read/write — routed skills (stage 1), a reproduction ledger ref (stage 2), recovered
figures (stage 3) — plus the cross-cutting gene sets + skills. So building the Library now is building
the substrate the umbrella needs regardless of how the shell UX lands.

### Recommendations (Claude)

- **Build the Library foundation now; design `SavedPaper` to extend into the Paper anchor.** Add
  optional `recoveredFigures?` / `reproductionId?` later without a rewrite. The foundation (store +
  Save + the three collections) is not in dispute and unblocks everything else. Don't build the
  umbrella *shell* yet — sequence it after the substrate exists.
- **Reproduction splits into a deterministic engine and a recipe-inference step — gate the latter, not
  the former (owner pushed on this 2026-06-20; the refined answer).** Skill Match answers *which* skills;
  Reproduction answers *how they were used* (params, thresholds, contrasts, design formula, ordering,
  filtering). That splits cleanly:
  - **The engine — run the skills, the parameter *sweep*, the R oracle, the score — is fully
    deterministic.** It's stronger than it sounds because **the printed numbers are the oracle**: you
    don't infer the recipe blind, you *search a parameter space for what hits a known target*. The sweep
    already recovered RPGRIP1's "numbers only reconcile at *unadjusted* p" with zero semantics. This is
    the moat + the honesty layer (it flags *paper-irreproducible* when nothing matches). **Never gate it.**
  - **Recipe inference from the methods prose has a deterministic floor and a real ceiling.** Floor
    (keyword/regex/sweep) reproduces well-specified single-number figures; ceiling = vague or complex
    multi-step pipelines (design formula / order / subsetting) that need reading comprehension. Honest
    tell: across all 4 ledgers the hard recipe-reading was done by an agent reading the STAR methods,
    not a deterministic extractor — so the hard cases already depend on a semantic reader, just not a
    productized one.
  - **Resolution — AI proposes, deterministic disposes.** For messy papers an LLM/RAG pass *proposes*
    the recipe / narrows the search; the deterministic engine *executes* + *validates against the
    printed numbers*. The AI hypothesises, it never "reproduces" — so validation stays deterministic and
    honest. This is the legitimate **Pro/AI gate**: free reproduces cleanly-specified figures (extraction
    + sweep); Pro cracks the vague/complex ones (AI proposes → engine validates). Same open-core, layered
    model as Skill Match ([[layered-deterministic-extraction]]).
- **Recover-data-in-viewer needs a renderer swap (the key enabler).** Today the PDF is a native
  browser viewer in an `<iframe>` — the parent page **cannot** draw a selection rectangle over it or
  map coordinates to PDF pages (it's an embedded chrome viewer). Region-select capture requires
  rendering the PDF ourselves on a `<canvas>` via **pdfjs-dist** (Apache-2.0, license-clean). That swap
  is self-contained and unlocks a lot (overlay capture, per-figure thumbnails, annotations). It also
  dovetails with the already-decided extract↔reproduction bridge (the "Digitize this panel" entry —
  [[selom-extract-reproduction-bridge]]): the viewer capture is the more general "grab any region"
  version of it. Scope it as its own piece after the Library foundation.
- **Sequencing.** Foundation (Library store + Save + collections) → paper-anchor handoff (Skill Match →
  Reproduction carrying the Paper) → pdf.js viewer + region capture (Recover data) → the umbrella shell
  (one nav, stages as tabs over a Paper). Each is its own scoped, owner-gated step.

### Open questions for the umbrella (defer until the foundation exists)
- Does the umbrella replace the three separate nav entries with one "Paper" workspace, or keep them as
  deep-links into stages? (Lean: keep the surfaces, add a unifying "open in Reproduction / Recover"
  flow first; collapse into one shell once the handoffs are proven.)
- Where do supplementary uploads live on the Paper anchor (stage 2)?
- Is a "Paper" the same primitive as a `Project`, or a lighter object a Project can reference?
