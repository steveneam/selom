"use client";

import * as React from "react";
import { ArrowRight, Paintbrush } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dropzone } from "../dropzone";
import { Pipeline, type StageKey, type StageState } from "@/components/pipeline";
import { getSkill } from "@/lib/catalog/seed";
import type { Dataset, Figure } from "@/lib/projects/types";

/** The project home — the pipeline tracker (or drop-to-start when empty) + figures. */
export function ProjectOverview({
  datasets,
  installs,
  figures,
  activeFigure,
  stageStates,
  onDrop,
  onStage,
  onRunSkill,
  onOpenFigure,
}: {
  datasets: Dataset[];
  installs: { id: string }[];
  figures: Figure[];
  activeFigure: Figure | undefined;
  stageStates: Partial<Record<StageKey, StageState>>;
  onDrop: (file: File) => void;
  onStage: (key: StageKey) => void;
  onRunSkill: () => void;
  onOpenFigure: (f: Figure) => void;
}) {
  return (
    <>
      <Card className="p-6 lg:p-8">
        {datasets.length === 0 ? (
          <>
            <div className="text-center">
              <h2 className="text-xl font-semibold tracking-tight text-foreground">Let&apos;s make your first figure</h2>
              <p className="mx-auto mt-1.5 max-w-md text-sm text-muted-foreground">
                Drop a dataset to get started — Selom detects the type, cleans it, and walks you through the rest.
              </p>
            </div>
            <Dropzone
              onFile={onDrop}
              accept=".h5ad,.csv,.tsv,.mzML,.iwxdata"
              title="Drop your data here"
              hint="or click to browse — this is step one"
              formats=".h5ad · .csv · .tsv · .mzML"
              className="mx-auto mt-6 max-w-2xl"
            />
            <p className="mt-8 text-center text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
              What happens next
            </p>
            <Pipeline variant="progress" states={stageStates} onStageClick={onStage} className="mt-4" />
          </>
        ) : (
          <>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold tracking-tight text-foreground">Project pipeline</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {figures.length > 0
                    ? "Keep editing, or publish with the methods text and provenance attached."
                    : "Next: run a skill to make your first figure."}
                </p>
              </div>
              <Button
                size="sm"
                variant={figures.length > 0 ? "outline" : "default"}
                onClick={() => {
                  if (figures.length > 0) onOpenFigure(activeFigure ?? figures[figures.length - 1]);
                  else onRunSkill();
                }}
              >
                {figures.length > 0 ? "Open figure" : "Run a skill"}
                <ArrowRight />
              </Button>
            </div>
            <Pipeline variant="progress" states={stageStates} onStageClick={onStage} className="mt-10" />
          </>
        )}
      </Card>

      {/* Counts — a quiet strip, not a hero-metric grid. */}
      <Card className="mt-5 grid grid-cols-3 divide-x divide-border p-0">
        <OverviewStat label="Datasets" value={datasets.length} />
        <OverviewStat label="Installed skills" value={installs.length} />
        <OverviewStat label="Figures" value={figures.length} />
      </Card>

      {figures.length > 0 && (
        <div className="mt-8">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Figures in this project
          </h3>
          <Card className="divide-y divide-border p-0">
            {figures.slice(0, 6).map((f) => (
              <button
                key={f.id}
                onClick={() => onOpenFigure(f)}
                className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-accent/40"
              >
                <Paintbrush className="size-4 shrink-0 text-primary" />
                <span className="truncate text-sm text-foreground">{f.title}</span>
                <span className="tabular ml-auto text-[11px] text-muted-foreground">
                  {getSkill(f.skillId ?? "")?.name ?? "figure"}
                </span>
              </button>
            ))}
          </Card>
        </div>
      )}
    </>
  );
}

function OverviewStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="px-5 py-4">
      <p className="tabular text-2xl font-semibold leading-none text-foreground">{value}</p>
      <p className="mt-1.5 text-sm text-muted-foreground">{label}</p>
    </div>
  );
}
