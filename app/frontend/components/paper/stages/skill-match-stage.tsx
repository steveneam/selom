"use client";

import * as React from "react";
import Link from "next/link";

import { useCatalog } from "@/lib/catalog/registry";
import { skillColor } from "@/lib/catalog/modality";
import type { SkillCatalogEntry } from "@/lib/catalog/types";
import { oosLabel } from "@/lib/skill-match/api";
import type { SavedPaper } from "@/lib/workspace/types";

/**
 * The Skill-Match stage body in the Paper shell — the compact routed inventory the Library keeps for a
 * saved paper (D3: the L3 skill inventory + per-figure tier rollup, not the full FeasibilityMap). For
 * the exact per-figure breakdown + the inline PDF viewer you re-drop the paper in Skill Match. Lifted
 * verbatim from the former `SavedSkillMatch` (its chrome now lives in `PaperShell`).
 */
export function SkillMatchStage({ paper }: { paper: SavedPaper }) {
  const { catalog } = useCatalog();
  const bySlug = React.useMemo(() => {
    const m = new Map<string | undefined, SkillCatalogEntry>();
    for (const e of catalog) m.set(e.id.split(".").pop(), e);
    return m;
  }, [catalog]);
  const installed = React.useMemo(
    () => new Set(catalog.filter((e) => e.tier === "verified").map((e) => e.id.split(".").pop())),
    [catalog],
  );
  const tier = paper.tierSummary;

  return (
    <section>
      <div>
        <h2 className="text-lg font-semibold text-foreground">Skills this paper needs</h2>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          The paper-level inventory Skill Match routed — {paper.skills.length} skill
          {paper.skills.length === 1 ? "" : "s"} across {paper.figureCount} figure
          {paper.figureCount === 1 ? "" : "s"}
          {tier.structured + tier.recovered > 0
            ? ` · ${tier.structured} routed cleanly, ${tier.recovered} via the recovery sweep`
            : ""}
          .
        </p>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {paper.skills.map((slug) => {
          const entry = bySlug.get(slug);
          const color = entry ? skillColor(entry) : "#64748b";
          const isInstalled = installed.has(slug);
          return (
            <span
              key={slug}
              className="inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium"
              style={{
                backgroundColor: `color-mix(in oklab, ${color} 12%, transparent)`,
                borderColor: `color-mix(in oklab, ${color} 38%, transparent)`,
                color: `color-mix(in oklab, ${color} 82%, white)`,
              }}
              title={isInstalled ? "Installed — runs in your account" : "Available in the Skill Store"}
            >
              <span
                aria-hidden
                className="size-1.5 rounded-full"
                style={{ backgroundColor: color, opacity: isInstalled ? 1 : 0.4 }}
              />
              {entry?.name ?? slug}
            </span>
          );
        })}
      </div>

      {paper.outOfScope.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-muted-foreground">Out of scope:</span>
          {paper.outOfScope.map((r) => (
            <span
              key={r}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              {oosLabel(r)}
            </span>
          ))}
        </div>
      )}

      <p className="mt-8 text-xs text-muted-foreground">
        This is the saved match summary. For the per-figure breakdown and the inline PDF viewer,{" "}
        <Link href="/skill-match" className="text-primary hover:underline">
          drop the paper again in Skill Match
        </Link>
        .
      </p>
    </section>
  );
}
