"use client";

import { useSyncExternalStore } from "react";
import { mockQcReport } from "@/lib/intake/mock";
import type { Dataset, FigureRef, GeneSet, Modality, Project, ProjectState, SkillInstall } from "./types";

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

function ds(projectId: string, id: string, filename: string, modality: Modality, t: number): Dataset {
  return { id, projectId, filename, modality, qc: mockQcReport(modality), createdAt: t };
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
  const figures: FigureRef[] = [
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
          // Tolerate state persisted before geneSets existed (added in the gene-set builder).
          state = { ...parsed, geneSets: parsed.geneSets ?? [] };
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
  deleteProject(id: string) {
    setState({
      projects: state.projects.filter((p) => p.id !== id),
      datasets: state.datasets.filter((d) => d.projectId !== id),
      installs: state.installs.filter((i) => i.projectId !== id),
      figures: state.figures.filter((f) => f.projectId !== id),
      geneSets: state.geneSets.filter((g) => g.projectId !== id),
    });
  },
  addDataset(projectId: string, filename: string, modality: Modality): Dataset {
    const d = ds(projectId, uid("ds"), filename, modality, Date.now());
    setState({ ...state, datasets: [...state.datasets, d] });
    return d;
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
  addFigure(projectId: string, fig: { title: string; datasetId?: string; skillId?: string }): FigureRef {
    const f: FigureRef = { id: uid("f"), projectId, title: fig.title, datasetId: fig.datasetId, skillId: fig.skillId, createdAt: Date.now() };
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
