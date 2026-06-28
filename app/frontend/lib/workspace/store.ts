"use client";

import { useSyncExternalStore } from "react";
import { api } from "@/lib/api/client";
import type { GeneSet, ProjectState, SkillInstall } from "@/lib/projects/types";
import type { SavedPaper, SavedSupplement, WorkspaceSkill, WorkspaceState } from "./types";
import {
  fromApiGeneSet, fromApiPaper, queue, reconcileFetchWorkspace, toApiGeneSet, toApiPaper,
} from "./sync";

/**
 * `WorkspaceStore` — the optimistic, API-backed Workspace Library (AWS materialization step 7c).
 *
 * Same sync-read / async-write shape as `projectStore` (sub-spec §2.2): the in-memory `state` stays
 * the synchronous source of truth (unchanged interface), each mutator writes through to a
 * localStorage mirror and enqueues the durable API write, and `hydrate()` reconciles against the
 * server. Paper mutations (supplements, data map, run id) re-upsert the WHOLE paper — the backend
 * reconciles its supplement children in one call — coalesced per paper so an edit burst is one POST.
 */

const KEY = "selom.workspace.v1";
/** The project-store key the one-time *local* migration reads from (the mirror seed; spec §6). */
const PROJECTS_KEY = "selom.projects.v1";
const DELETE_GRACE_MS = 7000;

