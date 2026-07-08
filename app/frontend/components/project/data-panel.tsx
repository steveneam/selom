"use client";

import * as React from "react";
import { Database, FileSpreadsheet, Plus, ShieldAlert, X } from "lucide-react";
import { IntakeQuestionnaire } from "@/components/intake/intake-questionnaire";
import { Dropzone } from "./dropzone";
import { CleaningReport } from "./cleaning-report";
import { DataTypeStrip } from "./data-type-strip";
import { DataFitVerdict } from "@/components/reproduction/data-fit-panel";
import { ConfidenceChip } from "@/components/ui/confidence-chip";
import { BAND_TONE, CONFIDENCE_META } from "@/lib/reproduction/data-fit";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/ui/cn";
import { modalityColor } from "@/lib/catalog/modality";
import { getSkill } from "@/lib/catalog/seed";
import { datasetDisplayName } from "@/lib/lineage/family";
import { detectModality, proposeForModality, proposeFromQc, type IntakeAnswers, type IntakeProposal } from "@/lib/intake/mock";
import { combineData, inspectData, modalityFromKind, qcFromInspect, type DataTypeOverride } from "@/lib/intake/inspect";
import { designRunParams, timeCourseDesignFile, type DesignChoice } from "@/lib/intake/design";
import { uploadDataset } from "@/lib/uploads/api";
import { apiMockingEnabled } from "@/lib/config/env";
import { projectStore } from "@/lib/projects/store";
import type { AiActionDelta } from "@/lib/ai/types";
import type { Dataset } from "@/lib/projects/types";

/** Inject the confirmed experimental design (the questionnaire's confirm-card) into the proposal's
 *  DE step — the `deg` runner reads these params directly (reference/treatment/condition_col/…) and
 *  records them in provenance, so a gateway-off re-run reproduces. No design → the proposal is
 *  unchanged (an already-computed DE table / unsupervised run needs none). build-spec §3b.
 *  `aiActions` (2b): when the design came from the AI refiner and was confirmed unchanged, attach the
 *  set_design delta to the DE step so runFlow routes it through /ai/apply (✨ attribution). */
