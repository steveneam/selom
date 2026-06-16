/**
 * Version families (Pillar 1 — liveness & lineage, S3). Versions are sibling `Figure`
 * rows linked by `parentFigureId` (Decision D5 — no separate table). These pure helpers
 * resolve a figure's family (its whole lineage tree) so the compare view + the rail can
 * group, count, and nest versions. No React, no storage.
 */
import type { Figure } from "@/lib/projects/types";

/**
 * Walk `parentFigureId` to the root ancestor's id. Stops at a missing/absent parent
 * and guards against a cycle (returns the node where the cycle closes), so malformed
 * state never loops.
 */
export function rootFigureId(figId: string, byId: Map<string, Figure>): string {
  const seen = new Set<string>();
  let cur = figId;
  for (;;) {
    if (seen.has(cur)) return cur; // cycle guard
    seen.add(cur);
    const parent = byId.get(cur)?.parentFigureId;
    if (!parent || !byId.has(parent)) return cur;
    cur = parent;
  }
}

/**
 * Every figure sharing `figId`'s root ancestor (its version family), oldest → newest.
 * Includes `figId` itself. Empty when `figId` isn't among `figures`.
 */
export function versionFamily(figures: Figure[], figId: string): Figure[] {
  const byId = new Map(figures.map((f) => [f.id, f]));
  if (!byId.has(figId)) return [];
  const root = rootFigureId(figId, byId);
  return figures
    .filter((f) => rootFigureId(f.id, byId) === root)
    .sort((x, y) => x.createdAt - y.createdAt);
}

/** How many versions share `figId`'s family (1 = it's the only one). */
export function familySize(figures: Figure[], figId: string): number {
  return versionFamily(figures, figId).length;
}

export interface FamilyGroup<T> {
  /** The family's root figure (the original). */
  root: Figure;
  /** The family's members, oldest → newest, each carrying its caller item. */
  items: T[];
}

/**
 * Group a list of items by the version family of the `Figure` each one carries.
 * Used by the rail to nest sibling versions (sweeps, re-runs, forks) under their
 * original instead of a flat, ever-growing list. Items keep their input order within a
 * family (callers pass figures oldest → newest); groups are ordered by the root's
 * creation time so the reading order matches the flat list it replaces.
 */
export function groupFamilies<T>(items: T[], getFigure: (t: T) => Figure): FamilyGroup<T>[] {
  const figures = items.map(getFigure);
  const byId = new Map(figures.map((f) => [f.id, f]));
  const order: string[] = [];
  const buckets = new Map<string, T[]>();
  for (const it of items) {
    const root = rootFigureId(getFigure(it).id, byId);
    let bucket = buckets.get(root);
    if (!bucket) {
      bucket = [];
      buckets.set(root, bucket);
      order.push(root);
    }
    bucket.push(it);
  }
  const groups = order.map((rootId): FamilyGroup<T> => {
    const items = buckets.get(rootId)!;
    // Prefer the actual root figure if it's in the list; else the earliest member.
    const rootItem = items.find((it) => getFigure(it).id === rootId) ?? items[0];
    return { root: getFigure(rootItem), items };
  });
  groups.sort((p, q) => p.root.createdAt - q.root.createdAt);
  return groups;
}
