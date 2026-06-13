"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Database, LayoutGrid, Redo2, Sparkles, Trash2, Undo2, Wrench } from "lucide-react";
import { DataPanel, type AnalyzeArgs } from "./data-panel";
import { WorkbenchPanel } from "./workbench-panel";
import { PublishConfidence } from "./publish-confidence";
import { Pipeline, type StageKey, type StageState } from "@/components/pipeline";
import { EditorWorkspace } from "@/components/figure/editor-workspace";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useFigureStore } from "@/hooks/use-figure-store";
import { getSkill } from "@/lib/catalog/seed";
import type { IntakeProposal, ProposedStep } from "@/lib/intake/mock";
import { projectStore, select, useProjects } from "@/lib/projects/store";
import { runSkill, runtimeSkillId, type SkillGuardrail, type SkillMethods, type SkillProvenance } from "@/lib/skills-api";

type Tab = "overview" | "data" | "workbench" | "figure";

export function ProjectWorkspace({ projectId }: { projectId: string }) {
  const router = useRouter();
  const state = useProjects();
  const project = select.project(state, projectId);
  const datasets = select.datasets(state, projectId);
  const installs = select.installs(state, projectId);
  const figures = select.figures(state, projectId);

  const figure = useFigureStore();
  const [tab, setTab] = React.useState<Tab>("overview");
  const [proposal, setProposal] = React.useState<IntakeProposal | null>(null);
  const [datasetId, setDatasetId] = React.useState<string | undefined>(undefined);
  const [lastFile, setLastFile] = React.useState<File | null>(null);
  const [running, setRunning] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  // Publish-confidence bundle for the current figure (B4): methods-text + repro record + guardrails.
  const [bundle, setBundle] = React.useState<{
    provenance?: SkillProvenance;
    methods?: SkillMethods;
    guardrails?: SkillGuardrail[];
  } | null>(null);

  // Undo / redo while editing a figure.
  React.useEffect(() => {
    if (tab !== "figure") return;
    function onKey(e: KeyboardEvent) {
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== "z") return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      e.preventDefault();
      if (e.shiftKey) figure.redo();
      else figure.undo();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [tab, figure]);

  const runFlow = React.useCallback(
    async (step: ProposedStep) => {
      setRunning(step.skillId);
      setError(null);
      try {
        const file = lastFile ?? new File(["mock"], datasets.find((d) => d.id === datasetId)?.filename ?? "data.csv");
        const res = await runSkill(runtimeSkillId(step.skillId), file, step.params);
        figure.init(res.figure);
        setBundle({ provenance: res.provenance, methods: res.methods, guardrails: res.guardrails });
        const name = getSkill(step.skillId)?.name ?? step.skillId;
        projectStore.addFigure(projectId, { title: `${name} — figure`, datasetId, skillId: step.skillId });
        setTab("figure");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Run failed. Please try again.");
      } finally {
        setRunning(null);
      }
    },
    [datasetId, datasets, figure, lastFile, projectId],
  );

  function onAnalyze({ datasetId: id, file, proposal: p }: AnalyzeArgs) {
    setDatasetId(id);
    setLastFile(file);
    setProposal(p);
    setTab("workbench");
  }

  if (!project) {
    return (
      <div className="grid h-full place-items-center p-10 text-center">
        <div className="space-y-2">
          <p className="text-sm font-medium text-foreground">Project not found</p>
          <Button variant="outline" size="sm" onClick={() => router.push("/")}>
            Back to Home
          </Button>
        </div>
      </div>
    );
  }

  const stageStates: Partial<Record<StageKey, StageState>> = {
    data: datasets.length > 0 ? "done" : "active",
    skill: installs.length > 0 ? "done" : datasets.length > 0 ? "active" : "todo",
    figure: figures.length > 0 ? "done" : installs.length > 0 ? "active" : "todo",
    publish: figures.length > 0 ? "active" : "todo",
  };

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col px-6 py-8 lg:px-10">
      {/* header */}
      <div className="flex flex-wrap items-center gap-3">
        <span
          aria-hidden
          className="size-3.5 rounded-[4px] ring-1 ring-inset ring-black/20"
          style={{ backgroundColor: project.color }}
        />
        <input
          key={project.id}
          defaultValue={project.name}
          aria-label="Project name"
          onBlur={(e) => projectStore.renameProject(project.id, e.target.value.trim() || project.name)}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          }}
          className="min-w-0 flex-1 rounded-md border border-transparent bg-transparent px-1.5 py-1 text-lg font-semibold tracking-tight text-foreground outline-none hover:border-border focus-visible:border-ring/60 focus-visible:bg-background/40"
        />
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground hover:text-destructive"
          onClick={() => {
            if (confirm(`Delete "${project.name}"? This cannot be undone.`)) {
              projectStore.deleteProject(project.id);
              router.push("/");
            }
          }}
        >
          <Trash2 /> Delete
        </Button>
      </div>

      {error && (
        <div role="alert" className="mt-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className="mt-4 flex min-h-0 flex-1 flex-col">
        <TabsList className="self-start">
          <TabsTrigger value="overview"><LayoutGrid /> Overview</TabsTrigger>
          <TabsTrigger value="data"><Database /> Data{datasets.length > 0 ? ` · ${datasets.length}` : ""}</TabsTrigger>
          <TabsTrigger value="workbench"><Wrench /> Workbench{installs.length > 0 ? ` · ${installs.length}` : ""}</TabsTrigger>
          <TabsTrigger value="figure"><Sparkles /> Figure</TabsTrigger>
        </TabsList>

        <div className="mt-5 min-h-0 flex-1">
          <TabsContent value="overview">
            {/* Live pipeline tracker — the project's place in the Selom loop. */}
            <Card className="p-6 lg:p-8">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold tracking-tight text-foreground">Project pipeline</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {figures.length > 0
                      ? "Keep editing, or publish with the methods text and provenance attached."
                      : datasets.length > 0
                        ? "Next: review the proposed pipeline in the Workbench and run a skill."
                        : "Start by dropping a dataset — Selom cleans it and asks a few questions."}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant={figures.length > 0 ? "outline" : "default"}
                  onClick={() => setTab(datasets.length === 0 ? "data" : figures.length > 0 ? "figure" : "workbench")}
                >
                  {datasets.length === 0 ? "Drop data" : figures.length > 0 ? "Open figure" : "Open Workbench"}
                  <ArrowRight />
                </Button>
              </div>
              <Pipeline variant="progress" states={stageStates} className="mt-10" />
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
                      onClick={() => setTab("figure")}
                      className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-accent/40"
                    >
                      <Sparkles className="size-4 shrink-0 text-primary" />
                      <span className="truncate text-sm text-foreground">{f.title}</span>
                      <span className="tabular ml-auto text-[11px] text-muted-foreground">
                        {getSkill(f.skillId ?? "")?.name ?? "figure"}
                      </span>
                    </button>
                  ))}
                </Card>
              </div>
            )}
          </TabsContent>

          <TabsContent value="data">
            <DataPanel projectId={project.id} datasets={datasets} onAnalyze={onAnalyze} />
          </TabsContent>

          <TabsContent value="workbench">
            <WorkbenchPanel installs={installs} proposal={proposal} running={running} onRun={runFlow} />
          </TabsContent>

          <TabsContent value="figure" className="h-full">
            {figure.spec ? (
              <div className="flex h-full flex-col gap-3">
                <div className="flex items-center gap-1.5">
                  <Button variant="ghost" size="icon" disabled={!figure.canUndo} onClick={figure.undo} aria-label="Undo">
                    <Undo2 />
                  </Button>
                  <Button variant="ghost" size="icon" disabled={!figure.canRedo} onClick={figure.redo} aria-label="Redo">
                    <Redo2 />
                  </Button>
                  <span className="ml-2 text-xs text-muted-foreground">Editing live — every change is a JSON-Patch.</span>
                  <Button variant="ghost" size="sm" className="ml-auto" onClick={() => { figure.reset(); setBundle(null); setTab("workbench"); }}>
                    New figure
                  </Button>
                </div>
                <PublishConfidence provenance={bundle?.provenance} methods={bundle?.methods} guardrails={bundle?.guardrails} />
                <div className="flex min-h-[520px] flex-1 overflow-hidden rounded-xl border border-border bg-background">
                  <EditorWorkspace store={figure} />
                </div>
              </div>
            ) : (
              <Card className="grid h-full min-h-[320px] place-items-center p-10 text-center">
                <div className="max-w-sm space-y-2">
                  <Sparkles className="mx-auto size-6 text-muted-foreground" />
                  <p className="text-sm font-medium text-foreground">No figure yet</p>
                  <p className="text-xs text-muted-foreground">
                    Run a skill from the Workbench and the editable figure appears here.
                  </p>
                  <Button variant="outline" size="sm" onClick={() => setTab("workbench")}>
                    Go to Workbench
                  </Button>
                </div>
              </Card>
            )}
          </TabsContent>
        </div>
      </Tabs>
    </div>
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
