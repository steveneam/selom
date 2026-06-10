"use client";

import * as React from "react";
import { Database, FileUp, ShieldAlert } from "lucide-react";
import { IntakeQuestionnaire } from "@/components/intake/intake-questionnaire";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { detectModality, proposeForModality, type IntakeProposal } from "@/lib/intake/mock";
import { projectStore } from "@/lib/projects/store";
import type { Dataset } from "@/lib/projects/types";

export interface AnalyzeArgs {
  datasetId: string;
  file: File;
  proposal: IntakeProposal | null;
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
  const [dragging, setDragging] = React.useState(false);

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
      <div className="space-y-4">
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) ingest(f);
          }}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-input bg-card/40 px-6 py-8 text-center transition-colors",
            "hover:border-primary/50 hover:bg-card/70",
            dragging && "border-primary bg-accent/40",
          )}
        >
          <input
            type="file"
            accept=".h5ad,.csv,.tsv,.mzML"
            className="sr-only"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) ingest(f);
            }}
          />
          <span className="grid size-10 place-items-center rounded-full border border-border bg-background/70 text-primary">
            <FileUp className="size-5" />
          </span>
          <p className="text-sm font-medium text-foreground">Drop a dataset or click to browse</p>
          <p className="tabular text-xs text-muted-foreground">.h5ad · .csv · .tsv · .mzML</p>
        </label>

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
                })
              }
              onSkip={() => onAnalyze({ datasetId: active.dataset.id, file: active.file, proposal: null })}
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
