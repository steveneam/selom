"use client";

import * as React from "react";
import { Paintbrush, RefreshCw, RotateCcw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PaneBoundary } from "@/components/ui/error-boundary";
import { FigureDataPanel } from "../figure-data-panel";
import { EmptyState } from "./empty-state";
import { FigureCanvas } from "@/components/figure/figure-canvas";
import { AiProposalRow } from "@/components/ai/ai-proposal-row";
import { AskAi, type AutoTuneOutcome } from "@/components/ai/ask-ai";
import { getSkill } from "@/lib/catalog/seed";
import { deriveFigureModel } from "@/lib/figure/figure-model";
import { readSeededMarks } from "@/lib/erg/marks";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { SkillParams } from "@/lib/skills/api";
import type { AiProposal } from "@/lib/ai/types";
import type { PendingCounter } from "@/lib/ai/proposals";
import type { Figure } from "@/lib/projects/types";
import type { FigureStore } from "@/hooks/use-figure-store";

type CanvasProps = React.ComponentProps<typeof FigureCanvas>;

/**
 * The Figure-data view (`view === "figuredata"`): a LIVE preview of the figure beside the staged
 * inputs — a dot drag / numeric editor / AskAi proposal / deterministic Auto-tune all stage into the
 * shared queue, and ONE explicit re-run applies them. Presentational: the staging state lives in
 * `use-figure-data-staging`, the AI-proposal handlers in `use-ai-helpers`; this renders them.
 */
