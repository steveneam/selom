"use client";

import { useSyncExternalStore } from "react";
import { mockQcReport } from "@/lib/intake/mock";
import type { FigureSpec } from "@/lib/figure-spec";
import type { Dataset, Figure, GeneSet, Modality, Project, ProjectState, SkillInstall } from "./types";

/**
 * Mock `ProjectStore` — the localStorage-backed implementation of the projects
 * data layer (docs/command-center/design.md §5). Schema-aligned to the planned
 * Supabase tables so the swap (phase B4) replaces this module, not its callers.
 *
 * SSR-safe: the seed is the server snapshot and the first client snapshot, so
 * hydration matches; localStorage is read once on the client via `hydrate()`.
 */

const KEY = "selom.projects.v1";

export const PROJECT_COLORS = [
  "#22d3ee", "#a78bfa", "#fb923c", "#34d399", "#f472b6", "#facc15", "#60a5fa", "#f87171",
];

function uid(prefix: string): string {
  // Browser-only mutator path; safe to use crypto here.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
  return `${prefix}_${Math.floor(Math.random() * 1e9).toString(36)}`;
}

/**
 * Deterministic sha256-shaped stand-in derived from a seed string (FNV-1a, expanded
 * to 64 hex chars). Stable for a given id → no SSR/hydration mismatch and a
 * real-looking input hash in the repro panel. The dogfood mock has no real bytes to
 * hash; the real backend supplies the genuine sha256 on ingest (Pillar 1).
 */
function hexFrom(seed: string): string {
  let h = 0x811c9dc5;
  let out = "";
  let s = seed;
  while (out.length < 64) {
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    out += h.toString(16).padStart(8, "0");
    s = out;
  }
  return out.slice(0, 64);
}

/** A fresh random data version (client-only mutator path) — used to simulate the
 *  dataset's bytes changing, so figures built on the old bytes read as stale. */
function randomSha(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return (crypto.randomUUID() + crypto.randomUUID()).replace(/-/g, "").slice(0, 64);
  }
  return hexFrom(`${Math.random()}`);
}

function ds(projectId: string, id: string, filename: string, modality: Modality, t: number): Dataset {
  return { id, projectId, filename, modality, currentSha256: hexFrom(id), qc: mockQcReport(modality), createdAt: t };
}

/** Deterministic seed (stable ids → no hydration mismatch). */
function seed(): ProjectState {
  const t = 1_749_000_000_000; // fixed epoch for the seed
  const projects: Project[] = [
    { id: "demo-pbmc", name: "PBMC scRNA-seq", color: "#22d3ee", createdAt: t },
    { id: "demo-tumor", name: "Tumor bulk DEG", color: "#fb923c", createdAt: t - 86_400_000 },
    { id: "demo-phospho", name: "Phosphoproteomics", color: "#a78bfa", createdAt: t - 2 * 86_400_000 },
  ];
  const datasets: Dataset[] = [
    ds("demo-pbmc", "demo-pbmc-ds", "pbmc3k.h5ad", "scRNA-seq", t),
    ds("demo-tumor", "demo-tumor-ds", "tumor_counts.csv", "bulk RNA-seq", t - 86_400_000),
  ];
  const installs: SkillInstall[] = [
    { id: "i1", projectId: "demo-pbmc", skillId: "selom.umap_scrna", installedAt: t },
    { id: "i2", projectId: "demo-pbmc", skillId: "selom.deg", installedAt: t },
    { id: "i3", projectId: "demo-tumor", skillId: "selom.deg", installedAt: t },
    { id: "i4", projectId: "demo-tumor", skillId: "selom.volcano", installedAt: t },
  ];
  const figures: Figure[] = [
    { id: "f1", projectId: "demo-pbmc", datasetId: "demo-pbmc-ds", skillId: "selom.umap_scrna", title: "UMAP — Leiden clusters", createdAt: t },
  ];
  return { projects, datasets, installs, figures, geneSets: [] };
}

let state: ProjectState = seed();
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

function setState(next: ProjectState) {
  state = next;
  persist();
  emit();
}

