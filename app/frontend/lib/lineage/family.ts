/**
 * Dataset "families" (Pillar 1 — GraphPad-Prism-style lineage). Every dataset gets a
 * stable family accent colour; its derived Statistics and Figures carry that colour +
 * the dataset's (live) name as a source chip, so the rail reads "which output came from
 * which data" at a glance — and renaming the dataset propagates to the whole family for
 * free (the chip reads the dataset's current name, it isn't copied onto each output).
 */

import type { Dataset } from "@/lib/projects/types";

/** Qualitative accent palette for families — assigned by dataset order within a project. */
export const FAMILY_PALETTE = [
  "#60a5fa", // blue
  "#f472b6", // pink
  "#34d399", // green
  "#fbbf24", // amber
  "#a78bfa", // violet
  "#22d3ee", // cyan
  "#fb7185", // rose
  "#a3e635", // lime
];

/** Map each dataset id → its family colour (distinct for the first 8 in a project). */
export function familyColorMap(datasets: Pick<Dataset, "id">[]): Map<string, string> {
  const m = new Map<string, string>();
  datasets.forEach((d, i) => m.set(d.id, FAMILY_PALETTE[i % FAMILY_PALETTE.length]));
  return m;
}

/** The dataset's display name — a user-set label if present, else the filename. */
export function datasetDisplayName(d: Pick<Dataset, "label" | "filename">): string {
  return d.label?.trim() || d.filename;
}

/** A compact name for a family chip (label as-is, or the filename minus extension), truncated. */
export function datasetChipName(d: Pick<Dataset, "label" | "filename">): string {
  const raw = d.label?.trim() || d.filename.replace(/\.[^.]+$/, "");
  return raw.length > 16 ? `${raw.slice(0, 15)}…` : raw;
}
