/**
 * Workspace-Library domain types (docs/workspace-library/spec.md §3).
 *
 * The Workspace Library is the project- and data-AGNOSTIC home for the assets a user
 * accumulates: saved papers (Skill-Match results), gene sets, and skill installs. These
 * outlive any single project, so they're stored at the account level rather than hanging
 * off a `projectId`.
 *
 * Shaped — like `lib/projects/types.ts` — to match a planned account/DB schema so the
 * later swap from the localStorage mock to a real `WorkspaceStore` (Supabase + auth) is a
 * backend-impl change, not a FE rewrite. No component imports a backend SDK directly;
 * everything goes through `workspaceStore` / `useWorkspace` (spec I1).
 */

import type { GeneSet } from "@/lib/projects/types";

/**
 * The kind of a supplementary file, mirroring the backend ingest contract
 * (app/backend/extract/ingest.py): a PDF supplement carries *extended methods*; an Excel or
 * CSV supplement carries *supplementary tables* (the golden numbers like ST2 / ST6 the
 * Reproduction engine matches against).
 */
export type SupplementKind = "pdf" | "xlsx" | "csv";

/**
 * One supplementary file attached to a saved paper during the Reproduction stage (the umbrella
 * §10 stage-2 input the owner asked for). Compact metadata only — NO bytes / object URL
 * (spec I5); the dropped `File` lives in session state for the later live drive, while this
 * record (filename + kind + size) persists on the Paper anchor so the Library remembers what
 * the user attached.
 */
export interface SavedSupplement {
  id: string;
  filename: string;
  kind: SupplementKind;
  /** Bytes — for display only. */
  size?: number;
  addedAt: number;
}

/**
 * A saved Skill-Match result — the paper's metadata + its routed skill summary, kept so
 * the user can revisit "what skills does this paper need" without re-dropping the PDF.
 * Compact by design (no PDF bytes, no object URL — those are session-only; spec I5).
 *
 * This is the substrate for the owner's "unified Paper workflow" umbrella (spec §10): it
 * is intentionally designed to EXTEND into the Paper anchor that Skill Match, Reproduction,
 * and Recover-data all read/write — hence the reserved optional fields at the bottom.
 */
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
  url?: string | null;
  // routed summary (the L3 inventory + per-figure rollup, NOT the live FeasibilityMap)
  skills: string[]; // bare slugs (resolve to catalog names at render, as the chips do)
  outOfScope: string[]; // oos reason slugs
  figureCount: number;
  tierSummary: { structured: number; recovered: number };
  savedAt: number;

  // ── The unified Paper workflow (spec §10); the anchor extends without a type migration. ──
  /** The live-reproduction run id once the paper's drive succeeds (live-reproduction-spec §7).
   *  The Score stage reads this to GET /reproduction-runs/{id} and render the driven ledger. */
  reproductionRunId?: string;
  /** Supplementary files attached in the Reproduction stage (stage 2) — Excel / CSV tables +
   *  extended-methods PDFs. Metadata only (no bytes; spec I5). */
  supplements?: SavedSupplement[];
  /** Recovered-figure ids saved from the in-viewer region grab (stage 3). */
  recoveredFigures?: string[];
}

/** A workspace-level skill install — the account-wide "library of skills I've added"
 *  (replaces the per-project `SkillInstall` once installs are promoted; spec D1). */
export interface WorkspaceSkill {
  id: string;
  skillId: string; // catalog id, e.g. "selom.deg"
  installedAt: number;
}

/** The full denormalized workspace snapshot (mirrors `ProjectState`'s shape + discipline). */
export interface WorkspaceState {
  papers: SavedPaper[];
  /** Promoted out of project scope (spec D1) — `GeneSet.projectId` becomes vestigial here. */
  geneSets: GeneSet[];
  skills: WorkspaceSkill[];
}