export const projectStore = {
  subscribe(cb: () => void): () => void {
    listeners.add(cb);
    return () => listeners.delete(cb);
  },
  getSnapshot(): ProjectState {
    return state;
  },
  getServerSnapshot(): ProjectState {
    return state;
  },

  /** Load persisted state on the client (once). Safe post-hydration. */
  hydrate() {
    if (hydrated || typeof window === "undefined") return;
    hydrated = true;
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as ProjectState;
        if (parsed && Array.isArray(parsed.projects)) {
          // Tolerate state persisted before later fields existed: geneSets (gene-set
          // builder) and figures persisted before Pillar 1 (no `spec`/`provenance` —
          // they load fine since those fields are optional; the editor flags them as
          // "spec not stored (legacy)" rather than crashing).
          state = { ...parsed, geneSets: parsed.geneSets ?? [], figures: parsed.figures ?? [] };
          emit();
        }
      } else {
        persist(); // first run — write the seed
      }
    } catch {
      /* ignore corrupt storage */
    }
  },

  // ── mutators ─────────────────────────────────────────────────────────────
  createProject(name: string, color?: string): Project {
    const p: Project = {
      id: uid("p"),
      name: name.trim() || "Untitled project",
      color: color ?? PROJECT_COLORS[state.projects.length % PROJECT_COLORS.length],
      createdAt: Date.now(),
    };
    setState({ ...state, projects: [p, ...state.projects] });
    return p;
  },
  renameProject(id: string, name: string) {
    setState({ ...state, projects: state.projects.map((p) => (p.id === id ? { ...p, name } : p)) });
  },
  /**
   * Delete a project and everything in it, returning a snapshot of exactly what was
   * removed so the caller can offer an Undo (the mock has no server-side trash). A
   * confirmed delete is otherwise irreversible — the snapshot is the only safety net.
   */
  deleteProject(id: string): ProjectState {
    const removed: ProjectState = {
      projects: state.projects.filter((p) => p.id === id),
      datasets: state.datasets.filter((d) => d.projectId === id),
      installs: state.installs.filter((i) => i.projectId === id),
      figures: state.figures.filter((f) => f.projectId === id),
      geneSets: state.geneSets.filter((g) => g.projectId === id),
    };
    setState({
      projects: state.projects.filter((p) => p.id !== id),
      datasets: state.datasets.filter((d) => d.projectId !== id),
      installs: state.installs.filter((i) => i.projectId !== id),
      figures: state.figures.filter((f) => f.projectId !== id),
      geneSets: state.geneSets.filter((g) => g.projectId !== id),
    });
    return removed;
  },
  /** Re-insert a deleted project's slices (Undo). No-op for ids already present. */
  restoreProject(snap: ProjectState) {
    const has = new Set(state.projects.map((p) => p.id));
    if (snap.projects.some((p) => has.has(p.id))) return;
    setState({
      projects: [...snap.projects, ...state.projects],
      datasets: [...state.datasets, ...snap.datasets],
      installs: [...state.installs, ...snap.installs],
      figures: [...state.figures, ...snap.figures],
      geneSets: [...state.geneSets, ...snap.geneSets],
    });
  },
  addDataset(projectId: string, filename: string, modality: Modality): Dataset {
    const d = ds(projectId, uid("ds"), filename, modality, Date.now());
    setState({ ...state, datasets: [...state.datasets, d] });
    return d;
  },
  /** Apply the live engine inspect result to a dataset (lib/intake/inspect.ts): the real
   *  modality + cleaning/QC report, replacing the optimistic filename-only guess. Persisted, so
   *  re-opening the dataset shows the real verdict without re-uploading the bytes. */
  updateDatasetProfile(id: string, patch: { modality?: Modality; qc?: import("./types").QcReport }) {
    setState({
      ...state,
      datasets: state.datasets.map((d) =>
        d.id === id
          ? { ...d, modality: patch.modality ?? d.modality, qc: patch.qc ?? d.qc }
          : d,
      ),
    });
  },
  /** Rename a dataset (Pillar 1 family). An empty label clears the override (back to
   *  the filename); the change propagates to every figure/stat chip built on it. */
  renameDataset(id: string, label: string) {
    const next = label.trim() || undefined;
    setState({ ...state, datasets: state.datasets.map((d) => (d.id === id ? { ...d, label: next } : d)) });
  },
  /** Delete one dataset (only the dataset — its figures are left in place, just without
   *  a live data link). Returns the removed record so the caller can offer an Undo. */
  removeDataset(id: string): Dataset | undefined {
    const d = state.datasets.find((x) => x.id === id);
    if (d) setState({ ...state, datasets: state.datasets.filter((x) => x.id !== id) });
    return d;
  },
  /** Re-insert a deleted dataset (Undo). No-op if it's already present. */
  restoreDataset(dataset: Dataset) {
    if (state.datasets.some((d) => d.id === dataset.id)) return;
    setState({ ...state, datasets: [...state.datasets, dataset] });
  },
  /**
   * Mark a dataset's bytes as changed — bumps `currentSha256` to a new version so
   * every figure built on the old bytes reads as stale (Pillar 1). The real trigger
   * is a re-ingest with different bytes; this is the dogfood/dev stand-in for it.
   */
  markDatasetUpdated(id: string): void {
    setState({
      ...state,
      datasets: state.datasets.map((d) => (d.id === id ? { ...d, currentSha256: randomSha() } : d)),
    });
  },
  installSkill(projectId: string, skillId: string) {
    if (state.installs.some((i) => i.projectId === projectId && i.skillId === skillId)) return;
    const i: SkillInstall = { id: uid("i"), projectId, skillId, installedAt: Date.now() };
    setState({ ...state, installs: [...state.installs, i] });
  },
  uninstallSkill(projectId: string, skillId: string) {
    setState({
      ...state,
      installs: state.installs.filter((i) => !(i.projectId === projectId && i.skillId === skillId)),
    });
  },
  /**
   * Persist a produced figure durably — its full Plotly `spec`, the provenance
   * `bundle`, the Statistics `table`, and any lineage (`parentFigureId` on a
   * re-run / variant). Pillar 1: the spec + bundle were transient before this.
   */
  addFigure(projectId: string, fig: Omit<Figure, "id" | "projectId" | "createdAt">): Figure {
    const f: Figure = { ...fig, id: uid("f"), projectId, createdAt: Date.now() };
    setState({ ...state, figures: [...state.figures, f] });
    return f;
  },
  /** Persist an in-canvas edit back to the figure's stored spec (durable working spec). */
  updateFigureSpec(id: string, spec: FigureSpec) {
    setState({ ...state, figures: state.figures.map((f) => (f.id === id ? { ...f, spec } : f)) });
  },
  /**
   * Tag a figure as frozen ("paper") or unfreeze it (Pillar 1, S3, Decision D6). A
   * frozen figure is immutable in the editor — editing it forks a new version via
   * `forkFigure` — so this is just a flag; nothing else changes.
   */
  freezeFigure(id: string, frozen: boolean) {
    setState({ ...state, figures: state.figures.map((f) => (f.id === id ? { ...f, frozen } : f)) });
  },
  /** Delete one figure, returning the removed record so the caller can offer an Undo. */
  removeFigure(id: string): Figure | undefined {
    const fig = state.figures.find((f) => f.id === id);
    if (fig) setState({ ...state, figures: state.figures.filter((f) => f.id !== id) });
    return fig;
  },
  /** Re-insert a deleted figure (Undo). No-op if it's already present. */
  restoreFigure(fig: Figure) {
    if (state.figures.some((f) => f.id === fig.id)) return;
    setState({ ...state, figures: [...state.figures, fig] });
  },
  /**
   * Fork a figure into a new sibling version (copies the parent, applies `patch`,
   * links via `parentFigureId`). A fork is always unfrozen — editing a frozen
   * "paper" figure forks an editable copy (Decision D6). Never mutates the parent.
   */
  forkFigure(parentId: string, patch: Partial<Omit<Figure, "id" | "projectId" | "createdAt">> = {}): Figure | null {
    const parent = state.figures.find((f) => f.id === parentId);
    if (!parent) return null;
    const f: Figure = { ...parent, ...patch, id: uid("f"), parentFigureId: parentId, frozen: false, createdAt: Date.now() };
    setState({ ...state, figures: [...state.figures, f] });
    return f;
  },
  /** Save a gene set into a project (idempotent on the source catalog id within a project). */
  saveGeneSet(projectId: string, set: Omit<GeneSet, "id" | "projectId" | "createdAt">): GeneSet {
    const existing = state.geneSets.find(
      (g) => g.projectId === projectId && g.createdFrom != null && g.createdFrom === set.createdFrom,
    );
    if (existing) return existing;
    const g: GeneSet = { ...set, id: uid("gs"), projectId, createdAt: Date.now() };
    setState({ ...state, geneSets: [g, ...state.geneSets] });
    return g;
  },
  removeGeneSet(id: string) {
    setState({ ...state, geneSets: state.geneSets.filter((g) => g.id !== id) });
  },
};

// ── selectors ────────────────────────────────────────────────────────────────
export const select = {
  project: (s: ProjectState, id: string) => s.projects.find((p) => p.id === id),
  datasets: (s: ProjectState, id: string) => s.datasets.filter((d) => d.projectId === id),
  installs: (s: ProjectState, id: string) => s.installs.filter((i) => i.projectId === id),
  installedIds: (s: ProjectState, id: string) => s.installs.filter((i) => i.projectId === id).map((i) => i.skillId),
  figures: (s: ProjectState, id: string) => s.figures.filter((f) => f.projectId === id),
  geneSets: (s: ProjectState, id: string) => (s.geneSets ?? []).filter((g) => g.projectId === id),
};

/** Reactive snapshot hook. */
export function useProjects(): ProjectState {
  return useSyncExternalStore(projectStore.subscribe, projectStore.getSnapshot, projectStore.getServerSnapshot);
}
