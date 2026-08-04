"use client";

import * as React from "react";
import { RefreshCw, RotateCcw, SlidersHorizontal } from "lucide-react";
import { cn } from "@/lib/ui/cn";
import { ParamControl } from "./param-control";
import { MarksEditor, MARKS_PARAM_KEYS } from "./marks-editor";
import { ThresholdEditor, THRESHOLD_PARAM_KEYS } from "./threshold-editor";
import { DataCheckPanel } from "./data-check";
import { DataFitVerdict } from "@/components/reproduction/data-fit-panel";
import { Button } from "@/components/ui/button";
import { PaneShell } from "@/components/ui/pane-shell";
import { AiMarker } from "@/components/ai/ai-marker";
import { isFieldDisabled, visibleParamFields, type ParamDataContext, type ParamField } from "@/lib/catalog/params";
import { useSkillParams, type ParamSpecSeed } from "@/lib/catalog/use-skill-params";
import { authorOf, authorOfKeys } from "@/lib/ai/proposals";
import { changedRingClass } from "@/lib/ui/changed-ring";
import type { PaneState } from "@/lib/ui/pane-state";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { SkillParams } from "@/lib/skills/api";
import type { SeededMark } from "@/lib/erg/marks";
import type { AiProposal } from "@/lib/ai/types";
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
  params,
  onParamsChange,
  running,
  dataCheck,
  dataFit,
  paramContext = null,
  seededMarks = [],
  canEditMarks = false,
  canEditThresholds = false,
  figureSpec,
  specSeed = null,
  markLabelsShown = true,
  onMarkLabelsShownChange,
  proposals = [],
  onRevertProposal,
  onReset,
  onRerun,
  onPickSkill,
  onPickManually,
}: {
  skillId: string;
  skillName: string;
  /** The figure's run params (what the figure was last run with) — the baseline for "dirty". */
  baseParams: SkillParams;
  /** The STAGED params (controlled, owned by the parent so a dot drag + this panel share one source). */
  params: SkillParams;
  onParamsChange: React.Dispatch<React.SetStateAction<SkillParams>>;
  running: boolean;
  dataCheck?: Figure["dataCheck"];
  dataFit?: Figure["dataFit"];
  /** The SOURCE dataset's schema (columns + categorical levels), so a column input is picked from
   *  what the data has rather than typed. Optional + fail-soft: absent → the plain text fields. */
  paramContext?: ParamDataContext | null;
  /** Skill-seeded ERG landmark marks (meta.selom.marks) — the rows the Marks editor renders. */
  seededMarks?: SeededMark[];
  /** Whether this figure declares the landmarkMarks capability (docs/figure-data-capabilities/spec.md
   *  §4) — the gate for the Marks editor. True for ERG trace/flicker figures even before dots are
   *  drawn, so the operator can turn the dots on and adjust a/b (N1/P1) times. */
  canEditMarks?: boolean;
  /** Whether this figure declares the thresholds capability (generalization-spec §F) — the gate for
   *  the volcano FC/p-value threshold editor. */
  canEditThresholds?: boolean;
  /** The active figure spec — supplies the volcano points for the threshold editor's live count. */
  figureSpec?: FigureSpec | null;
  /** C5: the figure's own provenance `param_spec` (+ its version) — when present the Inputs render
   *  from it instantly with no describe round-trip, and stay tunable offline (re-run still needs the
   *  backend). Absent it, the spec is fetched (with a local-cache seed/fallback). */
  specSeed?: ParamSpecSeed | null;
  /** Live state of the "show a/b labels" toggle — drives an instant client-side restyle of the
   *  preview (the parent owns it so the preview can react without a re-run). */
  markLabelsShown?: boolean;
  onMarkLabelsShownChange?: (shown: boolean) => void;
  /** AI Helpers (S5): the figure's proposal queue — a control whose staged value is currently an
   *  accepted AI proposal's value gets a ✨ (filled) attribution marker with click-to-revert. */
  proposals?: AiProposal[];
  onRevertProposal?: (id: string) => void;
  /** Discard all staged input changes back to this figure's current run values (and un-stage any
   *  accepted AI proposals). Shown as "Reset" when there's something to discard. */
  onReset?: () => void;
  /** Re-run the skill with the edited inputs → a new figure version. */
  onRerun: (params: SkillParams) => void;
  /** From the data-check routing card: set up a suggested skill in the workbench. */
  onPickSkill: (skillId: string) => void;
  /** From the data-check routing card: take over and pick a skill manually. */
  onPickManually: () => void;
}) {
  const { fields: schema, status: paramsStatus, retry: retryParams } = useSkillParams(skillId, specSeed, paramContext);
  // Params are CONTROLLED by the parent (so a dot drag and this panel write the same staged params).
  const setParams = onParamsChange;
  // The Inputs pane as a stable PaneState (Task B3): loading → skeleton (not a vanished pane); a
  // failed/timed-out param-spec fetch → an error + Retry (not an infinite spinner); a successful
  // fetch with no tunable knobs → an explicit "fixed defaults" empty note; else the controls.
  const inputsState: PaneState<ParamField[]> = React.useMemo(() => {
    switch (paramsStatus) {
      case "idle":
      case "loading":
        return { status: "loading", label: "Loading inputs…" };
      case "error":
        return {
          status: "error",
          message: "Couldn’t load this skill’s inputs (the backend didn’t respond).",
          retry: retryParams,
        };
      case "empty":
        return {
          status: "empty",
          message: "This skill runs with fixed defaults — there are no adjustable inputs to re-run.",
        };
      default:
        return { status: "ready", data: schema };
    }
  }, [paramsStatus, schema, retryParams]);
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
          <SlidersHorizontal className="size-4 text-stage-figuredata" />
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

      {/* ERG landmark marks (figure-data-capabilities §4) — gated on the declared landmarkMarks
          capability, not on dots being drawn, so the operator can turn the dots on then adjust a/b
          (N1/P1) times and re-run. Model-fit knobs (capabilities.modelFit) are schema-reserved (v1). */}
      {canEditMarks && (
        <MarksEditor
          seededMarks={seededMarks}
          params={params}
          onParamsChange={setParams}
          markLabelsShown={markLabelsShown}
          onMarkLabelsShownChange={onMarkLabelsShownChange}
          // #6 — the bespoke editor shares the param grid's changed-state ring over its own keys.
          changedAuthor={authorOfKeys(MARKS_PARAM_KEYS, baseParams, params, proposals)}
        />
      )}

      {/* Volcano FC/p-value thresholds (generalization-spec §F) — gated on the declared thresholds
          capability. Points re-colour live (the parent preview applies them); re-run updates the table. */}
      {canEditThresholds && (
        <ThresholdEditor
          figureSpec={figureSpec}
          params={params}
          onParamsChange={setParams}
          changedAuthor={authorOfKeys(THRESHOLD_PARAM_KEYS, baseParams, params, proposals)}
        />
      )}

      {/* Inputs → re-run. A stable slot across loading / error / empty / ready (Task B3). */}
      <PaneShell state={inputsState} title="Inputs">
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {visibleParamFields(schema, params).map((f) => {
            // Highlight a control changed since the figure was produced (staged ≠ base), so it's
            // obvious WHICH inputs a re-run will apply: amber for a manual edit (matching the
            // pending-changes banner), fuchsia + the ✨ marker for an accepted AI value. authorOf
            // returns null when unchanged → no highlight. Editing an AI value yourself flips it to
            // "user" (amber) since the value stops matching the proposal — no extra bookkeeping.
            const author = authorOf(f.key, baseParams, params, proposals);
            const aiProposal =
              author === "ai"
                ? proposals.find((p) => p.status === "accepted" && p.paramKey === f.key)
                : undefined;
            return (
              <div
                key={f.key}
                className={cn("rounded-lg p-2 transition-shadow", changedRingClass(author))}
              >
                {/* The ✨ marker rides ParamControl's `badge` slot (inline beside the label), NOT an
                    absolute overlay — an overlay covered the control's right-aligned value readout. It
                    is "staged" (accepted, not yet re-run), not "applied". */}
                <ParamControl
                  field={f}
                  value={params[f.key]}
                  disabled={isFieldDisabled(schema, f, params)}
                  onChange={(v) => setParams((p) => ({ ...p, [f.key]: v }))}
                  badge={
                    aiProposal ? (
                      <AiMarker
                        state="staged"
                        size="xs"
                        model={aiProposal.model}
                        onRevert={onRevertProposal ? () => onRevertProposal(aiProposal.id) : undefined}
                      />
                    ) : undefined
                  }
                />
              </div>
            );
          })}
        </div>
        {/* Helper text on its own line, then a right-aligned button row — in the narrow 360px dock a
            side-by-side text+buttons layout cramps the text into a one-word column once Reset appears. */}
        <div className="mt-4 space-y-2">
          <p className="text-[11px] text-muted-foreground">
            {dirty ? "Re-runs the analysis → a new linked version." : "Adjust an input to re-run."}
          </p>
          <div className="flex items-center justify-end gap-2">
            {dirty && onReset && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onReset}
                disabled={running}
                title="Discard changes — back to this figure's current values"
              >
                <RotateCcw /> Reset
              </Button>
            )}
            <Button size="sm" disabled={running || !dirty} onClick={() => onRerun(params)}>
              <RefreshCw /> {running ? "Re-running…" : "Re-run → new version"}
            </Button>
          </div>
        </div>
      </PaneShell>
    </div>
  );
}
