"use client";

import * as React from "react";
import { Paintbrush, Table2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PaneBoundary } from "@/components/ui/error-boundary";
import { AskAi } from "@/components/ai/ask-ai";
import { explain } from "@/lib/ai/api";
import { StatsPanel, type StatsLabeling } from "../stats-panel";
import { EmptyState } from "./empty-state";
import { getSkill } from "@/lib/catalog/seed";
import type { Figure } from "@/lib/projects/types";

/**
 * The Statistics view (`view === "stats"`): the focused figure's stored table(s) (or a spec-derived
 * fallback) with the gene-label column when the figure is a volcano. Presentational — the tables +
 * labeling are derived in the composition root.
 *
 * **N tables STACK; they are never tabbed** (docs/stats-tables/spec.md D2). The deciding fact is
 * what one of them is: a pairwise p-value table is not an alternative view of the ranked values, it
 * is the **provenance of marks already drawn on the figure**. Stars on the canvas with their
 * p-values behind an unselected tab repeats the exact failure the one-table trade existed to avoid.
 * Tabs would also silently scope the per-panel CSV export, the compare diff and find-in-page to
 * whichever tab is active.
 */
/** Panels open by default. A wall-guard, not a preference — no skill in D4 wants more than two. */
const MAX_OPEN = 3;

export function StatsView({
  activeFigure,
  tables,
  labeling,
  onOpenFigure,
  onRunSkill,
}: {
  activeFigure: Figure | undefined;
  /** Every table this run computed, in the runner's array order (D4 — order is the only authority). */
  tables: React.ComponentProps<typeof StatsPanel>["table"][];
  labeling: StatsLabeling | undefined;
  onOpenFigure: (f: Figure) => void;
  onRunSkill: () => void;
}) {
  const table = tables[0];
  // Grade advisory (Layer A Phase 3): the Statistics stage is advisory-only (spine invariant #4).
  // Ground the explain on the figure's actual method — its skill + the deg `mode` param — so the
  // advice names the real test the runner used (DETECTED == EXPLAINED). Deterministic-primary: the
  // gateway-off answer is a grounded card (ai.grade), never a black box.
  const skillId = activeFigure?.skillId;
  const runtimeSkillId = skillId?.replace(/^selom\./, "");
  const mode = activeFigure?.provenance?.params?.mode;
  const askGradeAdvice = React.useCallback(
    async (goal: string) => {
      if (!runtimeSkillId) return null;
      return explain({
        request: "grade_advice",
        stage: "grade",
        skill_id: runtimeSkillId,
        goal,
        stats: { skill_id: runtimeSkillId, ...(mode != null ? { mode: String(mode) } : {}) },
      });
    },
    [runtimeSkillId, mode],
  );

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
            {/*
              One table lends the heading its title, exactly as before (G3). With several, the
              heading goes generic and each keeps its own title on its own panel — and there is
              deliberately NO "N tables" count. Mobbin: eight mature multi-section report surfaces
              and not one heads the group with a count of its sections. Laravel Cloud
              (mobbin.com/screens/32d12b37-22cd-4a53-981e-e338101609ce) titles each section and lets
              the stack speak; Braintrust (…/5cdf1141-8f00-4e7d-b5f4-729ea894a29a) does show counts,
              but per-section on its own header, describing ROWS — which StatsPanel already does. A
              count here would tell the reader how many boxes sit below boxes they can already see.
            */}
            {tables.length === 1 ? (table.title ?? "Statistics") : "Statistics"}
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
        <div className="flex flex-col gap-3">
          {tables.map((t, i) => (
            <StatsPanel
              key={i}
              table={t}
              // EVERY table is open, up to the wall-guard. Collapsing tables 2..N was an earlier
              // draft and is wrong for the same reason tabs are: a collapsed panel and an
              // unselected tab hide the same numbers, and the p-values must be visible in the same
              // glance as the stars they explain. Affordable because the panel body is already
              // height-capped (max-h-[300px]) and its rows capped at 200.
              defaultOpen={i < MAX_OPEN}
              // Labelling is a COLUMN INDEX, so it is meaningful against exactly one table — the
              // first (spec §Gene labelling). volcano and deg, the only figures with geneLabels,
              // emit one table each, so this states the answer rather than changing today's.
              labeling={i === 0 ? labeling : undefined}
            />
          ))}
        </div>
      </PaneBoundary>
      {/* Advisory-only (propose-never-auto): explain which test this figure uses + what it assumes. */}
      <AskAi
        stage="grade"
        mode="advisory"
        label="Ask about this statistic"
        placeholder="e.g. which test is this, and what does it assume?"
        context={{ skillId, params: activeFigure.provenance?.params }}
        onExplain={askGradeAdvice}
      />
    </div>
  );
}
