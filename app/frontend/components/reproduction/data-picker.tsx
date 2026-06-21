"use client";

import * as React from "react";
import { FileSpreadsheet, RotateCcw, TriangleAlert, X } from "lucide-react";

import { CONFIDENCE_META, type DataFit, type FileFitReport } from "@/lib/reproduction/data-fit";
import type { DataMap, PanelDrive, PaperRun } from "@/lib/reproduction/run";
import { workspaceStore } from "@/lib/workspace/store";
import type { SavedPaper } from "@/lib/workspace/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/**
 * The per-panel data picker (Slice 2 R4). After a run, some in-scope golden panels classify
 * `data_unmatched` — the auto-matcher found no attached file it could feed to that panel's skill (a
 * flat QC table can't be a single-cell matrix; the deposited data is cited, not attached). This is
 * the recovery affordance: point such a panel at a chosen supplement, and Selom re-runs with that
 * choice as a `data_map` override (which wins over the auto-heuristic — D3 "ask only on the gap").
 *
 * Honest by construction: the engine's fit band is shown for each candidate, so forcing a poor-fit
 * file is an *informed* choice; an un-picked panel stays honestly grey (no silent guess). The choice
 * persists on the paper (filenames, not bytes — I5), so it survives until changed. Renders nothing
 * when there are no `data_unmatched` panels (the common / showcase case).
 */
export function DataPicker({
  paper,
  run,
  panelDrives,
  dataFits,
}: {
  paper: SavedPaper;
  run: PaperRun;
  panelDrives: PanelDrive[];
  dataFits: FileFitReport[];
}) {
  const unmatched = panelDrives.filter((d) => d.status === "data_unmatched");
  // The full picked map (covers already-driven picks too, so they stay driven on re-run); seeded
  // from the paper's persisted choices. The UI only edits the currently-unmatched panels.
  const [choices, setChoices] = React.useState<DataMap>(() => paper.dataMap ?? {});

  if (unmatched.length === 0) return null;

  const files = dataFits.map((ff) => ff.filename).filter(Boolean);
  const dirty = JSON.stringify(choices) !== JSON.stringify(paper.dataMap ?? {});
  const hasPicks = unmatched.some((d) => choices[d.panel_key]);
  // The bytes are present this session (a fresh run leaves them in the session cache); after a reload
  // the run is "expired" and this panel never renders, so canRun is effectively always true here.
  const canRerun = run.canRun && hasPicks;

  function setChoice(panelKey: string, filename: string | null) {
    setChoices((prev) => {
      const next = { ...prev };
      if (filename) next[panelKey] = filename;
      else delete next[panelKey];
      return next;
    });
  }

  function rerun() {
    workspaceStore.setPaperDataMap(paper.id, choices);
    run.start(choices);
  }

  return (
    <section className="mt-10">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Point unmatched panels at the right file</h2>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Selom couldn&apos;t auto-match a supplement to these in-scope panels. Pick the file that holds
          each panel&apos;s data and re-run — your choice overrides the auto-matcher and is remembered.
        </p>
      </div>

      <div className="mt-4 space-y-3">
        {unmatched.map((d) => (
          <PickerRow
            key={d.panel_key}
            drive={d}
            files={files}
            dataFits={dataFits}
            value={choices[d.panel_key]}
            onChange={(fn) => setChoice(d.panel_key, fn)}
          />
        ))}
      </div>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-xl text-[11px] leading-relaxed text-muted-foreground">
          {files.length === 0
            ? "No tabular supplement is attached to point these at — add the Excel/CSV that holds this data on the Reproduce tab, then run again."
            : "Un-picked panels stay honestly grey — excluded from the score, never a defect. Re-running grades the panels you pointed at."}
        </p>
        <Button
          size="sm"
          onClick={rerun}
          disabled={!canRerun}
          title={
            canRerun
              ? "Re-run reproduction with your picks"
              : run.phase === "running"
                ? "Reproduction is running…"
                : "Pick a file for at least one panel — and keep the data attached — to re-run"
          }
        >
          <RotateCcw className="size-4" />
          {run.phase === "running" ? "Re-running…" : "Re-run with these picks"}
        </Button>
      </div>
      {dirty && run.phase !== "running" && (
        <p className="mt-1.5 text-right text-[11px] text-amber-600 dark:text-amber-400">
          Unsaved picks — re-run to apply them.
        </p>
      )}
    </section>
  );
}

function PickerRow({
  drive,
  files,
  dataFits,
  value,
  onChange,
}: {
  drive: PanelDrive;
  files: string[];
  dataFits: FileFitReport[];
  value?: string;
  onChange: (filename: string | null) => void;
}) {
  // The engine's fit for the chosen file against THIS panel's skill — so forcing a poor fit is informed.
  const chosenFit = value ? fitFor(dataFits, value, drive.skill_id) : undefined;
  const poor = chosenFit && (chosenFit.confidence === "not_a_fit" || chosenFit.confidence === "unreadable");

  return (
    <Card className="p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="tabular text-sm font-semibold text-foreground">{drive.panel_key}</span>
        {drive.skill_id && (
          <span className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {drive.skill_id}
          </span>
        )}
        {drive.note && <span className="text-xs text-muted-foreground">{drive.note}</span>}
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <FileSpreadsheet className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <div className="min-w-0 flex-1 sm:max-w-sm">
          <Select value={value ?? undefined} onValueChange={(v) => onChange(v)}>
            <SelectTrigger aria-label={`Data file for panel ${drive.panel_key}`}>
              <SelectValue placeholder={files.length ? "Choose a file…" : "No file attached"} />
            </SelectTrigger>
            <SelectContent>
              {files.map((fn) => {
                const f = fitFor(dataFits, fn, drive.skill_id);
                const meta = f ? CONFIDENCE_META[f.confidence] : null;
                return (
                  <SelectItem key={fn} value={fn}>
                    <span className="flex items-center gap-2">
                      {meta && (
                        <span
                          aria-hidden
                          className="size-1.5 shrink-0 rounded-full"
                          style={{ backgroundColor: meta.color }}
                        />
                      )}
                      <span className="truncate">{fn}</span>
                      {meta && <span className="text-muted-foreground/70">· {meta.label}</span>}
                    </span>
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
        </div>
        {value && (
          <Button
            variant="ghost"
            size="icon"
            className="size-8 text-muted-foreground hover:text-foreground"
            onClick={() => onChange(null)}
            aria-label={`Clear the file for panel ${drive.panel_key}`}
            title="Clear — leave this panel grey"
          >
            <X className="size-4" />
          </Button>
        )}
      </div>

      {chosenFit && (
        <p
          className={`mt-1.5 inline-flex items-start gap-1.5 text-[11px] leading-relaxed ${
            poor ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"
          }`}
        >
          {poor && <TriangleAlert className="mt-px size-3 shrink-0" />}
          {poor
            ? `Selom rates this a poor fit — it'll run because you chose it, but the result may be misleading. ${chosenFit.reason}`
            : chosenFit.reason}
        </p>
      )}
    </Card>
  );
}

/** The engine's per-(file, skill) fit, looked up from the run's data-fit ranking. */
function fitFor(
  dataFits: FileFitReport[],
  filename: string,
  skillId?: string | null,
): DataFit | undefined {
  const ff = dataFits.find((x) => x.filename === filename);
  if (!ff) return undefined;
  return ff.fits.find((f) => f.skill_id === skillId) ?? ff.fits[0];
}