function withDesign(
  proposal: IntakeProposal | null,
  choice: DesignChoice | null,
  aiActions?: AiActionDelta[],
): IntakeProposal | null {
  if (!proposal || !choice) return proposal;
  const dp = designRunParams(choice);
  return {
    ...proposal,
    steps: proposal.steps.map((s) =>
      s.skillId === "selom.deg"
        ? { ...s, params: { ...s.params, ...dp }, ...(aiActions?.length ? { aiActions } : {}) }
        : s,
    ),
  };
}

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
  reattachDatasetId,
  onReattach,
}: {
  projectId: string;
  datasets: Dataset[];
  onAnalyze: (args: AnalyzeArgs) => void;
  /** A file dropped on the Overview hub — ingest it here on arrival. */
  incomingFile?: File | null;
  onIncomingConsumed?: () => void;
  /** When set (from the lost-bytes banner), the next dropped file REFILLS this existing dataset
   *  instead of creating a new one (C5 re-attach). */
  reattachDatasetId?: string | null;
  /** Push re-attached bytes up so the session can re-run the figure (sets `lastFile`). */
  onReattach?: (datasetId: string, file: File) => void;
}) {
  const [active, setActive] = React.useState<Active | null>(null);
  const [designFile, setDesignFile] = React.useState<File | null>(null);
  // The active data-type override (the L3 layer) — tracked so a design-sheet re-inspect preserves it.
  const [override, setOverride] = React.useState<DataTypeOverride | undefined>(undefined);
  // Cleaning steps the user has switched off for the active dataset (before/after editor).
  const [disabledSteps, setDisabledSteps] = React.useState<Set<string>>(new Set());
  // The live engine inspect is in flight for the active dataset (drop or data-type override).
  const [inspecting, setInspecting] = React.useState(false);
  // The real byte-upload handshake (WS2.1) is in flight for a freshly dropped file.
  const [uploading, setUploading] = React.useState(false);
  // Multi-file combine (C6) is in flight; or its error.
  const [combining, setCombining] = React.useState(false);
  const [combineError, setCombineError] = React.useState<string | null>(null);
  // dev:mock has no upload/run-dataset handlers → skip the byte-upload handshake (WS2.1) and keep the
  // metadata-only + multipart mock path. Real backend (the verify target) runs the full loop.
  const mockMode = apiMockingEnabled;

  React.useEffect(() => {
    setDisabledSteps(new Set());
  }, [active?.dataset.id]);

  // Classify the dropped bytes against the live engine and apply the real modality + cleaning/QC
  // verdict, replacing the optimistic filename-only guess. Fail-soft: a null result (offline /
  // dev:mock / uninspectable) keeps the guess so the flow is never broken. `override` is the user's
  // explicit data-type choice (the L3 layer). Tagged by dataset id so a late response from a
  // previous file can't clobber a newer active dataset.
  const runInspect = React.useCallback(
    async (dataset: Dataset, file: File, over?: DataTypeOverride, designSheet?: File | null) => {
      setInspecting(true);
      // A2 fix: track the in-flight/failed state explicitly (rather than silently keeping whatever
      // qc — real or none — the dataset already had) so the UI can render an honest "Inspecting…" /
      // "Couldn't inspect this file" instead of ever showing a fabricated verdict.
      projectStore.setInspectState(dataset.id, "pending");
      const result = await inspectData(file, over, designSheet);
      setInspecting(false);
      if (!result) {
        projectStore.setInspectState(dataset.id, "failed");
        setActive((a) => (a && a.dataset.id === dataset.id
          ? { ...a, dataset: { ...a.dataset, inspectState: "failed" } }
          : a));
        return;
      }
      const modality = modalityFromKind(result.kind);
      const qc = qcFromInspect(result);
      // Persist the Slice-2 data-aware route + the intake DESIGN prefill alongside QC so the data-driven
      // recommendations AND the questionnaire's confirm-card prefill survive reload (read from the
      // dataset, not an in-session proposal).
      const { routing, dataFit, design } = result;
      projectStore.updateDatasetProfile(dataset.id, { modality, qc, routing, dataFit, design });
      setActive((a) => (a && a.dataset.id === dataset.id
        ? { ...a, dataset: { ...a.dataset, modality, qc, routing, dataFit, design, inspectState: undefined } }
        : a));
    },
    [],
  );

  async function ingest(file: File) {
    // C5 re-attach: when the lost-bytes banner sent us here, the next file REFILLS the existing
    // dataset (same record + a fresh sha) instead of spawning a duplicate, and the bytes go up so
    // the figure can re-run this session.
    const reattach = reattachDatasetId ? datasets.find((d) => d.id === reattachDatasetId) : undefined;
    if (reattach) {
      setActive({ dataset: reattach, file, real: true });
      setDisabledSteps(new Set());
      setOverride(undefined);
      projectStore.markDatasetUpdated(reattach.id);
      onReattach?.(reattach.id, file);
      void runInspect(reattach, file, undefined, designFile);
      return;
    }
    const modality = detectModality(file.name);
    // WS2.1 — close the upload→run→save loop: put the BYTES in the object store so the run goes from
    // the dataset_id (no re-upload) and the dataset survives reload re-runnable. Fail-soft: a failed
    // upload (or dev:mock, which has no upload handlers) degrades to the metadata-only dataset + this
    // session's multipart run — the proven flow is never broken.
    let dataset: Dataset | null = null;
    if (!mockMode) {
      setUploading(true);
      dataset = await uploadDataset(projectId, file);
      setUploading(false);
      if (dataset) dataset = projectStore.addUploadedDataset(dataset);
    }
    if (!dataset) dataset = projectStore.addDataset(projectId, file.name, modality);
    setActive({ dataset, file, real: true });
    setDisabledSteps(new Set());
    setOverride(undefined);
    void runInspect(dataset, file, undefined, designFile);
  }

  // Drop SEVERAL files → combine them into one multi-condition dataset (C6): each file is a
  // condition (its own `condition` column, e.g. C57/Rd10, else its stem). A single file falls
  // through to the normal ingest path. Fail-soft: a backend error surfaces a note, no dataset made.
  function combineFiles(files: File[]) {
    if (files.length <= 1) {
      if (files[0]) void ingest(files[0]);
      return;
    }
    setCombineError(null);
    setCombining(true);
    void combineData(files).then((result) => {
      setCombining(false);
      if (!result) {
        setCombineError(
          "Couldn't combine those files — they need to be ERG recordings (.iwxdata / Diagnosys / a canonical waveform table).",
        );
        return;
      }
      const dataset = projectStore.addDataset(projectId, result.file.name, detectModality(result.file.name));
      setActive({ dataset, file: result.file, real: true });
      setDisabledSteps(new Set());
      setOverride(undefined);
      void runInspect(dataset, result.file, undefined, designFile);
    });
  }

  // The user corrects the detected data type (the user-input layer). Needs the real bytes to
  // re-classify.
  function setDataType(code: DataTypeOverride) {
    if (!active?.real) return;
    setOverride(code);
    void runInspect(active.dataset, active.file, code, designFile);
  }

  // Clear an explicit override → re-inspect with no hint, falling back to the auto-detected type.
  function resetDataType() {
    if (!active?.real) return;
    setOverride(undefined);
    void runInspect(active.dataset, active.file, undefined, designFile);
  }

  // Attach / remove a design sheet → update state AND re-inspect the active dataset so the confirm-card
  // reflects the sheet as the design source of truth BEFORE the run, not only at run time (followups
  // #5), preserving the current data-type override. Done from the dropzone handlers (an event), not an
  // effect, so re-inspect stays an explicit user action.
  function attachDesign(f: File) {
    setDesignFile(f);
    if (active?.real) void runInspect(active.dataset, active.file, override, f);
  }
  function removeDesign() {
    setDesignFile(null);
    if (active?.real) void runInspect(active.dataset, active.file, override, null);
  }

  // Consume a file handed over from the Overview drop. Guard with a ref so a given
  // File is ingested exactly once (StrictMode double-invokes effects in dev, and the
  // parent's clear hasn't propagated yet on the second pass).
  const ingestedRef = React.useRef<File | null>(null);
  React.useEffect(() => {
    if (!incomingFile || ingestedRef.current === incomingFile) return;
    ingestedRef.current = incomingFile;
    void ingest(incomingFile);
    onIncomingConsumed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incomingFile]);

  function analyzeExisting(dataset: Dataset) {
    // A re-opened dataset's real bytes are gone (only metadata persists) — synthesize a placeholder
    // and mark it not-real, so its persisted profile shows read-only (no bogus re-classify of "mock").
    setActive({ dataset, file: new File(["mock"], dataset.filename), real: false });
    setOverride(undefined);
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
            onFile={(f) => void ingest(f)}
            onFiles={combineFiles}
            multiple
            accept=".h5ad,.csv,.tsv,.txt,.mzML,.iwxdata"
            title={reattachDatasetId ? "Re-upload this dataset's file" : "Drop your data here"}
            hint="or click to browse — drop several ERG recordings to combine them into one cohort"
            formats=".h5ad · .csv · .tsv · .txt · .mzML · .iwxdata"
          />
        ) : (
          <Dropzone
            onFile={(f) => void ingest(f)}
            onFiles={combineFiles}
            multiple
            accept=".h5ad,.csv,.tsv,.txt,.mzML,.iwxdata"
            title={reattachDatasetId ? "Re-upload this dataset's file" : "Add or combine datasets"}
            hint="Drop one file, or several ERG recordings to combine into one cohort"
            icon={Plus}
            variant="secondary"
          />
        )}
        {uploading && (
          <p className="text-xs text-muted-foreground" role="status">
            Uploading your data…
          </p>
        )}
        {combining && (
          <p className="text-xs text-muted-foreground" role="status">
            Combining files into one cohort…
          </p>
        )}
        {combineError && (
          <p className="rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
            {combineError}
          </p>
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
              onClick={removeDesign}
            >
              <X />
            </Button>
          </div>
        ) : (
          <Dropzone
            onFile={attachDesign}
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
              // Slice-3 fit band: the persisted data-fit confidence (followups #2) — a glance at
              // whether this dataset is a good fit for what it routes to, without opening it.
              const fitBand = d.dataFit?.confidence;
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
                      {/* A2 fix: a dataset with no real qc yet ever shows an honest in-flight/failed
                          state — never fabricated dims. Once `qc` is real (even if stale mid-reinspect)
                          it keeps showing the last known-good verdict. */}
                      {!d.qc && d.inspectState === "pending" ? (
                        "Inspecting…"
                      ) : !d.qc && d.inspectState === "failed" ? (
                        "Couldn't inspect this file"
                      ) : (
                        <>
                          {d.qc?.profileLabel ?? d.modality}
                          {d.qc ? ` · ${d.qc.nObs.toLocaleString()} × ${d.qc.nVar.toLocaleString()}` : ""}
                          {d.qc?.applies && d.qc.cleaningSteps?.length
                            ? ` · ${d.qc.cleaningSteps.length} cleaning steps`
                            : ""}
                        </>
                      )}
                    </p>
                  </div>
                  {fitBand && (
                    <ConfidenceChip
                      tone={BAND_TONE[fitBand]}
                      label={CONFIDENCE_META[fitBand].label}
                      size="xs"
                      title={CONFIDENCE_META[fitBand].short}
                    />
                  )}
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
            {active.dataset.qc ? (
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
            ) : active.dataset.inspectState === "failed" ? (
              // A2 fix: no real qc and inspect definitively failed — say so, never guess at dims.
              <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                Couldn&apos;t inspect this file — try again, or set the data type manually above.
              </p>
            ) : (
              <p className="text-xs text-muted-foreground" role="status">
                Inspecting…
              </p>
            )}
            {/* Slice-3 (followups #1): the own-data fit verdict on the intake surface — the best-
                fitting analysis's confidence band, reusing the reproduction verdict component. */}
            <DataFitVerdict
              fit={active.dataset.dataFit?.fits[0]}
              skillName={
                active.dataset.dataFit?.fits[0]
                  ? getSkill(`selom.${active.dataset.dataFit.fits[0].skill_id}`)?.name
                  : undefined
              }
            />
            <IntakeQuestionnaire
              modality={active.dataset.modality}
              // A4 fix: `modality` is only a confirmed classification once a real inspect succeeded
              // (`qc` set) — otherwise it's still just the filename heuristic, and the confirm card
              // must say so rather than "Detected".
              modalityGuessed={!active.dataset.qc}
              design={active.dataset.design}
              routing={active.dataset.routing}
              dataColumns={active.dataset.dataFit?.columns}
              onSubmit={(answers: IntakeAnswers, choice: DesignChoice | null, aiActions?: AiActionDelta[]) =>
                onAnalyze({
                  datasetId: active.dataset.id,
                  file: active.file,
                  // A1 fix: once a real qc exists, the proposal's summary/cleaning/guardrails come
                  // from IT, never the modality mock's fabricated stand-ins; the mock is the fallback
                  // only while no real qc is known yet.
                  proposal: withDesign(
                    active.dataset.qc
                      ? proposeFromQc(active.dataset.modality, active.dataset.qc, answers)
                      : proposeForModality(active.dataset.modality, answers),
                    choice,
                    aiActions,
                  ),
                  // A time-course run needs a design sheet (id + `time`); synthesize it from the detected
                  // timepoints when the user hasn't attached a real one (an attached sheet stays authoritative).
                  designFile:
                    (choice?.kind === "time_course" && !designFile && timeCourseDesignFile(choice)) || designFile,
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
