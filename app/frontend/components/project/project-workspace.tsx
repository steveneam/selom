"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Lock, Redo2, RefreshCw, SlidersHorizontal, Sparkles, Table2, Trash2, Undo2 } from "lucide-react";
import { DataPanel, type AnalyzeArgs } from "./data-panel";
import { DataCheckPanel } from "./data-check";
import { FigureDataPanel } from "./figure-data-panel";
import { Dropzone } from "./dropzone";
import { WorkbenchPanel } from "./workbench-panel";
import { PublishConfidence } from "./publish-confidence";
import { StaleBadge } from "./stale-badge";
import { StatsPanel } from "./stats-panel";
import { VersionBar } from "./version-bar";
import { CompareView } from "./compare-view";
import { Workrail, type FigureNode, type Lineage, type RailView } from "./workrail";
import { Pipeline, type StageKey, type StageState } from "@/components/pipeline";
import { EditorWorkspace } from "@/components/figure/editor-workspace";
import { FigureCanvas } from "@/components/figure/figure-canvas";
import { ExportMenu } from "@/components/figure/export-menu";
import { StylePicker } from "@/components/figure/style-picker";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useFigureStore } from "@/hooks/use-figure-store";
import { getSkill } from "@/lib/catalog/seed";
import type { IntakeProposal, ProposedStep } from "@/lib/intake/mock";
import { projectStore, select, useProjects } from "@/lib/projects/store";
import { useWorkspace, workspaceStore, wselect } from "@/lib/workspace/store";
import type { Dataset, Figure } from "@/lib/projects/types";
import { figureStaleness } from "@/lib/lineage/staleness";
import { figureTable } from "@/lib/lineage/figure-table";
import { versionFamily } from "@/lib/lineage/versions";
import type { ParamValue } from "@/lib/lineage/diff";
import { datasetDisplayName, familyColorMap } from "@/lib/lineage/family";
import { readStyleStamp } from "@/lib/figure-spec";
import { DataCheckError, runSkill, runtimeSkillId, type DataCheck, type SkillParams, type SkillProvenance } from "@/lib/skills-api";
import { subscribeIntent, takeIntent, type WorkspaceTab } from "@/lib/workspace/intent";
import { pushUndo } from "@/lib/workspace/undo";

/** Map a command-palette intent's tab onto the workrail's view model (Pillar 1, S2.3). */
function viewFromTab(tab: WorkspaceTab): RailView {
  return tab === "overview" ? "home" : tab === "workbench" ? "skill" : tab;
}

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

/**
 * Stamp the figure's input hash with the dataset's CURRENT version (Pillar 1). The
 * input hash is the dataset bytes' hash; in the dogfood mock the backend hash is a
 * fixed stand-in, so we record the dataset's client-maintained version, which is what
 * staleness diffs against. For a real backend the two are equal, so this is a no-op.
 */
function stampDataVersion(
  provenance: SkillProvenance | undefined,
  dataset: Dataset | undefined,
): SkillProvenance | undefined {
  if (!provenance || !dataset?.currentSha256) return provenance;
  return { ...provenance, input: { ...provenance.input, sha256: dataset.currentSha256 } };
}

