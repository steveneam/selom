"use client";

import * as React from "react";
import { GitBranch, GitCompare, Lock, LockOpen, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { SweepForm } from "./sweep-form";
import type { SkillParams } from "@/lib/skills-api";
import type { ParamValue } from "@/lib/lineage/diff";
import type { Figure } from "@/lib/projects/types";

/**
 * Version bar (Pillar 1, S3) — the lineage + versioning controls for the open figure.
 * Shows where this figure sits in its version family and offers the three version
 * actions: **Sweep** (fork N siblings over a parameter), **Compare** (side-by-side +
 * diff, when the family has ≥2 versions), and **Freeze** (tag as the paper version).
 * Sweep expands inline below the bar (progressive disclosure, not a modal).
 */
export function VersionBar({
  figure,
  familyCount,
  running,
  skillId,
  baseParams,
  onSweep,
  onCompare,
  onToggleFreeze,
}: {
  figure: Figure;
  /** How many versions are in this figure's family (≥2 → Compare is available). */
  familyCount: number;
  running: boolean;
  skillId?: string;
  baseParams: SkillParams;
  onSweep: (param: string, values: ParamValue[]) => void;
  onCompare: () => void;
  onToggleFreeze: () => void;
}) {
  const [sweepOpen, setSweepOpen] = React.useState(false);
  const frozen = !!figure.frozen;
  const label = figure.variantLabel ?? (figure.parentFigureId ? "Variant" : "Original");

  function runSweep(param: string, values: ParamValue[]) {
    setSweepOpen(false);
    onSweep(param, values);
  }

  return (
    <div className="rounded-xl border border-border bg-card/50">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
        <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <GitBranch className="size-3.5 text-stage-figure" />
          <span className="font-medium text-foreground">{label}</span>
          {familyCount > 1 && (
            <span className="tabular text-muted-foreground">· 1 of {familyCount}</span>
          )}
        </span>

        {frozen && (
          <span className="inline-flex items-center gap-1 rounded-full border border-stage-figure/40 bg-stage-figure/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-stage-figure">
            <Lock className="size-3" /> Frozen · paper
          </span>
        )}

        <div className="ml-auto flex items-center gap-1.5">
          <Button
            variant={sweepOpen ? "secondary" : "ghost"}
            size="sm"
            className="h-7"
            onClick={() => setSweepOpen((v) => !v)}
            disabled={!skillId}
            title={skillId ? "Sweep a parameter into linked versions" : "Re-run the skill to enable sweeps"}
          >
            <SlidersHorizontal /> Sweep
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7"
            onClick={onCompare}
            disabled={familyCount < 2}
            title={familyCount < 2 ? "Make another version to compare" : "Compare this figure's versions"}
          >
            <GitCompare /> Compare{familyCount >= 2 ? ` ${familyCount}` : ""}
          </Button>
          <Button
            variant={frozen ? "secondary" : "ghost"}
            size="sm"
            className={cn("h-7", frozen && "text-stage-figure")}
            onClick={onToggleFreeze}
            title={frozen ? "Unfreeze — make this version editable again" : "Freeze — tag this as the paper version"}
          >
            {frozen ? <Lock /> : <LockOpen />} {frozen ? "Frozen" : "Freeze"}
          </Button>
        </div>
      </div>

      {sweepOpen && skillId && (
        <div className="border-t border-border p-3">
          <SweepForm
            skillId={skillId}
            baseParams={baseParams}
            running={running}
            onRun={runSweep}
            onCancel={() => setSweepOpen(false)}
          />
        </div>
      )}
    </div>
  );
}
