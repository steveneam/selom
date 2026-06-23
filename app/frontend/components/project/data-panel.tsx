"use client";

import * as React from "react";
import { Database, FileSpreadsheet, Plus, ShieldAlert, X } from "lucide-react";
import { IntakeQuestionnaire } from "@/components/intake/intake-questionnaire";
import { Dropzone } from "./dropzone";
import { CleaningReport } from "./cleaning-report";
import { DataTypeStrip } from "./data-type-strip";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { modalityColor } from "@/lib/catalog/modality";
import { datasetDisplayName } from "@/lib/lineage/family";
import { detectModality, proposeForModality, type IntakeProposal } from "@/lib/intake/mock";
import { inspectData, modalityFromKind, qcFromInspect, type DataTypeOverride } from "@/lib/intake/inspect";
import { projectStore } from "@/lib/projects/store";
import type { Dataset } from "@/lib/projects/types";

export interface AnalyzeArgs {
  datasetId: string;
  file: File;
  proposal: IntakeProposal | null;
  /** Optional design / sample sheet for bulk + time-course DE (item b). */
  designFile?: File | null;
}

/** Active dataset being intaked (just uploaded, or chosen via "Analyze"). */
interface Active {
  dataset: Dataset;
  file: File;
  /** True when `file` holds the real dropped bytes (so we can (re)classify it live); false for a
   *  re-opened dataset whose bytes were lost — its persisted profile is shown read-only. */
  real: boolean;
}

