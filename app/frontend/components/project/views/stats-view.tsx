"use client";

import * as React from "react";
import { Paintbrush, Table2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PaneBoundary } from "@/components/ui/error-boundary";
import { StatsPanel, type StatsLabeling } from "../stats-panel";
import { EmptyState } from "./empty-state";
import { getSkill } from "@/lib/catalog/seed";
import type { Figure } from "@/lib/projects/types";

/**
 * The Statistics view (`view === "stats"`): the focused figure's stored table (or a spec-derived
 * fallback) with the gene-label column when the figure is a volcano. Presentational — the table +
 * labeling are derived in the composition root.
 */
export function StatsView({
  activeFigure,
  table,
  labeling,
  onOpenFigure,
  onRunSkill,
}: {
  activeFigure: Figure | undefined;
  table: React.ComponentProps<typeof StatsPanel>["table"] | undefined;
  labeling: StatsLabeling | undefined;
  onOpenFigure: (f: Figure) => void;
  onRunSkill: () => void;
}) {
  if (!(activeFigure && table)) {
    return (
      <EmptyState
        title="No statistics selected"
        body="Pick a Statistics node in the rail, or run a skill that computes a table (DEG, enrichment, markers)."
        action="Run a skill"
        onAction={onRunSkill}
      />
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-base font-semibold tracking-tight text-foreground">
            <Table2 className="size-4 text-stage-publish" />
            {table.title ?? "Statistics"}
          </h2>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            from <span className="text-foreground">{activeFigure.title}</span> ·{" "}
            {getSkill(activeFigure.skillId ?? "")?.name ?? "skill"}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => onOpenFigure(activeFigure)}>
          <Paintbrush /> Open figure
        </Button>
      </div>
      <PaneBoundary label="stats" title="This table couldn't be shown" resetKeys={[activeFigure.id]}>
        <StatsPanel table={table} defaultOpen labeling={labeling} />
      </PaneBoundary>
    </div>
  );
}
