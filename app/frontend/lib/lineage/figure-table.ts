import { deriveTable } from "./derive-table";
import type { Figure } from "@/lib/projects/types";
import type { StatsTable } from "@/lib/skills/api";
import { asTables } from "@/lib/skills/stats-tables";

/**
 * The Statistics tables for a figure (Pillar 1): its stored backend `table`(s), or a single
 * fallback derived from the figure's spec (Decision D3). `[]` → no substantive table → no
 * Statistics node / nothing to diff in compare.
 *
 * Returns an array because a run may carry several (docs/stats-tables/spec.md D1). Callers that
 * genuinely want one — the caption, the gene-label column — take `[0]` and say why.
 */
export function figureTables(fig: Figure): StatsTable[] {
  const stored = asTables(fig.table);
  if (stored.length > 0) return stored;
  return fig.spec ? asTables(deriveTable(fig.spec)) : [];
}
