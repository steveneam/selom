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

## 7. Decisions to confirm (owner sign-off needed)

- **D1 — Promotion scope.** Which collections move to the workspace? The memory says papers + gene
  sets + skills. Confirm; in particular whether **skill installs** become purely workspace-level (a
  skill installed once is available in every project) vs staying project-scoped.
- **D2 — Dual vs single home.** For anything promoted, do project-level copies still exist (dual:
  workspace default + per-project override) or is the workspace the single source of truth (simpler;
  the Store/Gene Sets surfaces stop asking "which project")? Recommendation: **single home** — it's the
  whole point ("project-agnostic") and avoids two-writer ambiguity.
- **D3 — SavedPaper depth.** Store the compact **summary** (recommended — small, all the Library needs)
  vs the full re-openable `FeasibilityMap` (re-open shows the exact per-figure rows without re-routing,
  but bloats localStorage). Recommendation: **summary**, with a "re-drop to re-route per-figure" path.

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
