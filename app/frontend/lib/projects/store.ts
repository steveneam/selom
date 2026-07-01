"use client";

import { useSyncExternalStore } from "react";
import { mockQcReport } from "@/lib/intake/mock";
import { api } from "@/lib/api/client";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { Dataset, Figure, GeneSet, Modality, Project, ProjectState, QcReport, SkillInstall } from "./types";
import {
  fromApiDataset, fromApiFigure, fromApiGeneSet, fromApiInstall, fromApiProject,
  queue, reconcileFetch, toApiFigure, toApiGeneSet, useSyncStatus,
} from "./sync";

/**
 * `ProjectStore` — the optimistic, API-backed projects data layer (AWS materialization step 7c).
 *
 * **Sync read / async write** (sub-spec §2.2): the in-memory `state` stays the synchronous source of
 * truth, so every mutator keeps its exact signature + value return (zero component edits). Each
 * mutator applies to `state` + writes through to a localStorage MIRROR (instant offline render),
 * then enqueues the durable API write (`./sync` → the write queue). `hydrate()` loads the mirror,
 * then reconciles against the server (the authority). Ids are client-authoritative so an optimistic
 * create needs no temp-id remap and a retried write / Undo is an idempotent upsert.
 *
 * SSR-safe: the seed is the server snapshot + the first client snapshot (hydration matches); the
 * mirror + reconcile run once on the client via `hydrate()`.
 */

const KEY = "selom.projects.v1";
/** Undo window for a delete — an Undo within it cancels the queued DELETE (no data loss, no API). */
const DELETE_GRACE_MS = 7000;

export const PROJECT_COLORS = [
  "#22d3ee", "#a78bfa", "#fb923c", "#34d399", "#f472b6", "#facc15", "#60a5fa", "#f87171",
];

function uid(prefix: string): string {
  // Client-authoritative id (sub-spec §2.2): a FULL uuid hex (not the old 8-char slice) so the
  // per-tenant collision space is negligible — the backend stores this id verbatim.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID().replace(/-/g, "")}`;
  }
  return `${prefix}_${Math.floor(Math.random() * 1e9).toString(36)}${Math.floor(Math.random() * 1e9).toString(36)}`;
}

/**
 * Deterministic sha256-shaped stand-in derived from a seed string (FNV-1a, expanded to 64 hex).
 * Stable for a given id → no SSR/hydration mismatch + a real-looking input hash. The dogfood mock
 * has no real bytes to hash; the real backend supplies the genuine sha256 on ingest (Pillar 1).
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

/** A fresh random data version (client-only mutator path) — simulates the dataset's bytes changing. */
function randomSha(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return (crypto.randomUUID() + crypto.randomUUID()).replace(/-/g, "").slice(0, 64);
  }
  return hexFrom(`${Math.random()}`);
}

/** `qc` is explicit (not auto-fabricated) — the demo seed passes `mockQcReport(...)` (a labeled
 *  example); a REAL dataset created via `addDataset` passes none, so it starts honestly `undefined`
 *  until a live `/data/inspect` succeeds (A2 fix — never render fabricated dims as the user's data). */
function ds(projectId: string, id: string, filename: string, modality: Modality, t: number, qc?: QcReport): Dataset {
  return { id, projectId, filename, modality, currentSha256: hexFrom(id), qc, createdAt: t };
}

/** Deterministic seed (stable ids → no hydration mismatch). Dev scaffolding — for a real signed-in
 *  user it's local-only (never enqueued) and the reconcile merge keeps it beside the server rows. */
