"use client";

import * as React from "react";
import { Database, FileSpreadsheet, ShieldAlert, X } from "lucide-react";
import { IntakeQuestionnaire } from "@/components/intake/intake-questionnaire";
import { Dropzone } from "./dropzone";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { detectModality, proposeForModality, type IntakeProposal } from "@/lib/intake/mock";
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
}

export function DataPanel({
  projectId,
  datasets,
  onAnalyze,
}: {
  projectId: string;
  datasets: Dataset[];
  onAnalyze: (args: AnalyzeArgs) => void;
}) {
  const [active, setActive] = React.useState<Active | null>(null);
  const [designFile, setDesignFile] = React.useState<File | null>(null);

  function ingest(file: File) {
    const modality = detectModality(file.name);
    const dataset = projectStore.addDataset(projectId, file.name, modality);
    setActive({ dataset, file });
  }

  function analyzeExisting(dataset: Dataset) {
    // Seeded datasets have no File object — synthesize one (the mock ignores bytes).
    setActive({ dataset, file: new File(["mock"], dataset.filename) });
  }

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {/* left: upload + dataset list */}
      <div className="space-y-5">
        <Dropzone
          onFile={ingest}
          accept=".h5ad,.csv,.tsv,.mzML"
          title="Drop your data here"
          hint="or click to browse — Selom detects the type, cleans it, and asks a few questions"
          formats=".h5ad · .csv · .tsv · .mzML"
        />

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
            Datasets
          </p>
          {datasets.length === 0 ? (
            <p className="text-xs text-muted-foreground">No datasets yet — drop a file to begin.</p>
          ) : (
            datasets.map((d) => (
              <Card key={d.id} className="flex items-center gap-3 p-3">
                <span className="grid size-8 place-items-center rounded-md border border-border bg-background/60 text-muted-foreground">
                  <Database className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">{d.filename}</p>
                  <p className="tabular text-xs text-muted-foreground">
                    {d.modality}
                    {d.qc ? ` · ${d.qc.nObs.toLocaleString()} × ${d.qc.nVar.toLocaleString()}` : ""}
                  </p>
                </div>
                {d.qc && d.qc.guardrails.some((g) => g.level !== "info") && (
                  <span title="Guardrail flags" className="text-amber-400">
                    <ShieldAlert className="size-4" />
                  </span>
                )}
                <Button variant="outline" size="sm" className="h-7 px-2.5 text-xs" onClick={() => analyzeExisting(d)}>
                  Analyze
                </Button>
              </Card>
            ))
          )}
        </div>
      </div>

      {/* right: intake questionnaire + QC for the active dataset */}
      <div>
        {active ? (
          <Card className="space-y-4 p-5">
            {active.dataset.qc && (
              <div className="rounded-lg border border-border bg-background/40 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
                    Ingest &amp; QC
                  </p>
                  <span className="tabular text-[11px] text-muted-foreground">
                    {active.dataset.qc.nObs.toLocaleString()} × {active.dataset.qc.nVar.toLocaleString()}
                  </span>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {active.dataset.qc.guardrails.map((g, i) => (
                    <Badge key={i} variant={g.level === "error" ? "danger" : g.level === "warn" ? "warn" : "outline"}>
                      {g.level}
                    </Badge>
                  ))}
                  <span className="text-[11px] text-muted-foreground">
                    {active.dataset.qc.cleaning.length} cleaning steps applied
                  </span>
                </div>
              </div>
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