export function ProjectWorkspace({ projectId }: { projectId: string }) {
  const router = useRouter();
  const state = useProjects();
  const ws = useWorkspace();
  const project = select.project(state, projectId);
  const datasets = select.datasets(state, projectId);
  // Installs are workspace-level now (account-wide, spec D1) — every project sees every
  // installed skill. WorkspaceSkill has the {id, skillId} the workbench reads.
  const installs = wselect.skills(ws);
  const figures = select.figures(state, projectId);

  const figure = useFigureStore();
  // The workrail view (Pillar 1, S2.3) — replaces the old four tabs. The lineage rail
  // navigates: home (pipeline) / data / skill (run) / stats (a result table) / figure.
  const [view, setView] = React.useState<RailView>("home");
  // The persisted figure currently in focus (Pillar 1). Drives the editor (figure view),
  // the Statistics table (stats view), and the staleness/bundle read-out. null = nothing
  // open / fresh run.
  const [activeFigureId, setActiveFigureId] = React.useState<string | null>(null);
  // The dataset in focus in the Data view (picked from the rail) — drives the
  // context-scoped header delete ("Delete dataset").
  const [activeDatasetId, setActiveDatasetId] = React.useState<string | null>(null);
  // The version family (figure ids) shown in the compare view (S3.2).
  const [compareIds, setCompareIds] = React.useState<string[]>([]);
  // A skill the command palette / Gene Sets surface asked to pre-select in the
  // Workbench, with optional param prefills. The nonce makes a repeat request (same
  // skill, again) a fresh prop for the panel.
  const [preselect, setPreselect] = React.useState<{ id: string; n: number; params?: Record<string, string | number | boolean> } | null>(null);
  const [proposal, setProposal] = React.useState<IntakeProposal | null>(null);
  const [datasetId, setDatasetId] = React.useState<string | undefined>(undefined);
  const [lastFile, setLastFile] = React.useState<File | null>(null);
  const [designFile, setDesignFile] = React.useState<File | null>(null);
  // A file dropped on the Overview hub — handed to the Data tab to ingest + intake.
  const [incomingFile, setIncomingFile] = React.useState<File | null>(null);
  const [running, setRunning] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  // The is-my-data-clean guardrail tripped (HTTP 422, P1c/D-e5): the run was halted by a
  // block-severity QC problem. Holds the verdict + the step so "Review & run anyway" can re-run
  // with override. Cleared at the start of every run.
  const [blocked, setBlocked] = React.useState<{ check: DataCheck; step: ProposedStep } | null>(null);
  // Active journal style for the current figure (journal-styles v1) — DERIVED from the
  // spec's stamp (layout.meta.selomStyle), not held separately, so undo/redo and "New
  // figure" rewind the picker label for free. Runs come out in the Selom default.
  const activeStyle = readStyleStamp(figure.spec);
  // When the export popover is open, the page dims+blurs behind it but the figure
  // artboard stays crisp (it's the subject of the export) — see EditorWorkspace `elevated`.
  const [exportOpen, setExportOpen] = React.useState(false);
  // Publish-confidence bundle for the open figure (B4): methods-text + repro record +
  // guardrails. Derived from the persisted record (Pillar 1) so it survives reload —
  // no longer transient React state.
  const activeFigure = activeFigureId ? figures.find((f) => f.id === activeFigureId) : undefined;
  const bundle = activeFigure
    ? {
        provenance: activeFigure.provenance,
        methods: activeFigure.methods,
        legend: activeFigure.legend,
        guardrails: activeFigure.guardrails,
      }
    : null;

  // Staleness (Pillar 1): diff the open figure's stored provenance against the live
  // trigger-set. The only "live" factor we can compute in the dogfood mock is the
  // dataset's current data version; params (a re-run uses the figure's own), skill
  // version, and env aren't separately tracked here, so they're left unknown (skipped).
  const activeDataset = activeFigure?.datasetId ? datasets.find((d) => d.id === activeFigure.datasetId) : undefined;
  const staleness = activeFigure
    ? figureStaleness(activeFigure, { sha256: activeDataset?.currentSha256 })
    : { stale: false, reasons: [] };
  const mockMode = process.env.NEXT_PUBLIC_API_MOCKING === "enabled";
  // Re-run needs the dataset bytes: present this session (lastFile) or fabricated in
  // mock mode; with neither (e.g. after reload against a real backend) it's disabled.
  const canRerun = !!activeFigure?.skillId && !!activeFigure?.provenance && (lastFile != null || mockMode);
  // The Statistics table for the focused figure (stats view) — its stored table or a
  // fallback derived from its spec (D3).
  const activeStatsTable = activeFigure ? figureTable(activeFigure) : undefined;
  // Versioning (S3): the frozen "paper" flag, the open figure's version family
  // (self + siblings + ancestors), and the figures resolved for the compare view.
  const frozen = !!activeFigure?.frozen;
  const activeFamily = React.useMemo(
    () => (activeFigure ? versionFamily(figures, activeFigure.id) : []),
    [figures, activeFigure],
  );
  const compareFamily = React.useMemo(
    () => compareIds.map((id) => figures.find((f) => f.id === id)).filter((f): f is Figure => !!f),
    [compareIds, figures],
  );

  // Per-figure rail nodes (S2.3): each figure with its staleness + whether it carries a
  // Statistics table (so the Statistics section lists only substantive nodes, D3).
  const figureNodes: FigureNode[] = React.useMemo(
    () =>
      figures.map((f) => {
        const ds = f.datasetId ? datasets.find((d) => d.id === f.datasetId) : undefined;
        return {
          figure: f,
          staleness: figureStaleness(f, { sha256: ds?.currentSha256 }),
          hasStats: !!figureTable(f),
        };
      }),
    [figures, datasets],
  );
  // Stable family accent colour per dataset (Pillar 1 lineage) — its figures + stats
  // carry this colour + the dataset's live name as a source chip.
  const familyColors = React.useMemo(() => familyColorMap(datasets), [datasets]);
  // The active figure's lineage — light its source dataset + its own stats/figure nodes
  // in the rail (only while a figure or its stats is in focus).
  const lineage: Lineage =
    (view === "figure" || view === "stats" || view === "figuredata") && activeFigure
      ? { datasetId: activeFigure.datasetId, figureId: activeFigure.id }
      : {};

  // Consume a command-palette intent for this project: switch view, and (when a
  // skill was named) install it and pre-select it in the Workbench. Runs on
  // mount (intent queued just before navigation) and on every later dispatch
  // while this workspace stays mounted (same-project ⌘K actions).
  React.useEffect(() => {
    function consume() {
      const intent = takeIntent(projectId);
      if (!intent) return;
      if (intent.skillId) {
        workspaceStore.installSkill(intent.skillId);
        setPreselect((p) => ({ id: intent.skillId!, n: (p?.n ?? 0) + 1, params: intent.params }));
      }
      if (intent.tab) setView(viewFromTab(intent.tab));
    }
    consume();
    return subscribeIntent(consume);
  }, [projectId]);

  // Undo / redo while editing a figure (not on a frozen, read-only one).
  React.useEffect(() => {
    if (view !== "figure" || frozen) return;
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
  }, [view, figure, frozen]);

  // Persist in-canvas edits back to the open figure's stored spec (Pillar 1 — the
  // working spec is durable now). Debounced so a live drag (many `set`s) coalesces
  // into one write on settle; undo/redo + discrete commits persist their result too.
  // Never writes a frozen "paper" version — it's immutable (edits fork instead, D6).
  React.useEffect(() => {
    const spec = figure.spec;
    if (!activeFigureId || !spec || frozen) return;
    const id = setTimeout(() => projectStore.updateFigureSpec(activeFigureId, spec), 350);
    return () => clearTimeout(id);
  }, [figure.spec, activeFigureId, frozen]);

  const runFlow = React.useCallback(
    async (step: ProposedStep, opts: { override?: boolean } = {}) => {
      setRunning(step.skillId);
      setError(null);
      setBlocked(null);
      try {
        // Attach the project's dataset even on the demo deep-link (no explicit pick),
        // so produced figures have a dataset to compute staleness against.
        const dsId = datasetId ?? datasets[0]?.id;
        const dataset = dsId ? datasets.find((d) => d.id === dsId) : undefined;
        const file = lastFile ?? new File(["mock"], dataset?.filename ?? "data.csv");
        const res = await runSkill(runtimeSkillId(step.skillId), file, step.params, designFile, opts);
        const name = getSkill(step.skillId)?.name ?? step.skillId;
        // Persist the figure durably — full spec + the provenance bundle (the staleness
        // trigger-set, stamped with the dataset's current version). Both were transient
        // before Pillar 1, lost on reload. The legend + data-check verdict ride along too.
        const saved = projectStore.addFigure(projectId, {
          title: `${name} — figure`,
          datasetId: dsId,
          skillId: step.skillId,
          spec: res.figure,
          provenance: stampDataVersion(res.provenance, dataset),
          methods: res.methods,
          legend: res.legend,
          guardrails: res.guardrails,
          table: res.table ?? undefined,
          dataCheck: res.dataCheck,
          dataFit: res.dataFit ?? undefined,
        });
        setActiveFigureId(saved.id);
        figure.init(res.figure); // fresh spec carries no style stamp → activeStyle derives the default
        setView("figure");
      } catch (e) {
        // The is-my-data-clean guardrail (HTTP 422) → a reviewable block card + "run anyway",
        // not a generic error (P1c/D-e5).
        if (e instanceof DataCheckError) setBlocked({ check: e.dataCheck, step });
        else setError(e instanceof Error ? e.message : "Run failed. Please try again.");
      } finally {
        setRunning(null);
      }
    },
    [datasetId, datasets, figure, lastFile, designFile, projectId],
  );

  // Re-run a (stale) figure: replay its skill with the SAME params against the
  // dataset's CURRENT bytes, persisting a NEW version (`parentFigureId`). The prior is
  // retained, never mutated (Pillar 1). The new version stamps the current data
  // version, so it reads fresh while the prior stays stale.
  const rerunFigure = React.useCallback(
    async (fig: Figure) => {
      if (!fig.skillId || !fig.provenance) return;
      setRunning(fig.skillId);
      setError(null);
      try {
        const dataset = fig.datasetId ? datasets.find((d) => d.id === fig.datasetId) : undefined;
        const file = lastFile ?? new File(["mock"], dataset?.filename ?? "data.csv");
        const res = await runSkill(runtimeSkillId(fig.skillId), file, fig.provenance.params, designFile);
        const saved = projectStore.addFigure(projectId, {
          title: fig.title,
          datasetId: fig.datasetId,
          skillId: fig.skillId,
          spec: res.figure,
          provenance: stampDataVersion(res.provenance, dataset),
          methods: res.methods,
          legend: res.legend,
          guardrails: res.guardrails,
          table: res.table ?? undefined,
          dataCheck: res.dataCheck,
          dataFit: res.dataFit ?? undefined,
          parentFigureId: fig.id,
          variantLabel: "re-run",
        });
        setActiveFigureId(saved.id);
        figure.init(res.figure);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Re-run failed. Please try again.");
      } finally {
        setRunning(null);
      }
    },
    [datasets, lastFile, designFile, figure, projectId],
  );

  // Parameter sweep (S3.1): run the open figure's skill once per value of a chosen
  // param (holding the rest fixed) → N linked sibling versions sharing the figure as
  // parent. Lands in the compare view so the sweep is immediately legible.
  const runSweep = React.useCallback(
    async (param: string, values: ParamValue[]) => {
      const origin = activeFigure;
      if (!origin?.skillId) return;
      setRunning(origin.skillId);
      setError(null);
      const dataset = origin.datasetId ? datasets.find((d) => d.id === origin.datasetId) : undefined;
      // The non-swept params hold at the figure's recorded config; the backend fills any
      // gap with the skill defaults, so a provenance-less origin sweeps from {} safely.
      const base = origin.provenance?.params ?? {};
      const saved: Figure[] = [];
      try {
        for (const value of values) {
          const params = { ...base, [param]: value };
          const file = lastFile ?? new File(["mock"], dataset?.filename ?? "data.csv");
          const res = await runSkill(runtimeSkillId(origin.skillId), file, params, designFile);
          saved.push(
            projectStore.addFigure(projectId, {
              title: origin.title,
              datasetId: origin.datasetId,
              skillId: origin.skillId,
              spec: res.figure,
              provenance: stampDataVersion(res.provenance, dataset),
              methods: res.methods,
              legend: res.legend,
              guardrails: res.guardrails,
              table: res.table ?? undefined,
              dataCheck: res.dataCheck,
              dataFit: res.dataFit ?? undefined,
              parentFigureId: origin.id,
              variantLabel: `${param} = ${value}`,
            }),
          );
        }
        if (saved.length >= 2) {
          setCompareIds(saved.map((f) => f.id));
          setActiveFigureId(saved[saved.length - 1].id);
          setView("compare");
        } else if (saved.length === 1) {
          setActiveFigureId(saved[0].id);
          if (saved[0].spec) figure.init(saved[0].spec);
          setView("figure");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Sweep failed. Please try again.");
      } finally {
        setRunning(null);
      }
    },
    [activeFigure, datasets, lastFile, designFile, figure, projectId],
  );

  // Re-run the open figure from the Figure-data stage with EDITED inputs (P2): replay its
  // skill with new params → a NEW linked version (`parentFigureId`), the original kept.
  // Mirrors `rerunFigure`/`runSweep`; lands on the figure view with the new version open.
  const rerunFigureWithParams = React.useCallback(
    async (params: SkillParams) => {
      const origin = activeFigure;
      if (!origin?.skillId) return;
      setRunning(origin.skillId);
      setError(null);
      setBlocked(null);
      try {
        const dataset = origin.datasetId ? datasets.find((d) => d.id === origin.datasetId) : undefined;
        const file = lastFile ?? new File(["mock"], dataset?.filename ?? "data.csv");
        const res = await runSkill(runtimeSkillId(origin.skillId), file, params, designFile);
        const saved = projectStore.addFigure(projectId, {
          title: origin.title,
          datasetId: origin.datasetId,
          skillId: origin.skillId,
          spec: res.figure,
          provenance: stampDataVersion(res.provenance, dataset),
          methods: res.methods,
          legend: res.legend,
          guardrails: res.guardrails,
          table: res.table ?? undefined,
          dataCheck: res.dataCheck,
          dataFit: res.dataFit ?? undefined,
          parentFigureId: origin.id,
          variantLabel: "edited inputs",
        });
        setActiveFigureId(saved.id);
        figure.init(res.figure);
        // Stay on the Figure-data view: the live preview beside the inputs updates in place
        // (and the styling box shows the same shared figure when opened) — no view switch.
      } catch (e) {
        // A block-severity QC problem surfaces the same reviewable block card as a fresh run.
        if (e instanceof DataCheckError)
          setBlocked({ check: e.dataCheck, step: { skillId: origin.skillId, params, rationale: "", confidence: 0 } });
        else setError(e instanceof Error ? e.message : "Re-run failed. Please try again.");
      } finally {
        setRunning(null);
      }
    },
    [activeFigure, datasets, lastFile, designFile, figure, projectId],
  );

  // Freeze / unfreeze the open figure (S3.3, Decision D6) — tag it as the "paper"
  // version. Frozen figures are read-only; editing one forks a copy (see `editCopy`).
  const toggleFreeze = React.useCallback(() => {
    if (!activeFigure) return;
    projectStore.freezeFigure(activeFigure.id, !activeFigure.frozen);
  }, [activeFigure]);

  // Edit a frozen "paper" version: fork an editable copy (the original stays, untouched)
  // and open it in the editor.
  const editCopy = React.useCallback(() => {
    if (!activeFigure) return;
    const fork = projectStore.forkFigure(activeFigure.id, { variantLabel: "edited copy" });
    if (!fork) return;
    setActiveFigureId(fork.id);
    if (fork.spec) figure.init(fork.spec);
    setView("figure");
  }, [activeFigure, figure]);

  // Dev helper: `?demo=<skillId>` (or any truthy `?demo`) auto-runs a skill so you
  // land on a live editable figure in ONE step — for fast manual checks and the
  // Playwright gesture test, skipping the data/intake/workbench dance. Mock-mode
  // only; in a production build NEXT_PUBLIC_API_MOCKING is unset so this is dead code.
  const demoRan = React.useRef(false);
  React.useEffect(() => {
    if (demoRan.current) return;
    if (process.env.NEXT_PUBLIC_API_MOCKING !== "enabled") return;
    const sp = new URLSearchParams(window.location.search);
    if (!sp.has("demo")) return;
    const skillId = sp.get("demo") || installs[0]?.skillId;
    if (!skillId) return;
    demoRan.current = true;
    // Forward any other query params as skill params so mock-variant routes (e.g.
    // `?data_check=unsure`, which the MSW handler keys off the run query) are reachable
    // for a manual check. Dev/mock-only — dead code in a production build.
    const params: Record<string, string> = {};
    sp.forEach((v, k) => {
      if (k !== "demo") params[k] = v;
    });
    void runFlow({ skillId, params } as ProposedStep);
  }, [installs, runFlow]);

  function onAnalyze({ datasetId: id, file, proposal: p, designFile: df }: AnalyzeArgs) {
    setDatasetId(id);
    setLastFile(file);
    setDesignFile(df ?? null);
    setProposal(p);
    setView("skill");
  }

  // Pick a suggested-pipeline step from the data-check verdict (P3a guidance): install the
  // skill and pre-select it in the Workbench, ready to run on this data. Routing steps are
  // bare slugs of Selom-native skills; the catalog/install layer is keyed by `selom.<slug>`.
  function pickSuggestedSkill(skillId: string) {
    const catalogId = `selom.${skillId}`;
    workspaceStore.installSkill(catalogId);
    setPreselect((p) => ({ id: catalogId, n: (p?.n ?? 0) + 1 }));
    setView("skill");
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

  function goToStage(key: StageKey) {
    setView(key === "publish" ? "figure" : key);
  }

  // Drop a file straight onto the Overview hub: hand it to the Data view, which
  // ingests it and opens the intake — so the first thing in a new project just works.
  function dropOnOverview(file: File) {
    setIncomingFile(file);
    setView("data");
  }

  // Open a persisted figure in the editor: seed the live store from its stored spec
  // (durable now — Pillar 1). A legacy figure with no stored spec opens to a notice
  // rather than crashing (see the Figure view's empty states).
  function openFigure(f: Figure) {
    setActiveFigureId(f.id);
    if (f.spec) figure.init(f.spec);
    else figure.reset();
    setView("figure");
  }

  // Select a figure's Statistics node: focus it (drives the table read-out) without
  // disturbing the editor store.
  function openStats(f: Figure) {
    setActiveFigureId(f.id);
    setView("stats");
  }

  // Open the compare view for a version family (from the rail's family group or the
  // version bar). Needs ≥2 versions; focuses the newest so the lineage reads cleanly.
  function openCompare(ids: string[]) {
    if (ids.length < 2) return;
    setCompareIds(ids);
    setActiveFigureId(ids[ids.length - 1]);
    setView("compare");
  }

  // Delete ONE figure (only that figure — never the project). Offers an Undo rather
  // than a confirm, since the removal is reversible from the returned record. If the
  // deleted figure was open, drop back to the project home.
  function deleteFigure(f: Figure) {
    const removed = projectStore.removeFigure(f.id);
    if (!removed) return;
    pushUndo(`Deleted figure “${f.title}”`, () => projectStore.restoreFigure(removed));
    if (activeFigureId === f.id) {
      setActiveFigureId(null);
      figure.reset();
      if (view === "figure" || view === "stats") setView("home");
    }
  }

  // Delete ONE dataset (only the dataset — its figures stay, just without a live data
  // link). Undo-backed, like figure delete.
  function deleteDataset(d: Dataset) {
    const removed = projectStore.removeDataset(d.id);
    if (!removed) return;
    pushUndo(`Deleted dataset “${datasetDisplayName(removed)}”`, () => projectStore.restoreDataset(removed));
    if (activeDatasetId === d.id) setActiveDatasetId(null);
  }

  // The dataset in focus in the Data view (picked from the rail) — the subject of the
  // context-scoped header delete.
  const focusedDataset = activeDatasetId ? datasets.find((d) => d.id === activeDatasetId) : undefined;

  return (
    <div className="flex h-full flex-col px-5 py-6 lg:px-7">
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
        {/* The header's destructive action is scoped to the current view — the whole
            project can only be deleted from the Pipeline (home), never from inside a
            Data / Statistics / Figure view (owner steer). */}
        {view === "home" ? (
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-destructive"
            onClick={() => {
              const n = datasets.length;
              const m = figures.length;
              const msg =
                `Delete the entire project “${project.name}”?\n\n` +
                `This removes the whole project — its ${n} dataset${n === 1 ? "" : "s"} and ` +
                `${m} figure${m === 1 ? "" : "s"}. (To remove a single figure or dataset, open ` +
                `it and use the scoped Delete, or its rail trash icon.)\n\nYou can Undo right after.`;
              if (confirm(msg)) {
                const snap = projectStore.deleteProject(project.id);
                pushUndo(`Deleted project “${project.name}”`, () => projectStore.restoreProject(snap));
                router.push("/");
              }
            }}
          >
            <Trash2 /> Delete project
          </Button>
        ) : (view === "figure" || view === "stats") && activeFigure ? (
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-destructive"
            onClick={() => deleteFigure(activeFigure)}
          >
            <Trash2 /> Delete figure
          </Button>
        ) : view === "data" && focusedDataset ? (
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-destructive"
            onClick={() => deleteDataset(focusedDataset)}
          >
            <Trash2 /> Delete dataset
          </Button>
        ) : null}
      </div>

      {error && (
        <div role="alert" className="mt-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {blocked && (
        <div className="mt-3">
          <DataCheckPanel
            dataCheck={blocked.check}
            variant="blocked"
            skillName={getSkill(blocked.step.skillId)?.name ?? blocked.step.skillId}
            overriding={running != null}
            onOverride={() => runFlow(blocked.step, { override: true })}
            onDismiss={() => setBlocked(null)}
          />
        </div>
      )}

      {/* Workrail + main pane (Pillar 1, S2.3) — the lineage rail replaces the tabs. */}
      <div className="mt-5 flex min-h-0 flex-1 gap-6">
        <Workrail
          datasets={datasets}
          figureNodes={figureNodes}
          familyColors={familyColors}
          view={view}
          activeFigureId={activeFigureId}
          activeDatasetId={activeDatasetId}
          lineage={lineage}
          onHome={() => setView("home")}
          onSelectData={(id) => {
            setActiveDatasetId(id ?? null);
            setView("data");
          }}
          onRunSkill={() => setView("skill")}
          onSelectStats={openStats}
          onFigureData={() => setView("figuredata")}
          hasActiveFigure={!!activeFigure}
          onSelectFigure={openFigure}
          onDeleteFigure={deleteFigure}
          onRenameDataset={(id, label) => projectStore.renameDataset(id, label)}
          onCompareFamily={openCompare}
        />

        <main className="flex min-h-0 min-w-0 flex-1 flex-col">
          {view === "figure" ? (
            figure.spec ? (
              <div className="flex h-full flex-col gap-3">
                <div className="flex items-center gap-1.5">
                  {frozen ? (
                    <>
                      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-stage-figure">
                        <Lock className="size-3.5" /> Frozen — read-only
                      </span>
                      <Button size="sm" variant="outline" className="ml-1 h-7" onClick={editCopy}>
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
                        onClick={() => rerunFigure(activeFigure)}
                        disabled={!canRerun || running != null}
                        title={canRerun ? "Re-run with the current data → a new version" : "Re-attach the dataset to re-run"}
                      >
                        <RefreshCw /> {running === activeFigure.skillId ? "Re-running…" : "Re-run"}
                      </Button>
                    </div>
                  )}
                  <div className="ml-auto flex items-center gap-1.5">
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
                        onClick={() => setView("figuredata")}
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
                    <Button variant="ghost" size="sm" onClick={() => { figure.reset(); setActiveFigureId(null); setView("skill"); }}>
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
                    onSweep={runSweep}
                    onCompare={() => openCompare(activeFamily.map((f) => f.id))}
                    onToggleFreeze={toggleFreeze}
                  />
                )}
                {/* Figure-forward (§3.7): the data-check routing + data-fit verdict relocate to the
                    Figure-data stage (reachable from the toolbar / rail) so the artboard is the hero. */}
                <PublishConfidence
                  provenance={bundle?.provenance}
                  methods={bundle?.methods}
                  legend={bundle?.legend}
                  guardrails={bundle?.guardrails}
                />
                <div className="flex min-h-[520px] flex-1 overflow-hidden rounded-xl border border-border bg-background">
                  <EditorWorkspace
                    store={figure}
                    elevated={exportOpen}
                    readOnly={frozen}
                    onEditCopy={editCopy}
                    skill={
                      activeFigure?.skillId
                        ? {
                            skillName: skillDisplayName(activeFigure.skillId),
                            badge: skillBadge(activeFigure.skillId),
                            onOpenFigureData: () => setView("figuredata"),
                          }
                        : undefined
                    }
                  />
                </div>
              </div>
            ) : activeFigure && !activeFigure.spec ? (
              <EmptyState
                title="Figure spec not stored"
                body={`“${activeFigure.title}” was created before figures were saved durably, so its editable spec isn’t available. Re-run the skill to produce a fresh, editable version.`}
                action="Run a skill"
                onAction={() => setView("skill")}
              />
            ) : (
              <EmptyState
                title="No figure yet"
                body="Run a skill and the editable figure appears here."
                action="Run a skill"
                onAction={() => setView("skill")}
              />
            )
          ) : view === "compare" ? (
            compareFamily.length >= 2 ? (
              <CompareView
                family={compareFamily}
                datasets={datasets}
                familyColors={familyColors}
                onClose={() => (activeFigure ? openFigure(activeFigure) : setView("home"))}
                onOpenFigure={openFigure}
              />
            ) : (
              <EmptyState
                title="Nothing to compare"
                body="A version family needs at least two versions. Run a parameter sweep or re-run a figure to make one."
                action="Run a skill"
                onAction={() => setView("skill")}
              />
            )
          ) : view === "figuredata" ? (
            activeFigure?.skillId ? (
              // Figure-data is figure-forward: the inputs sit beside a LIVE preview of the same
              // figure the styling box edits (shared `figure` store), so tuning a param + re-run
              // updates the graph in place — no switching to the artboard to see the change.
              <div className="flex min-h-0 flex-1 gap-4">
                <div className="flex min-h-[520px] flex-1 flex-col overflow-hidden rounded-xl border border-border bg-background">
                  <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
                    <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      Live preview {running != null && <span className="text-primary">· re-running…</span>}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openFigure(activeFigure)}
                      title="Open this figure in the editor to style it"
                    >
                      <Sparkles /> Style this figure
                    </Button>
                  </div>
                  {figure.spec ?? activeFigure.spec ? (
                    <div className="relative flex min-h-0 flex-1 items-start justify-center overflow-auto p-6">
                      <div
                        className="relative flex rounded-xl border border-border bg-artboard p-3 shadow-2xl ring-1 ring-black/5"
                        style={{ width: "100%", maxWidth: "56rem", height: "min(70vh, 680px)" }}
                      >
                        <div className="min-h-0 min-w-0 flex-1">
                          <FigureCanvas spec={(figure.spec ?? activeFigure.spec)!} displayModeBar={false} />
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="grid flex-1 place-items-center p-6 text-center text-xs text-muted-foreground">
                      Re-run to generate this figure’s preview.
                    </div>
                  )}
                </div>
                <div className="w-[360px] shrink-0 overflow-y-auto pr-1">
                  <FigureDataPanel
                    key={activeFigure.id}
                    skillId={activeFigure.skillId}
                    skillName={getSkill(activeFigure.skillId)?.name ?? activeFigure.skillId}
                    baseParams={activeFigure.provenance?.params ?? {}}
                    running={running != null}
                    dataCheck={activeFigure.dataCheck}
                    dataFit={activeFigure.dataFit}
                    onRerun={rerunFigureWithParams}
                    onPickSkill={pickSuggestedSkill}
                    onPickManually={() => setView("skill")}
                  />
                </div>
              </div>
            ) : (
              <EmptyState
                title="No figure selected"
                body="Open a figure to tune the inputs behind it and re-run."
                action="Run a skill"
                onAction={() => setView("skill")}
              />
            )
          ) : (
            <div className="min-h-0 flex-1 overflow-y-auto pr-0.5">
              {view === "home" && (
                <Overview
                  datasets={datasets}
                  installs={installs}
                  figures={figures}
                  activeFigure={activeFigure}
                  stageStates={stageStates}
                  onDrop={dropOnOverview}
                  onStage={goToStage}
                  onRunSkill={() => setView("skill")}
                  onOpenFigure={openFigure}
                />
              )}

              {view === "data" && (
                <DataPanel
                  projectId={project.id}
                  datasets={datasets}
                  onAnalyze={onAnalyze}
                  incomingFile={incomingFile}
                  onIncomingConsumed={() => setIncomingFile(null)}
                />
              )}

              {view === "skill" && (
                <WorkbenchPanel installs={installs} proposal={proposal} running={running} onRun={runFlow} preselect={preselect} />
              )}

              {view === "stats" &&
                (activeFigure && activeStatsTable ? (
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="min-w-0">
                        <h2 className="flex items-center gap-2 text-base font-semibold tracking-tight text-foreground">
                          <Table2 className="size-4 text-stage-publish" />
                          {activeStatsTable.title ?? "Statistics"}
                        </h2>
                        <p className="mt-0.5 truncate text-xs text-muted-foreground">
                          from <span className="text-foreground">{activeFigure.title}</span> ·{" "}
                          {getSkill(activeFigure.skillId ?? "")?.name ?? "skill"}
                        </p>
                      </div>
                      <Button variant="outline" size="sm" onClick={() => openFigure(activeFigure)}>
                        <Sparkles /> Open figure
                      </Button>
                    </div>
                    <StatsPanel table={activeStatsTable} defaultOpen />
                  </div>
                ) : (
                  <EmptyState
                    title="No statistics selected"
                    body="Pick a Statistics node in the rail, or run a skill that computes a table (DEG, enrichment, markers)."
                    action="Run a skill"
                    onAction={() => setView("skill")}
                  />
                ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

/** The project home — the pipeline tracker (or drop-to-start when empty) + figures. */
function Overview({
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
    </>
  );
}

function EmptyState({
  title,
  body,
  action,
  onAction,
}: {
  title: string;
  body: string;
  action: string;
  onAction: () => void;
}) {
  return (
    <Card className="grid h-full min-h-[320px] place-items-center p-10 text-center">
      <div className="max-w-sm space-y-2">
        <Sparkles className="mx-auto size-6 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-muted-foreground">{body}</p>
        <Button variant="outline" size="sm" onClick={onAction}>
          {action}
        </Button>
      </div>
    </Card>
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