function uid(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID().replace(/-/g, "")}`;
  }
  return `${prefix}_${Math.floor(Math.random() * 1e9).toString(36)}${Math.floor(Math.random() * 1e9).toString(36)}`;
}

/** Deterministic empty seed (stable → no SSR/hydration mismatch). */
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

/** Enqueue a coalesced whole-paper upsert (per paper id). */
function pushPaper(p: SavedPaper) {
  queue.enqueue({ coalesceKey: `paper:${p.id}`, run: () => api.post("/workspace/papers", toApiPaper(p)) });
}

/**
 * One-time, NON-DESTRUCTIVE *local* migration (mirror seed only): lift project-scoped gene sets +
 * installs into the workspace mirror so the FE renders them instantly. The durable server-side
 * migration is the backend import (`importLocalStateOnce`). The projectStore copies are read, never
 * deleted.
 */
function migrateFromProjects(): WorkspaceState {
  const next = seed();
  try {
    const raw = localStorage.getItem(PROJECTS_KEY);
    if (!raw) return next;
    const projects = JSON.parse(raw) as Partial<ProjectState>;
    const seenFrom = new Set<string>();
    for (const g of projects.geneSets ?? []) {
      if (g.createdFrom != null) {
        if (seenFrom.has(g.createdFrom)) continue;
        seenFrom.add(g.createdFrom);
      }
      next.geneSets.push(g);
    }
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

function mergeById<T extends { id: string }>(local: T[], server: T[]): T[] {
  const byId = new Map<string, T>();
  for (const r of local) byId.set(r.id, r);
  for (const r of server) byId.set(r.id, r);
  return [...byId.values()];
}

async function reconcile() {
  if (queue.pending > 0) return; // a write is in flight — don't clobber the newer local row
  try {
    const srv = await reconcileFetchWorkspace();
    setState({
      papers: mergeById(state.papers, srv.papers),
      geneSets: mergeById(state.geneSets, srv.geneSets),
      skills: mergeById(state.skills, srv.skills),
    });
  } catch {
    /* offline / backend down — the mirror already rendered; a later focus retries */
  }
}

let focusBound = false;

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

  /** Load the mirror (or run the local project→workspace migration on a first run), then reconcile. */
  hydrate() {
    if (hydrated || typeof window === "undefined") return;
    hydrated = true;
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<WorkspaceState>;
        if (parsed && typeof parsed === "object") {
          state = { papers: parsed.papers ?? [], geneSets: parsed.geneSets ?? [], skills: parsed.skills ?? [] };
          emit();
        }
      } else {
        state = migrateFromProjects();
        persist();
        emit();
      }
    } catch {
      /* ignore corrupt storage */
    }
    void reconcile();
    if (!focusBound && typeof window.addEventListener === "function") {
      focusBound = true;
      window.addEventListener("focus", () => void reconcile());
    }
  },

  // ── papers ───────────────────────────────────────────────────────────────
  /** Save a Skill-Match result. Idempotent on `doi || filename` (spec I3). */
  savePaper(p: Omit<SavedPaper, "id" | "savedAt">): SavedPaper {
    const dedupKey = (x: { doi?: string | null; filename: string }) => (x.doi && x.doi.trim()) || x.filename;
    const key = dedupKey(p);
    const existing = state.papers.find((x) => dedupKey(x) === key);
    const saved: SavedPaper = { ...p, id: existing?.id ?? uid("paper"), savedAt: Date.now() };
    setState({
      ...state,
      papers: existing ? state.papers.map((x) => (x.id === existing.id ? saved : x)) : [saved, ...state.papers],
    });
    pushPaper(saved);
    return saved;
  },
  /** Remove a saved paper, returning the removed record so the caller can offer an Undo. */
  removePaper(id: string): SavedPaper | undefined {
    const removed = state.papers.find((p) => p.id === id);
    if (removed) {
      setState({ ...state, papers: state.papers.filter((p) => p.id !== id) });
      queue.enqueue({ key: `del:paper:${id}`, graceMs: DELETE_GRACE_MS, run: () => api.del(`/workspace/papers/${id}`) });
    }
    return removed;
  },
  /** Re-insert a removed paper (Undo). No-op if it's already present. */
  restorePaper(paper: SavedPaper) {
    if (state.papers.some((p) => p.id === paper.id)) return;
    setState({ ...state, papers: [paper, ...state.papers] });
    if (queue.cancel(`del:paper:${paper.id}`)) return; // Undo within grace — the DELETE never fired
    pushPaper(paper);
  },

  // ── paper supplements ───────────────────────────────────────────────────────────────────────
  /** Attach supplementary files to a saved paper (metadata only — no bytes, spec I5). */
  addPaperSupplements(paperId: string, items: Omit<SavedSupplement, "id" | "addedAt">[]): SavedPaper | undefined {
    const paper = state.papers.find((p) => p.id === paperId);
    if (!paper) return undefined;
    const have = new Set((paper.supplements ?? []).map((s) => s.filename.toLowerCase()));
    const added: SavedSupplement[] = [];
    for (const it of items) {
      const fn = it.filename.toLowerCase();
      if (have.has(fn)) continue;
      have.add(fn);
      added.push({ ...it, id: uid("supp"), addedAt: Date.now() });
    }
    if (added.length === 0) return paper;
    const updated: SavedPaper = { ...paper, supplements: [...(paper.supplements ?? []), ...added] };
    setState({ ...state, papers: state.papers.map((p) => (p.id === paperId ? updated : p)) });
    pushPaper(updated);
    return updated;
  },
  /** Stamp the live-reproduction run id once a paper's drive succeeds. */
  setPaperReproductionRun(paperId: string, runId: string) {
    const paper = state.papers.find((p) => p.id === paperId);
    if (!paper || paper.reproductionRunId === runId) return;
    const updated: SavedPaper = { ...paper, reproductionRunId: runId };
    setState({ ...state, papers: state.papers.map((p) => (p.id === paperId ? updated : p)) });
    pushPaper(updated);
  },
  /** Persist the per-panel data-picker overrides (panel_key → supplement filename). */
  setPaperDataMap(paperId: string, dataMap: Record<string, string>) {
    const paper = state.papers.find((p) => p.id === paperId);
    if (!paper) return;
    const next = Object.keys(dataMap).length > 0 ? dataMap : undefined;
    if (JSON.stringify(paper.dataMap ?? null) === JSON.stringify(next ?? null)) return;
    const updated: SavedPaper = { ...paper, dataMap: next };
    setState({ ...state, papers: state.papers.map((p) => (p.id === paperId ? updated : p)) });
    pushPaper(updated);
  },
  /** Detach one supplement from a paper by its id. */
  removePaperSupplement(paperId: string, supplementId: string) {
    const paper = state.papers.find((p) => p.id === paperId);
    if (!paper || !paper.supplements) return;
    const updated: SavedPaper = { ...paper, supplements: paper.supplements.filter((s) => s.id !== supplementId) };
    setState({ ...state, papers: state.papers.map((p) => (p.id === paperId ? updated : p)) });
    pushPaper(updated);
  },

  // ── gene sets ──────────────────────────────────────────────────────────────
  /** Save a gene set into the workspace (idempotent on the source catalog id). */
  saveGeneSet(set: Omit<GeneSet, "id" | "projectId" | "createdAt">): GeneSet {
    const existing = state.geneSets.find((g) => g.createdFrom != null && g.createdFrom === set.createdFrom);
    if (existing) return existing;
    const g: GeneSet = { ...set, id: uid("gs"), projectId: "", createdAt: Date.now() };
    setState({ ...state, geneSets: [g, ...state.geneSets] });
    queue.enqueue({
      run: () => api.post("/workspace/gene-sets", toApiGeneSet(g)),
      onPermanentFail: () => setState({ ...state, geneSets: state.geneSets.filter((x) => x.id !== g.id) }),
    });
    return g;
  },
  removeGeneSet(id: string) {
    setState({ ...state, geneSets: state.geneSets.filter((g) => g.id !== id) });
    queue.enqueue({ key: `del:gs:${id}`, graceMs: DELETE_GRACE_MS, run: () => api.del(`/workspace/gene-sets/${id}`) });
  },

  // ── skills ───────────────────────────────────────────────────────────────
  installSkill(skillId: string) {
    if (state.skills.some((s) => s.skillId === skillId)) return;
    const s: WorkspaceSkill = { id: uid("ws"), skillId, installedAt: Date.now() };
    setState({ ...state, skills: [...state.skills, s] });
    queue.enqueue({
      run: () => api.post("/skill-installs", { id: s.id, skill_id: skillId }), // no project → workspace-wide
      onPermanentFail: () => setState({ ...state, skills: state.skills.filter((x) => x.id !== s.id) }),
    });
  },
  uninstallSkill(skillId: string) {
    setState({ ...state, skills: state.skills.filter((s) => s.skillId !== skillId) });
    queue.enqueue({ run: () => api.del(`/skill-installs?skill_id=${encodeURIComponent(skillId)}`) });
  },
};

// ── selectors (pure) ───────────────────────────────────────────────────────────
export const wselect = {
  papers: (s: WorkspaceState) => s.papers,
  paper: (s: WorkspaceState, id: string) => s.papers.find((p) => p.id === id),
  geneSets: (s: WorkspaceState) => s.geneSets,
  skills: (s: WorkspaceState) => s.skills,
  installedSkillIds: (s: WorkspaceState) => new Set(s.skills.map((x) => x.skillId)),
  hasSkill: (s: WorkspaceState, skillId: string) => s.skills.some((x) => x.skillId === skillId),
};

/** Reactive snapshot hook. */
export function useWorkspace(): WorkspaceState {
  return useSyncExternalStore(workspaceStore.subscribe, workspaceStore.getSnapshot, workspaceStore.getServerSnapshot);
}

export { fromApiPaper, fromApiGeneSet };
