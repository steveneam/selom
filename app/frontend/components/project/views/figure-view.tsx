"use client";

import * as React from "react";
import { Lock, Redo2, RefreshCw, SlidersHorizontal, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StaleBadge } from "../stale-badge";
import { VersionBar } from "../version-bar";
import { PublishConfidence } from "../publish-confidence";
import { StubEngineBanner } from "../stub-engine-banner";
import { EmptyState } from "./empty-state";
import { CanvasShell } from "@/components/figure/shell/canvas-shell";
import { ExportMenu } from "@/components/figure/export-menu";
import { StylePicker } from "@/components/figure/style-picker";
import { getSkill } from "@/lib/catalog/seed";
import { readStyleStamp } from "@/lib/figure/figure-spec";
import { projectStore } from "@/lib/projects/store";
import type { Figure, Dataset } from "@/lib/projects/types";
import type { FigureStore } from "@/hooks/use-figure-store";

/** Resolve a catalog entry from a namespaced ("selom.erg_traces") OR bare ("erg_traces") id. */
function resolveSkill(skillId: string) {
  return getSkill(skillId) ?? getSkill(`selom.${skillId}`);
}
/** Display name for the editor's Skill pane (catalog name, falling back to the id). */
function skillDisplayName(skillId: string): string {
  return resolveSkill(skillId)?.name ?? skillId;
}
/** Compact origin/version line for the editor's Skill pane ("proprietary · v0.1.0"). */
function skillBadge(skillId: string): string | undefined {
  const sk = resolveSkill(skillId);
  if (!sk) return undefined;
  const origin = sk.license === "proprietary" ? "proprietary" : sk.source;
  return `${origin} · v${sk.version}`;
}

type EditorProps = React.ComponentProps<typeof CanvasShell>;
type VersionBarProps = React.ComponentProps<typeof VersionBar>;

/**
 * The figure-editor view (`view === "figure"`): publish-confidence + the stub banner above the
 * CanvasShell (the four-region Inkscape frame around the artboard) — or an empty state when there's
 * no editable spec. This view still BUILDS the command cluster (undo/redo · staleness re-run · style ·
 * "Figure data" · export · "New figure" · version bar) and hands it to the shell as a `command` slot,
 * so its view-local state (`bundle`/`activeStyle`/export/staleness) stays here, out of the shell.
 */