export function FigureDataView({
  activeFigure,
  figure,
  fdParams,
  setFdParams,
  fdDirty,
  fdScope,
  previewSpec,
  markLabelsShown,
  setMarkLabelsShown,
  onMarkMove,
  onThresholdChange,
  autoTune,
  aiProposals,
  aiCounter,
  running,
  resetFdToBase,
  rerunPending,
  acceptAiProposal,
  dismissAiProposal,
  acceptAllAiProposals,
  dismissAllAiProposals,
  revertAiProposal,
  addAiProposals,
  onOpenFigure,
  onPickSkill,
  onRunSkill,
}: {
  activeFigure: Figure | undefined;
  figure: FigureStore;
  fdParams: SkillParams;
  setFdParams: React.Dispatch<React.SetStateAction<SkillParams>>;
  fdDirty: boolean;
  fdScope: string;
  previewSpec: FigureSpec | null | undefined;
  markLabelsShown: boolean;
  setMarkLabelsShown: React.Dispatch<React.SetStateAction<boolean>>;
  onMarkMove: CanvasProps["onMarkMove"];
  onThresholdChange: CanvasProps["onThresholdChange"];
  autoTune: () => Promise<AutoTuneOutcome>;
  aiProposals: AiProposal[];
  aiCounter: PendingCounter;
  running: string | null;
  resetFdToBase: () => void;
  rerunPending: () => void;
  acceptAiProposal: (id: string) => void;
  dismissAiProposal: (id: string) => void;
  acceptAllAiProposals: () => void;
  dismissAllAiProposals: () => void;
  revertAiProposal: (id: string) => void;
  addAiProposals: (fresh: AiProposal[]) => void;
  onOpenFigure: (f: Figure) => void;
  onPickSkill: (skillId: string) => void;
  onRunSkill: () => void;
}) {
  if (!activeFigure?.skillId) {
    return (
      <EmptyState
        title="No figure selected"
        body="Open a figure to tune the inputs behind it and re-run."
        action="Run a skill"
        onAction={onRunSkill}
      />
    );
  }
  return (
    // Figure-data is figure-forward: the inputs sit beside a LIVE preview of the same
    // figure the styling box edits (shared `figure` store), so tuning a param + re-run
    // updates the graph in place — no switching to the artboard to see the change.
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {/* Pending-changes prompt: any re-run input (dot drag, a/b time, dots toggle, an
          analysis input) stages here; the figure only updates when you re-run. */}
      {(fdDirty || aiProposals.length > 0) && (
        <div className="space-y-2.5 rounded-lg border border-stage-figuredata/45 bg-[color-mix(in_oklab,var(--stage-figuredata)_12%,var(--card))] px-3.5 py-2.5">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs leading-relaxed text-foreground">
              <span className="font-semibold text-stage-figuredata">Pending changes</span>
              {aiCounter.total > 0 ? (
                <>
                  {" · "}
                  <span className="tabular-nums">{aiCounter.total} pending</span>
                  {aiCounter.you > 0 && <span className="tabular-nums"> · {aiCounter.you} you</span>}
                  {aiCounter.ai > 0 && (
                    <span className="inline-flex items-center gap-0.5 align-baseline text-stage-ai">
                      {" · "}
                      <Sparkles className="size-3" aria-hidden />
                      <span className="tabular-nums">{aiCounter.ai}</span> AI
                    </span>
                  )}
                  {" — re-run to apply them to the measured values, the statistics table, and any downstream figures."}
                </>
              ) : (
                " — review the AI suggestions below, then accept the ones to keep."
              )}
            </span>
            <div className="flex shrink-0 items-center gap-2">
              {aiCounter.total > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={running != null}
                  onClick={resetFdToBase}
                  title="Discard changes — back to this figure's current values"
                >
                  <RotateCcw /> Reset
                </Button>
              )}
              <Button
                size="sm"
                disabled={running != null || aiCounter.total === 0}
                onClick={rerunPending}
              >
                <RefreshCw /> {running != null ? "Re-running…" : "Re-run → new version"}
              </Button>
            </div>
          </div>
          {aiProposals.length > 0 && (
            <div className="border-t border-stage-figuredata/25 pt-2.5">
              {/* Bulk actions (#1): only worth showing with 2+ un-acted suggestions — one row's own
                  Accept/Dismiss suffice below that. Accept all stages every proposed value at once. */}
              {aiProposals.filter((p) => p.status === "proposed").length >= 2 && (
                <div className="mb-1.5 flex items-center justify-end gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-[11px]"
                    disabled={running != null}
                    onClick={acceptAllAiProposals}
                  >
                    Accept all
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-[11px] text-muted-foreground hover:text-destructive"
                    disabled={running != null}
                    onClick={dismissAllAiProposals}
                  >
                    Dismiss all
                  </Button>
                </div>
              )}
              <ul className="space-y-1.5">
                {aiProposals.map((p) => (
                  <AiProposalRow
                    key={p.id}
                    proposal={p}
                    onAccept={acceptAiProposal}
                    onDismiss={dismissAiProposal}
                    onRevert={revertAiProposal}
                    disabled={running != null}
                  />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      <div className="flex min-h-0 flex-1 gap-4">
      <div className="flex min-h-[520px] flex-1 flex-col overflow-hidden rounded-xl border border-border bg-background">
        <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Live preview {running != null && <span className="text-primary">· re-running…</span>}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onOpenFigure(activeFigure)}
            title="Open this figure in the editor to style it"
          >
            <Paintbrush /> Style this figure
          </Button>
        </div>
        {figure.spec ?? activeFigure.spec ? (
          <div className="relative flex min-h-0 flex-1 items-start justify-center overflow-auto p-6">
            <div
              className="relative flex rounded-xl border border-border bg-artboard p-3 shadow-2xl ring-1 ring-black/5"
              style={{ width: "100%", maxWidth: "56rem", height: "min(70vh, 680px)" }}
            >
              <div className="min-h-0 min-w-0 flex-1">
                {/* Show the modebar so the live preview always has Zoom / Pan / Autoscale /
                    Reset-axes buttons — scroll-zoom (enabled for ERG) needs a reset to undo it.
                    onMarkMove makes the a/b dots draggable here too (not just in the styler).
                    previewSpec hides the dot labels client-side when the toggle is off.
                    Isolated (Task B1): a staged-preview projection that throws shows a fallback
                    rather than unmounting the Figure-data stage. */}
                <PaneBoundary
                  label="preview"
                  title="This preview couldn't be drawn"
                  resetKeys={[activeFigure.datasetId, activeFigure.skillId, activeFigure.id, previewSpec]}
                >
                  <FigureCanvas
                    spec={(previewSpec ?? figure.spec ?? activeFigure.spec)!}
                    displayModeBar
                    onMarkMove={onMarkMove}
                    onThresholdChange={onThresholdChange}
                  />
                </PaneBoundary>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid flex-1 place-items-center p-6 text-center text-xs text-muted-foreground">
            Re-run to generate this figure’s preview.
          </div>
        )}
      </div>
      <div className="w-[360px] shrink-0 space-y-3 overflow-y-auto pr-1">
        {/* AI Helpers (S5): a single-shot "Ask AI to tune these inputs" composer — its
            proposals land in the pending-changes banner above. Degrades clean (the gateway
            is off by default → an empty plan → a quiet note, the editor unaffected). */}
        <AskAi
          stage="analyze"
          mode="staged"
          label="Ask AI to tune these inputs"
          placeholder="e.g. tighten the clusters"
          context={{
            skillId: activeFigure.skillId,
            params: fdParams,
            figureSpec: figure.spec ?? activeFigure.spec,
          }}
          onStaged={addAiProposals}
          // The DETERMINISTIC one-click default (Layer A Auto-tune, docs/auto-tune/spec.md):
          // fetch the engine's best-practice params for this skill + data, stage the diff into
          // the SAME pending queue as human-authored changes (no ✨, no gateway) — one re-run
          // above commits them. Design params stay ingest's job, so they never appear here.
          // The handler lives in use-figure-data-staging (it owns fdParams + the base diff).
          onAutoTune={autoTune}
          autoTuneLabel="Auto-tune inputs"
          pendingActive={fdDirty}
          scopeKey={fdScope}
          disabled={running != null}
        />
        {/* Isolated (Task B1): the Figure-data inputs are bespoke per skill — if a control
            throws on an unexpected param/spec shape, the inputs pane fails alone, not the
            whole stage. resetKeys clear a stuck boundary on a dataset/skill/figure switch.
            Task B4: key={fdScope} (dataset:skill:figure) REMOUNTS the bespoke inputs on any
            such switch, so no staged control state from another skill can survive it. */}
        <PaneBoundary
          label="figure-data"
          title="These inputs couldn't be shown"
          resetKeys={[activeFigure.datasetId, activeFigure.skillId, activeFigure.id]}
        >
        <FigureDataPanel
          key={fdScope}
          skillId={activeFigure.skillId}
          skillName={getSkill(activeFigure.skillId)?.name ?? activeFigure.skillId}
          baseParams={activeFigure.provenance?.params ?? {}}
          params={fdParams}
          onParamsChange={setFdParams}
          running={running != null}
          dataCheck={activeFigure.dataCheck}
          dataFit={activeFigure.dataFit}
          seededMarks={readSeededMarks(figure.spec ?? activeFigure.spec)}
          canEditMarks={deriveFigureModel(figure.spec ?? activeFigure.spec).capabilities.landmarkMarks}
          canEditThresholds={deriveFigureModel(figure.spec ?? activeFigure.spec).capabilities.thresholds}
          figureSpec={figure.spec ?? activeFigure.spec}
          specSeed={
            // C5: seed the Inputs from THIS figure's own provenance param_spec (stamped at
            // run) so re-opening it shows the controls with no describe round-trip, and an
            // offline already-run figure stays tunable. Older figures (no param_spec) fetch.
            activeFigure.provenance?.skill?.param_spec
              ? { version: activeFigure.provenance.skill.version, spec: activeFigure.provenance.skill.param_spec }
              : null
          }
          markLabelsShown={markLabelsShown}
          onMarkLabelsShownChange={setMarkLabelsShown}
          proposals={aiProposals}
          onRevertProposal={revertAiProposal}
          onReset={resetFdToBase}
          // Route the panel's own Re-run through rerunPending too (NOT the plain
          // rerunFigureWithParams) so it takes the /ai/apply path when proposals are
          // accepted — otherwise the two identical "Re-run" buttons diverge and this one
          // silently drops AI provenance + orphans the queue. rerunPending reads fdParams
          // (the shared staged source the panel also edits) so the param arg is redundant.
          onRerun={rerunPending}
          onPickSkill={onPickSkill}
          onPickManually={onRunSkill}
        />
        </PaneBoundary>
      </div>
      </div>
    </div>
  );
}
