import * as React from "react";

import { ATTRIBUTION_META, tierLabel } from "@/lib/reproduction/api";
import type { Attribution } from "@/lib/reproduction/types";
import { cn } from "@/lib/cn";

/**
 * Shared atoms for the Reproduction view. The tier/verdict palette is dynamic hex from the
 * backend (TIER_COLORS), so we tint inline via color-mix rather than Tailwind classes —
 * matching the Badge component's color-mix aesthetic. Color is never the only signal: every
 * tile pairs its hue with the numeric score, a label, and/or an attribution glyph.
 */

/** A translucent fill + readable border/text from one accent hex (the Badge house style). */
export function tint(hex: string): React.CSSProperties {
  return {
    backgroundColor: `color-mix(in oklab, ${hex} 14%, transparent)`,
    borderColor: `color-mix(in oklab, ${hex} 42%, transparent)`,
    color: `color-mix(in oklab, ${hex} 80%, white)`,
  };
}

const chipBase =
  "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider whitespace-nowrap";

/** The named reproducibility tier, in its heatmap color. */
export function TierChip({ tier, color }: { tier: string; color: string }) {
  return (
    <span className={chipBase} style={tint(color)}>
      {tierLabel(tier)}
    </span>
  );
}

/** Who a residual is on — ✓ Selom / ⚙ engine / 📄 paper / 🗄 data, with a hover label. */
export function AttributionChip({
  attribution,
  icon,
  showLabel = false,
}: {
  attribution: Attribution;
  icon?: string;
  showLabel?: boolean;
}) {
  const meta = ATTRIBUTION_META[attribution] ?? { icon: icon ?? "·", label: attribution };
  return (
    <span
      className={cn(chipBase, "border-border bg-muted text-muted-foreground")}
      title={meta.label}
    >
      <span aria-hidden className="text-xs leading-none">
        {icon ?? meta.icon}
      </span>
      {showLabel && <span className="normal-case">{meta.label}</span>}
    </span>
  );
}

/** The source-provenance badge (e.g. `ST6+ Fig4e−`) — neutral, never accusatory (D14). */
export function ProvenanceBadge({ provenance }: { provenance: string }) {
  if (!provenance) return null;
  return (
    <span
      className="tabular rounded border border-border bg-background/60 px-1.5 py-0.5 text-[10px] text-muted-foreground"
      title="Source provenance — which deposit this panel reproduces (+) vs diverges from (−)"
    >
      {provenance}
    </span>
  );
}

const VERDICT_COLOR: Record<string, string> = {
  exact: "#22c55e",
  close: "#f59e0b",
  fail: "#f97316",
};

/** A golden-vs-computed verdict: exact / close / fail. */
export function VerdictChip({ verdict }: { verdict: string }) {
  const color = VERDICT_COLOR[verdict] ?? "#9ca3af";
  return (
    <span className={chipBase} style={tint(color)}>
      {verdict}
    </span>
  );
}

/** The blame label — why a number missed (paper-irreproducible / structural-limit / …). */
export function BlameChip({ blame }: { blame: string | null }) {
  if (!blame) return null;
  return (
    <span
      className={cn(chipBase, "border-border bg-muted text-muted-foreground normal-case")}
      title="Blame — where a residual originates (never a default accusation of the paper)"
    >
      {blame}
    </span>
  );
}
