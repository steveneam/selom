import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { stalenessLabel, type StalenessResult } from "@/lib/lineage/staleness";

/**
 * Non-blocking "stale" chip for a figure (Pillar 1 — liveness & lineage). Renders
 * nothing when the figure is up to date. The tooltip names exactly what diverged so
 * the staleness is explainable, not just a warning light. Reused on the figure
 * header now and on the workrail nodes in S2.
 */
export function StaleBadge({ result, className }: { result: StalenessResult; className?: string }) {
  if (!result.stale) return null;
  const detail = result.reasons
    .filter((r) => r.factor !== "env")
    .map((r) => `${r.factor}: ${r.was} → ${r.now}`)
    .join(" · ");
  return (
    <Badge variant="warn" className={className} title={detail} data-testid="stale-badge">
      <AlertTriangle className="size-3" /> {stalenessLabel(result)}
    </Badge>
  );
}
