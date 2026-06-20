"use client";

import { useSyncExternalStore } from "react";
import type { GeneSet, ProjectState, SkillInstall } from "@/lib/projects/types";
import type { SavedPaper, WorkspaceSkill, WorkspaceState } from "./types";

/**
 * Mock `WorkspaceStore` — the localStorage-backed implementation of the project- and
 * data-AGNOSTIC Workspace Library (docs/workspace-library/spec.md §4).
 *
 * A near-copy of `projectStore`'s proven pattern so the swap to a real account/DB+auth
 * backend is an impl change, not a caller rewrite (the persistence seam, spec §4): every
 * caller only ever touches `workspaceStore` / `useWorkspace` (spec I1). SSR-safe — the
 * seed is the server snapshot and the first client snapshot, so hydration matches; the
 * persisted state (and the one-time migration from project scope) loads once on the
 * client via `hydrate()` (spec I2).
 */

const KEY = "selom.workspace.v1";
/** The project-store key the one-time migration reads from (spec §6). */
const PROJECTS_KEY = "selom.projects.v1";

function uid(prefix: string): string {
  // Browser-only mutator path; safe to use crypto here.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
  return `${prefix}_${Math.floor(Math.random() * 1e9).toString(36)}`;
}

/** Deterministic empty seed (stable → no SSR/hydration mismatch). The Library starts empty;
 *  the first `hydrate()` migrates any project-scoped gene sets + installs in (spec §6). */
function seed(): WorkspaceState {
  return { papers: [], geneSets: [], skills: [] };
}

let state: WorkspaceState = seed();
let hydrated = false;
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

function persist() {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* storage unavailable (private mode / quota) — stay in-memory */
  }
}

function setState(next: WorkspaceState) {
  state = next;
  persist();
  emit();
}

/**
 * One-time, NON-DESTRUCTIVE migration (spec §6, I4): lift the assets that used to hang off a
 * project into the account-level workspace. The projectStore copies are read, never deleted —
 * callers stop reading them once they point at the workspace (a tracked follow-up, not a
 * big-bang rewrite). Returns a fresh seed if there's nothing to migrate.
 */
function migrateFromProjects(): WorkspaceState {
  const next = seed();
  try {
    const raw = localStorage.getItem(PROJECTS_KEY);
    if (!raw) return next;
    const projects = JSON.parse(raw) as Partial<ProjectState>;
    // Gene sets: lift all of them, deduped on the source catalog id (createdFrom) so the
    // same panel saved into two projects collapses to one workspace entry.
    const seenFrom = new Set<string>();
    for (const g of projects.geneSets ?? []) {
      if (g.createdFrom != null) {
        if (seenFrom.has(g.createdFrom)) continue;
        seenFrom.add(g.createdFrom);
      }
      next.geneSets.push(g);
    }
    // Installs: the union of skill ids across every project becomes the workspace skill library.
    const seenSkill = new Set<string>();
    for (const i of (projects.installs ?? []) as SkillInstall[]) {
      if (seenSkill.has(i.skillId)) continue;
      seenSkill.add(i.skillId);
      next.skills.push({ id: uid("ws"), skillId: i.skillId, installedAt: i.installedAt });
    }
  } catch {
    /* corrupt projects snapshot — migrate nothing, start clean */
  }
  return next;
}