export function DataPanel({
  projectId,
  datasets,
  onAnalyze,
  incomingFile,
  onIncomingConsumed,
}: {
  projectId: string;
  datasets: Dataset[];
  onAnalyze: (args: AnalyzeArgs) => void;
  /** A file dropped on the Overview hub — ingest it here on arrival. */
  incomingFile?: File | null;
  onIncomingConsumed?: () => void;
}) {
  const [active, setActive] = React.useState<Active | null>(null);
  const [designFile, setDesignFile] = React.useState<File | null>(null);
  // Cleaning steps the user has switched off for the active dataset (before/after editor).
  const [disabledSteps, setDisabledSteps] = React.useState<Set<string>>(new Set());
  // The live engine inspect is in flight for the active dataset (drop or data-type override).
  const [inspecting, setInspecting] = React.useState(false);

  React.useEffect(() => {
    setDisabledSteps(new Set());
  }, [active?.dataset.id]);

  // Classify the dropped bytes against the live engine and apply the real modality + cleaning/QC
  // verdict, replacing the optimistic filename-only guess. Fail-soft: a null result (offline /
  // dev:mock / uninspectable) keeps the guess so the flow is never broken. `override` is the user's
  // explicit data-type choice (the L3 layer). Tagged by dataset id so a late response from a
  // previous file can't clobber a newer active dataset.
  const runInspect = React.useCallback(
    async (dataset: Dataset, file: File, override?: DataTypeOverride) => {
      setInspecting(true);
      const result = await inspectData(file, override);
      setInspecting(false);
      if (!result) return;
      const modality = modalityFromKind(result.kind);
      const qc = qcFromInspect(result);
      projectStore.updateDatasetProfile(dataset.id, { modality, qc });
      setActive((a) => (a && a.dataset.id === dataset.id
        ? { ...a, dataset: { ...a.dataset, modality, qc } }
        : a));
    },
    [],
  );

  function ingest(file: File) {
    const modality = detectModality(file.name);
    const dataset = projectStore.addDataset(projectId, file.name, modality);
    setActive({ dataset, file, real: true });
    setDisabledSteps(new Set());
    void runInspect(dataset, file);
  }

  // The user corrects the detected data type (the user-input layer). Needs the real bytes to
  // re-classify.
  function setDataType(code: DataTypeOverride) {
    if (!active?.real) return;
    void runInspect(active.dataset, active.file, code);
  }

  // Clear an explicit override → re-inspect with no hint, falling back to the auto-detected type.
  function resetDataType() {
    if (!active?.real) return;
    void runInspect(active.dataset, active.file);
  }

  // Consume a file handed over from the Overview drop. Guard with a ref so a given
  // File is ingested exactly once (StrictMode double-invokes effects in dev, and the
  // parent's clear hasn't propagated yet on the second pass).
  const ingestedRef = React.useRef<File | null>(null);
  React.useEffect(() => {
    if (!incomingFile || ingestedRef.current === incomingFile) return;
    ingestedRef.current = incomingFile;
    ingest(incomingFile);
    onIncomingConsumed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incomingFile]);

  function analyzeExisting(dataset: Dataset) {
    // A re-opened dataset's real bytes are gone (only metadata persists) — synthesize a placeholder
    // and mark it not-real, so its persisted profile shows read-only (no bogus re-classify of "mock").
    setActive({ dataset, file: new File(["mock"], dataset.filename), real: false });
  }

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {/* left: upload + dataset list */}
      <div className="space-y-5">
        {/* Big box only when there's nothing yet; once you have data it shrinks to a
            compact "+ Add data" so the datasets (below) are the focus. A project can
            hold several datasets, so an add-affordance always lives here. */}
        {datasets.length === 0 ? (
          <Dropzone
            onFile={ingest}
            accept=".h5ad,.csv,.tsv,.mzML,.iwxdata"
            title="Drop your data here"
            hint="or click to browse — Selom detects the type, cleans it, and asks a few questions"
            formats=".h5ad · .csv · .tsv · .mzML · .iwxdata"
          />
        ) : (
          <Dropzone
            onFile={ingest}
            accept=".h5ad,.csv,.tsv,.mzML,.iwxdata"
            title="Add another dataset"
            hint="Drop a file or click to browse"
            icon={Plus}
            variant="secondary"
          />
        )}

        {/* Optional design / sample sheet (item b) — for bulk & time-course DE. */}
        {designFile ? (
          <div className="flex items-center gap-3 rounded-xl border border-stage-publish/40 bg-[color-mix(in_oklab,var(--stage-publish)_8%,transparent)] px-4 py-3">
            <span className="grid size-9 place-items-center rounded-lg border border-stage-publish/40 text-stage-publish [&_svg]:size-4">
              <FileSpreadsheet />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">{designFile.name}</p>
              <p className="text-xs text-muted-foreground">Design sheet — joined on sample id at run time.</p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 text-muted-foreground hover:text-destructive"
              aria-label="Remove design sheet"
              onClick={() => setDesignFile(null)}
            >
              <X />
            </Button>
          </div>
        ) : (
          <Dropzone
            onFile={setDesignFile}
            accept=".csv,.tsv,.xlsx"
            title="Add a design / sample sheet"
            hint="Optional — maps samples to conditions for bulk & time-course DE"
            icon={FileSpreadsheet}
            variant="secondary"
          />
        )}

        <div className="space-y-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Your data
          </p>
          {datasets.length === 0 ? (
            <p className="text-xs text-muted-foreground">No datasets yet — drop a file above to begin.</p>
          ) : (
            datasets.map((d) => {
              const color = modalityColor(d.modality);
              const isActive = active?.dataset.id === d.id;
              const warns = d.qc?.guardrails.filter((g) => g.level !== "info").length ?? 0;
              return (
                <button
                  key={d.id}
                  onClick={() => analyzeExisting(d)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-colors",
                    isActive
                      ? "border-primary/50 bg-accent/30 ring-1 ring-ring/30"
                      : "border-border bg-card hover:border-primary/40 hover:bg-card/80",
                  )}
                >
                  <span
                    aria-hidden
                    className="grid size-9 shrink-0 place-items-center rounded-lg border [&_svg]:size-4"
                    style={{
                      borderColor: `color-mix(in oklab, ${color} 45%, transparent)`,
                      background: `color-mix(in oklab, ${color} 12%, var(--card))`,
                      color,
                    }}
                  >
                    <Database />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{datasetDisplayName(d)}</p>
                    <p className="tabular text-xs text-muted-foreground">
                      {d.label ? `${d.filename} · ` : ""}
                      {d.qc?.profileLabel ?? d.modality}
                      {d.qc ? ` · ${d.qc.nObs.toLocaleString()} × ${d.qc.nVar.toLocaleString()}` : ""}
                      {d.qc?.applies && d.qc.cleaningSteps?.length
                        ? ` · ${d.qc.cleaningSteps.length} cleaning steps`
                        : ""}
                    </p>
                  </div>
                  {warns > 0 && (
                    <span
                      title={`${warns} guardrail flag${warns === 1 ? "" : "s"}`}
                      className="tabular inline-flex items-center gap-1 rounded-md border border-warn/40 bg-warn/10 px-1.5 py-0.5 text-[10px] font-medium text-warn"
                    >
                      <ShieldAlert className="size-3.5" />
                      {warns}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* right: intake questionnaire + QC for the active dataset */}
      <div>
        {active ? (
          <Card className="space-y-5 p-5">
            <DataTypeStrip
              qc={active.dataset.qc}
              modality={active.dataset.modality}
              inspecting={inspecting}
              canOverride={active.real}
              onSetDataType={setDataType}
              onResetDataType={resetDataType}
            />
            {active.dataset.qc && (
              <CleaningReport
                qc={active.dataset.qc}
                modality={active.dataset.modality}
                disabledSteps={disabledSteps}
                onToggleStep={(id) =>
                  setDisabledSteps((prev) => {
                    const next = new Set(prev);
                    if (next.has(id)) next.delete(id);
                    else next.add(id);
                    return next;
                  })
                }
              />
            )}
            <IntakeQuestionnaire
              modality={active.dataset.modality}
              onSubmit={(answers) =>
                onAnalyze({
                  datasetId: active.dataset.id,
                  file: active.file,
                  proposal: proposeForModality(active.dataset.modality, answers),
                  designFile,
                })
              }
              onSkip={() =>
                onAnalyze({ datasetId: active.dataset.id, file: active.file, proposal: null, designFile })
              }
            />
          </Card>
        ) : (
          <Card className="grid h-full place-items-center p-8 text-center">
            <div className="max-w-xs space-y-1.5">
              <p className="text-sm font-medium text-foreground">Drop or pick a dataset</p>
              <p className="text-xs text-muted-foreground">
                Selom auto-detects the data type, cleans it, and asks a few questions so the assistant
                can propose a pipeline.
              </p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
