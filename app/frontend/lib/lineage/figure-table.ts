import { deriveTable } from "./derive-table";
import type { Figure } from "@/lib/projects/types";
import type { StatsTable } from "@/lib/skills/api";

/**
 * The Statistics table for a figure (Pillar 1): its stored backend `table`, or a
 * fallback derived from the figure's spec (Decision D3). `undefined` → no substantive
 * table → no Statistics node / nothing to diff in compare.
 */
export function figureTable(fig: Figure): StatsTable | undefined {
  return fig.table ?? (fig.spec ? (deriveTable(fig.spec) ?? undefined) : undefined);
}