function seed(): ProjectState {
  const t = 1_749_000_000_000; // fixed epoch for the seed
  const projects: Project[] = [
    { id: "demo-pbmc", name: "PBMC scRNA-seq", color: "#22d3ee", createdAt: t },
    { id: "demo-tumor", name: "Tumor bulk DEG", color: "#fb923c", createdAt: t - 86_400_000 },
    { id: "demo-phospho", name: "Phosphoproteomics", color: "#a78bfa", createdAt: t - 2 * 86_400_000 },
  ];
  // Demo datasets keep an explicit, labeled example QC (they live under demo-* ids) — a REAL dataset
  // never takes this path (see `addDataset`).
  const datasets: Dataset[] = [
    ds("demo-pbmc", "demo-pbmc-ds", "pbmc3k.h5ad", "scRNA-seq", t, mockQcReport("scRNA-seq")),
    ds("demo-tumor", "demo-tumor-ds", "tumor_counts.csv", "bulk RNA-seq", t - 86_400_000, mockQcReport("bulk RNA-seq")),
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

/** Union-merge the server view into the cache: server wins by id, local-only rows are kept (in-flight
 *  optimistic creates + pre-migration data that hasn't been imported yet). Only runs when the queue is
 *  idle — a pending write means the server is behind, so we must not clobber the newer local row. */
function mergeById<T extends { id: string }>(local: T[], server: T[]): T[] {
  const byId = new Map<string, T>();
  for (const r of local) byId.set(r.id, r);
  for (const r of server) byId.set(r.id, r);
  return [...byId.values()];
}

/** Figures carry a LOCAL-ONLY field — `aiProposals`, the pre-commit AI queue (intentionally not in
 *  toApiFigure/fromApiFigure). The server row never has it, so on a server-wins merge re-attach it
 *  from the local row; otherwise a reconcile (hydrate / window-focus, queue idle) would clobber an
 *  accepted-but-not-yet-re-run proposal → authorOf flips to "user", the ✨ marker vanishes, and the
 *  re-run records NO provenance.actions[] (an AI run mis-logged as human). [[selom-ai-helpers]] */
export function mergeFigures(local: Figure[], server: Figure[]): Figure[] {
  const localById = new Map(local.map((f) => [f.id, f]));
  return mergeById(local, server).map((f) => {
    const prev = localById.get(f.id);
    return f.aiProposals === undefined && prev?.aiProposals ? { ...f, aiProposals: prev.aiProposals } : f;
  });
}

/** Datasets carry LOCAL-ONLY fields too — `routing` + `dataFit` + `design`, the data-aware route +
 *  intake-design prefill the FE persists (owner D2: no backend column, intentionally not in
 *  to/fromApiDataset). On a server-wins merge re-attach them from the local row, else a reconcile
 *  (hydrate / window-focus, queue idle) would clobber the data-driven "Recommended for your data"
 *  chips + the questionnaire's design prefill on reload. Generalizes `mergeFigures`' aiProposals
 *  preservation. [[selom-fe-review-framework]] */
export function mergeDatasets(local: Dataset[], server: Dataset[]): Dataset[] {
  const localById = new Map(local.map((d) => [d.id, d]));
  return mergeById(local, server).map((d) => {
    const prev = localById.get(d.id);
    if (!prev) return d;
    return {
      ...d,
      routing: d.routing ?? prev.routing,
      dataFit: d.dataFit ?? prev.dataFit,
      design: d.design ?? prev.design,
    };
  });
}

async function reconcile() {
  if (queue.pending > 0) return; // a write is in flight — server is stale, don't clobber
  try {
    const srv = await reconcileFetch();
    setState({
      projects: mergeById(state.projects, srv.projects),
      datasets: mergeDatasets(state.datasets, srv.datasets),
      installs: mergeById(state.installs, srv.installs),
      figures: mergeFigures(state.figures, srv.figures),
      geneSets: mergeById(state.geneSets, srv.geneSets),
    });
  } catch {
    /* offline / backend down — the mirror already rendered; a later focus retries */
  }
}

let focusBound = false;

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

  /** Load the mirror (instant), then reconcile against the server (the authority). Once. */
  hydrate() {
    if (hydrated || typeof window === "undefined") return;
    hydrated = true;
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as ProjectState;
        if (parsed && Array.isArray(parsed.projects)) {
          state = { ...parsed, geneSets: parsed.geneSets ?? [], figures: parsed.figures ?? [] };
          emit();
        }
      } else {
        persist(); // first run — write the seed mirror
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

  // ── mutators ─────────────────────────────────────────────────────────────
  createProject(name: string, color?: string): Project {
    const p: Project = {
      id: uid("p"),
      name: name.trim() || "Untitled project",
      color: color ?? PROJECT_COLORS[state.projects.length % PROJECT_COLORS.length],
      createdAt: Date.now(),
    };
    setState({ ...state, projects: [p, ...state.projects] });
    queue.enqueue({
      run: () => api.post("/projects", { id: p.id, name: p.name, color: p.color }),
      onPermanentFail: () => setState({ ...state, projects: state.projects.filter((x) => x.id !== p.id) }),
    });
    return p;
  },
  renameProject(id: string, name: string) {
    setState({ ...state, projects: state.projects.map((p) => (p.id === id ? { ...p, name } : p)) });
    queue.enqueue({ coalesceKey: `proj:${id}`, run: () => api.patch(`/projects/${id}`, { name }) });
  },
  /**
   * Delete a project and everything in it, returning a snapshot of exactly what was removed so the
   * caller can offer an Undo. The DELETE is queued behind a grace window — an Undo within it cancels
   * the queued op (no data loss); after it, the cascade has landed and Undo re-creates via import.
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
    queue.enqueue({ key: `del:project:${id}`, graceMs: DELETE_GRACE_MS, run: () => api.del(`/projects/${id}`) });
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
    const id = snap.projects[0]?.id;
    if (id && queue.cancel(`del:project:${id}`)) return; // Undo within grace — the DELETE never fired
    // The delete already landed — re-create via the idempotent import upsert (datasets are restored
    // metadata-only; their S3 byte pointers are not recoverable from the FE snapshot — sub-spec §4).
    queue.enqueue({ run: () => api.post("/import/local-state", { projects: snap }) });
  },
  addDataset(projectId: string, filename: string, modality: Modality): Dataset {
    const d = ds(projectId, uid("ds"), filename, modality, Date.now());
    setState({ ...state, datasets: [...state.datasets, d] });
    queue.enqueue({
      run: () => api.post("/datasets", {
        id: d.id, project_id: projectId, filename, modality, qc: d.qc, current_sha256: d.currentSha256,
      }),
      onPermanentFail: () => setState({ ...state, datasets: state.datasets.filter((x) => x.id !== d.id) }),
    });
    return d;
  },
  /** Apply the live engine inspect result to a dataset (real modality + cleaning/QC report, plus the
   *  Slice-2 data-aware route: suggested pipeline + per-skill data-fit + table shape). Persisting
   *  routing/dataFit here is what makes the "Recommended for your data" chips survive reload. */
  updateDatasetProfile(
    id: string,
    patch: {
      modality?: Modality;
      qc?: import("./types").QcReport;
      routing?: import("./types").Dataset["routing"];
      dataFit?: import("./types").Dataset["dataFit"];
      design?: import("./types").Dataset["design"];
    },
  ) {
    setState({
      ...state,
      datasets: state.datasets.map((d) =>
        d.id === id
          ? {
              ...d,
              modality: patch.modality ?? d.modality,
              qc: patch.qc ?? d.qc,
              routing: patch.routing ?? d.routing,
              dataFit: patch.dataFit ?? d.dataFit,
              design: patch.design ?? d.design,
              // This is only ever called on a successful inspect (A2) — clear any stale
              // pending/failed flag so the dataset list / cleaning pane stop showing it.
              inspectState: undefined,
            }
          : d,
      ),
    });
    // routing/dataFit/design are LOCAL-ONLY (owner D2: persisted in the FE store, no backend column) —
    // they ride the localStorage mirror + reconcile merge-preserve, NOT the PATCH (mirrors aiProposals).
    queue.enqueue({
      coalesceKey: `ds:${id}`,
      run: () => api.patch(`/datasets/${id}`, { modality: patch.modality, qc: patch.qc }),
    });
  },
  /** Mark a live `/data/inspect` as in flight ("pending") or definitively failed ("failed") for a
   *  dataset (A2 fix) — so the dataset list card + the active cleaning pane can render an honest
   *  "Inspecting…" / "Couldn't inspect this file" instead of ever guessing at dims. Client-only: no
   *  API call, and not preserved across a server reconcile (a stuck "pending" self-heals on the next
   *  focus/hydrate rather than lying forever). Cleared by `updateDatasetProfile` on success. */
  setInspectState(id: string, inspectState: Dataset["inspectState"]) {
    setState({
      ...state,
      datasets: state.datasets.map((d) => (d.id === id ? { ...d, inspectState } : d)),
    });
  },
  /** Rename a dataset (an empty label clears the override back to the filename). */
  renameDataset(id: string, label: string) {
    const next = label.trim() || undefined;
    setState({ ...state, datasets: state.datasets.map((d) => (d.id === id ? { ...d, label: next } : d)) });
    queue.enqueue({ coalesceKey: `ds:${id}`, run: () => api.patch(`/datasets/${id}`, { label: next ?? "" }) });
  },
  /** Delete one dataset (its figures stay, just without a live data link). Returns the removed record. */
  removeDataset(id: string): Dataset | undefined {
    const d = state.datasets.find((x) => x.id === id);
    if (d) {
      setState({ ...state, datasets: state.datasets.filter((x) => x.id !== id) });
      queue.enqueue({ key: `del:dataset:${id}`, graceMs: DELETE_GRACE_MS, run: () => api.del(`/datasets/${id}`) });
    }
    return d;
  },
  /** Re-insert a deleted dataset (Undo). No-op if it's already present. */
  restoreDataset(dataset: Dataset) {
    if (state.datasets.some((d) => d.id === dataset.id)) return;
    setState({ ...state, datasets: [...state.datasets, dataset] });
    if (queue.cancel(`del:dataset:${dataset.id}`)) return;
    queue.enqueue({
      run: () => api.post("/datasets", {
        id: dataset.id, project_id: dataset.projectId, filename: dataset.filename,
        modality: dataset.modality, qc: dataset.qc, current_sha256: dataset.currentSha256,
      }),
    });
  },
  /** Mark a dataset's bytes as changed — bumps `currentSha256` so figures on the old bytes read stale. */
  markDatasetUpdated(id: string): void {
    const sha = randomSha();
    setState({
      ...state,
      datasets: state.datasets.map((d) => (d.id === id ? { ...d, currentSha256: sha } : d)),
    });
    queue.enqueue({ coalesceKey: `ds:${id}`, run: () => api.patch(`/datasets/${id}`, { current_sha256: sha }) });
  },
  installSkill(projectId: string, skillId: string) {
    if (state.installs.some((i) => i.projectId === projectId && i.skillId === skillId)) return;
    const i: SkillInstall = { id: uid("i"), projectId, skillId, installedAt: Date.now() };
    setState({ ...state, installs: [...state.installs, i] });
    queue.enqueue({
      run: () => api.post("/skill-installs", { id: i.id, skill_id: skillId, project_id: projectId }),
      onPermanentFail: () => setState({ ...state, installs: state.installs.filter((x) => x.id !== i.id) }),
    });
  },
  uninstallSkill(projectId: string, skillId: string) {
    setState({
      ...state,
      installs: state.installs.filter((i) => !(i.projectId === projectId && i.skillId === skillId)),
    });
    queue.enqueue({
      run: () => api.del(`/skill-installs?skill_id=${encodeURIComponent(skillId)}&project_id=${encodeURIComponent(projectId)}`),
    });
  },
  /** Persist a produced figure durably — full Plotly `spec`, provenance, Statistics `table`, lineage. */
  addFigure(projectId: string, fig: Omit<Figure, "id" | "projectId" | "createdAt">): Figure {
    const f: Figure = { ...fig, id: uid("f"), projectId, createdAt: Date.now() };
    setState({ ...state, figures: [...state.figures, f] });
    queue.enqueue({
      run: () => api.post("/figures", toApiFigure(f)),
      onPermanentFail: () => setState({ ...state, figures: state.figures.filter((x) => x.id !== f.id) }),
    });
    return f;
  },
  /** Persist an in-canvas edit back to the figure's stored spec (coalesced — one PATCH per burst). */
  updateFigureSpec(id: string, spec: FigureSpec) {
    setState({ ...state, figures: state.figures.map((f) => (f.id === id ? { ...f, spec } : f)) });
    queue.enqueue({ coalesceKey: `spec:${id}`, run: () => api.patch(`/figures/${id}`, { spec }) });
  },
  /** Tag a figure as frozen ("paper") or unfreeze it (Pillar 1, S3, Decision D6). */
  freezeFigure(id: string, frozen: boolean) {
    setState({ ...state, figures: state.figures.map((f) => (f.id === id ? { ...f, frozen } : f)) });
    queue.enqueue({ coalesceKey: `freeze:${id}`, run: () => api.patch(`/figures/${id}`, { frozen }) });
  },
  /** AI Helpers (S5): set a figure's AI-proposal queue. LOCAL-ONLY — proposals are a transient
   *  pre-commit editing queue (accept → stage → re-run consumes them into `provenance.actions[]`,
   *  which IS persisted). It rides the localStorage mirror AND is preserved across server reconcile
   *  by `mergeFigures` (a plain server-wins merge would drop it, since it's intentionally NOT in
   *  `toApiFigure`'s whitelist — no backend column, no PATCH round-trip), so it survives a soft
   *  reload + a window-focus reconcile. */
  setFigureProposals(id: string, aiProposals: Figure["aiProposals"]) {
    setState({ ...state, figures: state.figures.map((f) => (f.id === id ? { ...f, aiProposals } : f)) });
  },
  /** Delete one figure, returning the removed record so the caller can offer an Undo. */
  removeFigure(id: string): Figure | undefined {
    const fig = state.figures.find((f) => f.id === id);
    if (fig) {
      setState({ ...state, figures: state.figures.filter((f) => f.id !== id) });
      queue.enqueue({ key: `del:figure:${id}`, graceMs: DELETE_GRACE_MS, run: () => api.del(`/figures/${id}`) });
    }
    return fig;
  },
  /** Re-insert a deleted figure (Undo). No-op if it's already present. */
  restoreFigure(fig: Figure) {
    if (state.figures.some((f) => f.id === fig.id)) return;
    setState({ ...state, figures: [...state.figures, fig] });
    if (queue.cancel(`del:figure:${fig.id}`)) return;
    queue.enqueue({ run: () => api.post("/figures", toApiFigure(fig)) });
  },
  /** Fork a figure into a new sibling version (copies the parent, applies `patch`, links the parent). */
  forkFigure(parentId: string, patch: Partial<Omit<Figure, "id" | "projectId" | "createdAt">> = {}): Figure | null {
    const parent = state.figures.find((f) => f.id === parentId);
    if (!parent) return null;
    const f: Figure = { ...parent, ...patch, id: uid("f"), parentFigureId: parentId, frozen: false, createdAt: Date.now() };
    setState({ ...state, figures: [...state.figures, f] });
    queue.enqueue({
      run: () => api.post("/figures", toApiFigure(f)),
      onPermanentFail: () => setState({ ...state, figures: state.figures.filter((x) => x.id !== f.id) }),
    });
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

export { useSyncStatus };

// Adapters re-exported so the one-time import + workspace store (FE-2) share the mapping.
export { fromApiProject, fromApiDataset, fromApiFigure, fromApiInstall, fromApiGeneSet };
