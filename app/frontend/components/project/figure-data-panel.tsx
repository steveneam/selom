"use client";

import * as React from "react";
import { RefreshCw, SlidersHorizontal } from "lucide-react";
import { ParamControl } from "./param-control";
import { DataCheckPanel } from "./data-check";
import { DataFitVerdict } from "@/components/reproduction/data-fit-panel";
import { Button } from "@/components/ui/button";
import { skillParamSchema, visibleParamFields } from "@/lib/catalog/params";
import type { SkillParams } from "@/lib/skills-api";
import type { Figure } from "@/lib/projects/types";

/**
 * The "Figure data" stage (figure-editor-contract spec §3.6) — the pipeline box between
 * Statistics and Figure. It surfaces the data BEHIND the active figure: the inputs that
 * produced it (the skill's declarative `param_spec`, prefilled from the run's params) so
 * they can be tuned and re-run into a new version, plus the data-check routing and
 * data-fit verdict (relocated off the artboard so the figure view stays figure-forward).
 *
 * Cosmetic edits stay on the artboard (JSON-Patch, instant); changing an INPUT here is a
 * backend re-run — versioned and provenance-stamped, the original kept.
 */
export function FigureDataPanel({
  skillId,
  skillName,
  baseParams,
  running,
  dataCheck,
  dataFit,
  onRerun,
  onPickSkill,
  onPickManually,
}: {
  skillId: string;
  skillName: string;
  /** The figure's run params — what the controls prefill from. */
  baseParams: SkillParams;
  running: boolean;
  dataCheck?: Figure["dataCheck"];
  dataFit?: Figure["dataFit"];
  /** Re-run the skill with the edited inputs → a new figure version. */
  onRerun: (params: SkillParams) => void;
  /** From the data-check routing card: set up a suggested skill in the workbench. */
  onPickSkill: (skillId: string) => void;
  /** From the data-check routing card: take over and pick a skill manually. */
  onPickManually: () => void;
}) {
  const schema = React.useMemo(() => skillParamSchema(skillId), [skillId]);
  const [params, setParams] = React.useState<SkillParams>(() => ({ ...baseParams }));
  // Did the user change anything from the figure's current inputs?
  const dirty = React.useMemo(
    () => schema.some((f) => params[f.key] !== baseParams[f.key]),
    [schema, params, baseParams],
  );

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div>
        <h2 className="flex items-center gap-2 text-base font-semibold tracking-tight text-foreground">
          <SlidersHorizontal className="size-4 text-stage-figure" />
          Figure data
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          The inputs behind <span className="text-foreground">{skillName}</span>. Tune them and
          re-run to make a new version — the current figure is kept.
        </p>
      </div>

      {/* The data behind the figure: routing verdict + data-fit (relocated off the artboard). */}
      {dataCheck && (
        <DataCheckPanel dataCheck={dataCheck} onPickSkill={onPickSkill} onPickManually={onPickManually} />
      )}
      {dataFit && <DataFitVerdict fit={dataFit} skillName={skillName} />}

      {/* Inputs → re-run. */}
      <div className="rounded-xl border border-border bg-card/60 p-4">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Inputs</p>
        {schema.length === 0 ? (
          <p className="mt-2 text-xs text-muted-foreground">
            This skill runs with fixed defaults — there are no adjustable inputs to re-run.
          </p>
        ) : (
          <>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {visibleParamFields(schema, params).map((f) => (
                <ParamControl
                  key={f.key}
                  field={f}
                  value={params[f.key]}
                  onChange={(v) => setParams((p) => ({ ...p, [f.key]: v }))}
                />
              ))}
            </div>
            <div className="mt-4 flex items-center justify-between gap-3">
              <span className="text-[11px] text-muted-foreground">
                {dirty ? "Re-runs the analysis → a new linked version." : "Adjust an input to re-run."}
              </span>
              <Button size="sm" disabled={running || !dirty} onClick={() => onRerun(params)}>
                <RefreshCw /> {running ? "Re-running…" : "Re-run → new version"}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