export function FigureView({
  figure,
  activeFigure,
  activeDataset,
  frozen,
  staleness,
  canRerun,
  running,
  mockMode,
  exportOpen,
  setExportOpen,
  activeFamily,
  onEditCopy,
  onRerunFigure,
  onSweep,
  onOpenCompare,
  onToggleFreeze,
  onMarkMove,
  onToggleLabel,
  onOpenFigureData,
  onNewFigure,
  onRunSkill,
}: {
  figure: FigureStore;
  activeFigure: Figure | undefined;
  activeDataset: Dataset | undefined;
  frozen: boolean;
  staleness: React.ComponentProps<typeof StaleBadge>["result"];
  canRerun: boolean;
  running: string | null;
  mockMode: boolean;
  exportOpen: boolean;
  setExportOpen: (open: boolean) => void;
  activeFamily: Figure[];
  onEditCopy: () => void;
  onRerunFigure: (f: Figure) => void;
  onSweep: VersionBarProps["onSweep"];
  onOpenCompare: (ids: string[]) => void;
  onToggleFreeze: () => void;
  onMarkMove: EditorProps["onMarkMove"];
  onToggleLabel: EditorProps["onToggleLabel"];
  onOpenFigureData: () => void;
  onNewFigure: () => void;
  onRunSkill: () => void;
}) {
  if (!figure.spec) {
    return activeFigure && !activeFigure.spec ? (
      <EmptyState
        title="Figure spec not stored"
        body={`“${activeFigure.title}” was created before figures were saved durably, so its editable spec isn’t available. Re-run the skill to produce a fresh, editable version.`}
        action="Run a skill"
        onAction={onRunSkill}
      />
    ) : (
      <EmptyState
        title="No figure yet"
        body="Run a skill and the editable figure appears here."
        action="Run a skill"
        onAction={onRunSkill}
      />
    );
  }

  // Active journal style for the current figure (journal-styles v1) — DERIVED from the spec's stamp,
  // and the publish-confidence bundle from the persisted record; both are figure-view-local.
  const activeStyle = readStyleStamp(figure.spec);
  const bundle = activeFigure
    ? {
        provenance: activeFigure.provenance,
        methods: activeFigure.methods,
        legend: activeFigure.legend,
        guardrails: activeFigure.guardrails,
      }
    : null;

  // The command cluster the shell frames in its top command bar — the toolbar (undo/redo ·
  // staleness re-run · style · "Figure data" · export · "New figure") plus the version bar.
  const command = (
    <div className="flex flex-col gap-2.5">
      {/* flex-wrap so a long toolbar wraps within the content column at narrow widths rather
          than forcing a single overflowing row. (The AI panel now overlays rather than
          reserving width, so nothing is pushed — this is just graceful narrow-width wrapping.) */}
      <div className="flex flex-wrap items-center gap-1.5">
        {frozen ? (
          <>
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-stage-figure">
              <Lock className="size-3.5" /> Frozen — read-only
            </span>
            <Button size="sm" variant="outline" className="ml-1 h-7" onClick={onEditCopy}>
              Edit a copy
            </Button>
          </>
        ) : (
          <>
            <Button variant="ghost" size="icon" disabled={!figure.canUndo} onClick={figure.undo} aria-label="Undo">
              <Undo2 />
            </Button>
            <Button variant="ghost" size="icon" disabled={!figure.canRedo} onClick={figure.redo} aria-label="Redo">
              <Redo2 />
            </Button>
            <span className="ml-2 text-xs text-muted-foreground">Editing live — every change is a JSON-Patch.</span>
          </>
        )}
        {staleness.stale && activeFigure && (
          <div className="ml-2 flex items-center gap-2">
            <StaleBadge result={staleness} />
            <Button
              size="sm"
              variant="outline"
              className="h-7"
              data-testid="rerun-figure"
              onClick={() => onRerunFigure(activeFigure)}
              disabled={!canRerun || running != null}
              title={canRerun ? "Re-run with the current data → a new version" : "Re-attach the dataset to re-run"}
            >
              <RefreshCw /> {running === activeFigure.skillId ? "Re-running…" : "Re-run"}
            </Button>
          </div>
        )}
        {/* flex-wrap + justify-end so this right-aligned action group wraps within the
            (narrow, rail-shrunk) content column instead of overflowing one 624px row under
            the AI panel — the outer toolbar's flex-wrap can't break inside a single child. */}
        <div className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
          {mockMode && activeDataset && (
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground"
              data-testid="simulate-data-change"
              onClick={() => projectStore.markDatasetUpdated(activeDataset.id)}
              title="Dev (mock only): mark this figure's dataset as changed, to demo staleness"
            >
              Simulate data change
            </Button>
          )}
          {!frozen && (
            <StylePicker
              store={figure}
              skillId={bundle?.provenance?.skill?.id}
              value={activeStyle.id}
            />
          )}
          {activeFigure?.skillId && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onOpenFigureData}
              title="Tune the inputs behind this figure and re-run"
            >
              <SlidersHorizontal /> Figure data
            </Button>
          )}
          <ExportMenu
            spec={figure.spec}
            filename={`selom-${bundle?.provenance?.skill?.id ?? "figure"}`}
            activeStyleLabel={activeStyle.label}
            onOpenChange={setExportOpen}
          />
          <Button variant="ghost" size="sm" onClick={onNewFigure}>
            New figure
          </Button>
        </div>
      </div>
      {activeFigure && (
        <VersionBar
          figure={activeFigure}
          familyCount={activeFamily.length}
          running={running != null}
          skillId={activeFigure.skillId}
          baseParams={activeFigure.provenance?.params ?? {}}
          onSweep={onSweep}
          onCompare={() => onOpenCompare(activeFamily.map((f) => f.id))}
          onToggleFreeze={onToggleFreeze}
        />
      )}
    </div>
  );

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Figure-forward (§3.7): the data-check routing + data-fit verdict relocate to the
          Figure-data stage (reachable from the toolbar / rail) so the artboard is the hero. */}
      <PublishConfidence
        provenance={bundle?.provenance}
        methods={bundle?.methods}
        legend={bundle?.legend}
        guardrails={bundle?.guardrails}
        skillId={activeFigure?.skillId ?? bundle?.provenance?.skill?.id}
      />
      {/* WS1.1 — a stub figure (backend without the science extras) is example data, not the
          user's results; label it loudly, right above the artboard. */}
      <StubEngineBanner provenance={bundle?.provenance} />
      {/* The four-region canvas shell (Pillar-2 s0) — the artboard is the centre hero, the command
          cluster frames the top, the inspector docks right, the tools rail sits left. */}
      <CanvasShell
        command={command}
        store={figure}
        elevated={exportOpen}
        readOnly={frozen}
        onEditCopy={onEditCopy}
        onMarkMove={onMarkMove}
        onToggleLabel={onToggleLabel}
        skill={
          activeFigure?.skillId
            ? {
                skillName: skillDisplayName(activeFigure.skillId),
                badge: skillBadge(activeFigure.skillId),
                onOpenFigureData: onOpenFigureData,
              }
            : undefined
        }
      />
    </div>
  );
}
