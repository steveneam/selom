"use client";

import * as React from "react";
import { RefreshCw, SlidersHorizontal } from "lucide-react";
import { ParamControl } from "./param-control";
import { MarksEditor } from "./marks-editor";
import { DataCheckPanel } from "./data-check";
import { DataFitVerdict } from "@/components/reproduction/data-fit-panel";
import { Button } from "@/components/ui/button";
import { visibleParamFields } from "@/lib/catalog/params";
import { useSkillParams } from "@/lib/catalog/use-skill-params";
import type { SkillParams } from "@/lib/skills-api";
import type { SeededMark } from "@/lib/erg/marks";
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
  seededMarks = [],
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
  /** Skill-seeded ERG landmark marks (meta.selom.marks) — drives the Marks editor when present. */
  seededMarks?: SeededMark[];
  /** Re-run the skill with the edited inputs → a new figure version. */
  onRerun: (params: SkillParams) => void;
  /** From the data-check routing card: set up a suggested skill in the workbench. */
  onPickSkill: (skillId: string) => void;
  /** From the data-check routing card: take over and pick a skill manually. */
  onPickManually: () => void;
}) {
  const { fields: schema, loading } = useSkillParams(skillId);
  const [params, setParams] = React.useState<SkillParams>(() => ({ ...baseParams }));
  // Did the user change anything from the figure's current inputs? Compared over the union of keys
  // (not just `schema`) so an edit to a non-overlay param — manual_marks / marks from the Marks
  // editor — also enables the re-run.
  const dirty = React.useMemo(() => {
    const keys = new Set([...Object.keys(baseParams), ...Object.keys(params)]);
    return [...keys].some((k) => params[k] !== baseParams[k]);
  }, [params, baseParams]);

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

      {/* ERG landmark marks (erg-manual-marks): set/confirm a/b (or N1/P1) times, then re-run. */}
      {seededMarks.length > 0 && (
        <MarksEditor seededMarks={seededMarks} params={params} onParamsChange={setParams} />
      )}

      {/* Inputs → re-run. */}
      <div className="rounded-xl border border-border bg-card/60 p-4">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Inputs</p>
        {loading ? (
          <p className="mt-2 text-xs text-muted-foreground">Loading inputs…</p>
        ) : schema.length === 0 ? (
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