export const workspaceStore = {
  subscribe(cb: () => void): () => void {
    listeners.add(cb);
    return () => listeners.delete(cb);
  },
  getSnapshot(): WorkspaceState {
    return state;
  },
  getServerSnapshot(): WorkspaceState {
    return state;
  },

  /** Load persisted state on the client (once); on a first run, run the project→workspace
   *  migration. Safe post-hydration (the `hydrated` flag makes it a no-op thereafter). */
  hydrate() {
    if (hydrated || typeof window === "undefined") return;
    hydrated = true;
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<WorkspaceState>;
        if (parsed && typeof parsed === "object") {
          // Tolerate snapshots persisted before a collection existed.
          state = {
            papers: parsed.papers ?? [],
            geneSets: parsed.geneSets ?? [],
            skills: parsed.skills ?? [],
          };
          emit();
        }
      } else {
        // First run on this client — migrate project-scoped assets in, then persist.
        state = migrateFromProjects();
        persist();
        emit();
      }
    } catch {
      /* ignore corrupt storage */
    }
  },

  // ── papers ───────────────────────────────────────────────────────────────
  /** Save a Skill-Match result. Idempotent on `doi || filename` (spec I3): re-saving the
   *  same paper updates the existing record in place, never duplicates. Returns the saved row. */
  savePaper(p: Omit<SavedPaper, "id" | "savedAt">): SavedPaper {
    const dedupKey = (x: { doi?: string | null; filename: string }) =>
      (x.doi && x.doi.trim()) || x.filename;
    const key = dedupKey(p);
    const existing = state.papers.find((x) => dedupKey(x) === key);
    const saved: SavedPaper = {
      ...p,
      id: existing?.id ?? uid("paper"),
      savedAt: Date.now(),
    };
    setState({
      ...state,
      papers: existing
        ? state.papers.map((x) => (x.id === existing.id ? saved : x))
        : [saved, ...state.papers],
    });
    return saved;
  },
  /** Remove a saved paper, returning the removed record so the caller can offer an Undo. */
  removePaper(id: string): SavedPaper | undefined {
    const removed = state.papers.find((p) => p.id === id);
    if (removed) setState({ ...state, papers: state.papers.filter((p) => p.id !== id) });
    return removed;
  },
  /** Re-insert a removed paper (Undo). No-op if it's already present. */
  restorePaper(paper: SavedPaper) {
    if (state.papers.some((p) => p.id === paper.id)) return;
    setState({ ...state, papers: [paper, ...state.papers] });
  },

  // ── gene sets ──────────────────────────────────────────────────────────────
  /** Save a gene set into the workspace (idempotent on the source catalog id). */
  saveGeneSet(set: Omit<GeneSet, "id" | "projectId" | "createdAt">): GeneSet {
    const existing = state.geneSets.find(
      (g) => g.createdFrom != null && g.createdFrom === set.createdFrom,
    );
    if (existing) return existing;
    // projectId is vestigial at the workspace level (spec D1); keep the field shape for the
    // GeneSet type + the later DB row, but it no longer scopes anything.
    const g: GeneSet = { ...set, id: uid("gs"), projectId: "", createdAt: Date.now() };
    setState({ ...state, geneSets: [g, ...state.geneSets] });
    return g;
  },
  removeGeneSet(id: string) {
    setState({ ...state, geneSets: state.geneSets.filter((g) => g.id !== id) });
  },

  // ── skills ───────────────────────────────────────────────────────────────
  installSkill(skillId: string) {
    if (state.skills.some((s) => s.skillId === skillId)) return;
    const s: WorkspaceSkill = { id: uid("ws"), skillId, installedAt: Date.now() };
    setState({ ...state, skills: [...state.skills, s] });
  },
  uninstallSkill(skillId: string) {
    setState({ ...state, skills: state.skills.filter((s) => s.skillId !== skillId) });
  },
};

// ── selectors (pure) ───────────────────────────────────────────────────────────
export const wselect = {
  papers: (s: WorkspaceState) => s.papers,
  geneSets: (s: WorkspaceState) => s.geneSets,
  skills: (s: WorkspaceState) => s.skills,
  installedSkillIds: (s: WorkspaceState) => new Set(s.skills.map((x) => x.skillId)),
  hasSkill: (s: WorkspaceState, skillId: string) => s.skills.some((x) => x.skillId === skillId),
};

/** Reactive snapshot hook. */
export function useWorkspace(): WorkspaceState {
  return useSyncExternalStore(workspaceStore.subscribe, workspaceStore.getSnapshot, workspaceStore.getServerSnapshot);
}
