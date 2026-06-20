"use client";

import * as React from "react";

/**
 * Session File cache for the live-reproduction drive (live-reproduction-spec §7, invariant I5).
 *
 * The drive needs the actual PDF + supplement *bytes*, but the Workspace Library persists only
 * metadata — no bytes, no object URLs (spec I5: localStorage can't hold File contents). So the
 * dropped `File` objects live HERE, in module memory, keyed by the saved paper id: the main PDF is
 * captured at the Skill-Match → Reproduce handoff, and supplements as they're dropped on the
 * Reproduce stage. This is deliberately NON-persistent — a reload clears it, and the Reproduce stage
 * then honestly re-prompts to re-attach (the bytes genuinely can't survive a reload). The same dedup
 * key as `workspaceStore.addPaperSupplements` (lowercased filename) so a re-drop restores the bytes
 * for the matching metadata row.
 */

interface Entry {
  main?: File;
  supplements: Map<string, File>; // keyed by lowercased filename
}

const files = new Map<string, Entry>();
const listeners = new Set<() => void>();

function entry(paperId: string): Entry {
  let e = files.get(paperId);
  if (!e) {
    e = { supplements: new Map() };
    files.set(paperId, e);
  }
  return e;
}

function emit() {
  for (const l of listeners) l();
}

export const paperFiles = {
  setMain(paperId: string, file: File) {
    entry(paperId).main = file;
    emit();
  },
  getMain(paperId: string): File | undefined {
    return files.get(paperId)?.main;
  },
  addSupplements(paperId: string, list: File[]) {
    if (list.length === 0) return;
    const e = entry(paperId);
    for (const f of list) e.supplements.set(f.name.toLowerCase(), f);
    emit();
  },
  removeSupplement(paperId: string, filename: string) {
    if (files.get(paperId)?.supplements.delete(filename.toLowerCase())) emit();
  },
  /** The supplement File bytes attached this session (the upload payload). */
  getSupplementFiles(paperId: string): File[] {
    return [...(files.get(paperId)?.supplements.values() ?? [])];
  },
  subscribe(cb: () => void): () => void {
    listeners.add(cb);
    return () => listeners.delete(cb);
  },
};

/** The reactive, render-safe view of a paper's session files. */
export interface PaperFilesView {
  hasMain: boolean;
  mainName: string | null;
  /** Lowercased filenames of supplements whose bytes are present THIS session. */
  attached: Set<string>;
  supplementCount: number;
}

const EMPTY_VIEW: PaperFilesView = {
  hasMain: false,
  mainName: null,
  attached: new Set(),
  supplementCount: 0,
};

// Cache a stable snapshot per paper so useSyncExternalStore sees a constant identity until the
// paper's files actually change (otherwise it would loop on a fresh object every render).
const viewCache = new Map<string, { view: PaperFilesView; sig: string }>();

function snapshot(paperId: string): PaperFilesView {
  const e = files.get(paperId);
  const main = e?.main;
  const names = e ? [...e.supplements.keys()].sort() : [];
  const sig = `${main ? `${main.name}:${main.size}` : ""}|${names.join(",")}`;
  if (sig === "|") return EMPTY_VIEW;
  const cached = viewCache.get(paperId);
  if (cached && cached.sig === sig) return cached.view;
  const view: PaperFilesView = {
    hasMain: !!main,
    mainName: main?.name ?? null,
    attached: new Set(names),
    supplementCount: names.length,
  };
  viewCache.set(paperId, { view, sig });
  return view;
}

/** Subscribe a component to one paper's session files (bytes presence drives the run readiness UI). */
export function usePaperFiles(paperId: string): PaperFilesView {
  return React.useSyncExternalStore(
    paperFiles.subscribe,
    () => snapshot(paperId),
    () => EMPTY_VIEW,
  );
}
