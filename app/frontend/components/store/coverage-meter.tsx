"use client";

import { useCatalog } from "@/lib/catalog/registry";
import { CATALOG_TOTAL_ESTIMATE } from "@/lib/catalog/seed";

/**
 * Honest coverage meter (design §6.4), now registry-driven: "runnable" is the live
 * Verified count from `GET /skills`, not a seed constant. Total stays an estimate of
 * the full browsable catalog. Browsable ≠ runnable, shown honestly.
 */
export function CoverageMeter() {
  const { catalog } = useCatalog();
  const runnable = catalog.filter((s) => s.tier === "verified").length;
  const pct = Math.round((runnable / CATALOG_TOTAL_ESTIMATE) * 100);

  return (
    <div className="w-56 shrink-0 rounded-lg border border-border bg-card/50 p-3">
      <div className="flex items-baseline justify-between">
        <span className="tabular text-sm font-semibold text-foreground">
          {runnable}
          <span className="text-muted-foreground"> / ~{CATALOG_TOTAL_ESTIMATE}</span>
        </span>
        <span className="text-[10px] font-medium uppercase tracking-wider text-primary/80">
          runnable
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(2, pct)}%` }} />
      </div>
      <p className="mt-1.5 text-[11px] leading-snug text-muted-foreground">
        Coverage grows via the Skill Foundry — browsable ≠ runnable, shown honestly.
      </p>
    </div>
  );
}
