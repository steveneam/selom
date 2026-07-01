"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Trash2 } from "lucide-react";
import { DataPanel, type AnalyzeArgs } from "./data-panel";
import { DataCheckPanel } from "./data-check";
import { CompareView } from "./compare-view";
import { Workrail, type FigureNode, type Lineage, type RailView } from "./workrail";
import type { StageKey, StageState } from "@/components/pipeline";
import { Button } from "@/components/ui/button";
import { useFigureStore } from "@/hooks/use-figure-store";
import { getSkill } from "@/lib/catalog/seed";
import { deriveFigureModel } from "@/lib/figure/figure-model";
import {
  labelableGenes,
  labeledGenes,
  toggleGeneLabelOps,
  toggleLabelOps,
  type GeneLabelPoint,
} from "@/lib/volcano/labels";
import type { StatsLabeling } from "./stats-panel";
import type { IntakeProposal, ProposedStep } from "@/lib/intake/mock";
import { projectStore, select, useProjects } from "@/lib/projects/store";
import { useWorkspace, workspaceStore, wselect } from "@/lib/workspace/store";
import type { Figure } from "@/lib/projects/types";
import { figureStaleness } from "@/lib/lineage/staleness";
import { figureTable } from "@/lib/lineage/figure-table";
import { versionFamily } from "@/lib/lineage/versions";
import { familyColorMap } from "@/lib/lineage/family";
import { subscribeIntent, takeIntent, type WorkspaceTab } from "@/lib/workspace/intent";
import { pushUndo } from "@/lib/workspace/undo";
import { useWorkspaceView } from "./hooks/use-workspace-view";
import { useFigureCrud } from "./hooks/use-figure-crud";
import { useFigureRun } from "./hooks/use-figure-run";
import { useFigureDataStaging } from "./hooks/use-figure-data-staging";
import { useAiHelpers } from "./hooks/use-ai-helpers";
import { AiPanel } from "@/components/ai/ai-panel";
import { EmptyState } from "./views/empty-state";
import { ProjectOverview } from "./views/project-overview";
import { FigureView } from "./views/figure-view";
import { FigureDataView } from "./views/figure-data-view";
import { SkillView, type Preselect } from "./views/skill-view";
import { StatsView } from "./views/stats-view";

/** Map a command-palette intent's tab onto the workrail's view model (Pillar 1, S2.3). */
function viewFromTab(tab: WorkspaceTab): RailView {
  return tab === "overview" ? "home" : tab === "workbench" ? "skill" : tab;
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
  // The workrail routing state (Pillar 1, S2.3) — view + the figure/dataset/compare
  // focus. Extracted into useWorkspaceView; the run + CRUD hooks below write it through
  // these setters.
  const {
    view,
    setView,
    activeFigureId,
    setActiveFigureId,
    activeDatasetId,
    setActiveDatasetId,
    compareIds,
    setCompareIds,
  } = useWorkspaceView();
  // A skill the command palette / Gene Sets surface asked to pre-select in the
  // Workbench, with optional param prefills. The nonce makes a repeat request (same
  // skill, again) a fresh prop for the panel.
  const [preselect, setPreselect] = React.useState<Preselect | null>(null);
  const [proposal, setProposal] = React.useState<IntakeProposal | null>(null);
  const [datasetId, setDatasetId] = React.useState<string | undefined>(undefined);
  const [lastFile, setLastFile] = React.useState<File | null>(null);
  // The dataset the workbench is acting on. Its persisted data-aware route (Slice 2) sources the
  // data-fit "Recommended for your data" chips + the route composer's data context — read on load,
  // so the recommendations survive reload (no longer tied to an in-session proposal).
  const workbenchDataset = React.useMemo(
    () => datasets.find((d) => d.id === datasetId) ?? null,
    [datasets, datasetId],
  );
  const [designFile, setDesignFile] = React.useState<File | null>(null);
  // A file dropped on the Overview hub — handed to the Data tab to ingest + intake.
  const [incomingFile, setIncomingFile] = React.useState<File | null>(null);
  // The dataset the user is re-uploading bytes for (C5): the next file dropped in the Data tab
  // REFILLS this existing dataset instead of spawning a duplicate. Set from the lost-bytes banner.
  const [reattachId, setReattachId] = React.useState<string | null>(null);
  // When the export popover is open, the page dims+blurs behind it but the figure
  // artboard stays crisp (it's the subject of the export) — see EditorWorkspace `elevated`.
  const [exportOpen, setExportOpen] = React.useState(false);
  // AI panel (S5) — the right-dock with the Activity feed + the capability-gap backlog.
  const [aiPanelOpen, setAiPanelOpen] = React.useState(false);
  // The open figure (owns the AI-proposal queue + the staged figure-data base) and its source dataset.
  const activeFigure = activeFigureId ? figures.find((f) => f.id === activeFigureId) : undefined;
  const activeDataset = activeFigure?.datasetId ? datasets.find((d) => d.id === activeFigure.datasetId) : undefined;
  // Figure-data staging (§3C decomposition) — the STAGED inputs (a dot drag + the numeric Marks/Threshold
  // editors all write one `fdParams`), the live preview, the a/b-label toggle, and the deterministic
  // Auto-tune, lifted into a cohesive hook. Behaviour is this root's verbatim; the scope-reset happens
  // DURING render (derive-don't-sync) so a figure switch never flashes the prior figure's staged marks.
  const {
    fdParams,
    setFdParams,
    fdBaseParams,
    fdScope,
    fdDirty,
    previewSpec,
    markLabelsShown,
    setMarkLabelsShown,
    onMarkMove,
    onThresholdChange,
    autoTune,
  } = useFigureDataStaging({ activeFigure, activeFigureId, activeDataset, figure });
  // Publish-confidence bundle for the open figure (B4): methods-text + repro record +
  // guardrails. Derived from the persisted record (Pillar 1) so it survives reload —
  // no longer transient React state.
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
  const staleness = activeFigure
    ? figureStaleness(activeFigure, { sha256: activeDataset?.currentSha256 })
    : { stale: false, reasons: [] };
  const mockMode = process.env.NEXT_PUBLIC_API_MOCKING === "enabled";
  // Re-run needs the dataset bytes: present this session (lastFile) or fabricated in
  // mock mode; with neither (e.g. after reload against a real backend) it's disabled.
  const canRerun = !!activeFigure?.skillId && !!activeFigure?.provenance && (lastFile != null || mockMode);
  // The skill-run engine (§3C): a fresh run + the three re-run flavours + their shared run
  // state. It persists durable figure records and navigates by writing the routing setters.
  const { running, error, blocked, needData, setBlocked, setNeedData, runFlow, rerunFigure, runSweep, rerunFigureWithParams, rerunFigureWithAi } =
    useFigureRun({
      projectId,
      figure,
      datasets,
      datasetId,
      designFile,
      lastFile,
      mockMode,
      activeFigure,
      activeFigureId,
      setActiveFigureId,
      setView,
      setCompareIds,
    });

  // ── AI Helpers (S5) — orchestration lifted into a cohesive hook (§3C decomposition: state +
  // handlers out, rendering stays here). The panel open/close is UI state and stays local (above). ──
  const {
    aiProposals,
    aiCounter,
    aiTurns,
    acceptAiProposal,
    dismissAiProposal,
    revertAiProposal,
    addAiProposals,
    rerunPending,
    resetFdToBase,
  } = useAiHelpers({
    activeFigure,
    activeFigureId,
    figures,
    fdParams,
    fdBaseParams,
    setFdParams,
    setMarkLabelsShown,
    rerunFigureWithAi,
    rerunFigureWithParams,
  });

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
  }, [projectId, setView]);

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

  // Click a plotted point on a volcano (generalization-spec §H) → toggle its gene label: an INSTANT,
  // undoable annotation committed to the figure store (no re-run, unlike a threshold edit). The
  // Statistics-table Label toggle (`onToggleGeneLabel`, by gene name) writes the SAME `label_genes`
  // set — both go through the figure store, so a click and a table toggle stay in sync. Skipped on a
  // frozen (read-only) figure.
  const onToggleLabel = React.useCallback(
    (point: GeneLabelPoint) => {
      const spec = figure.spec;
      if (!spec || frozen) return;
      const ops = toggleLabelOps(spec, point);
      if (ops.length) figure.commit(ops);
    },
    [figure, frozen],
  );
  const onToggleGeneLabel = React.useCallback(
    (gene: string) => {
      const spec = figure.spec;
      if (!spec || frozen) return;
      const ops = toggleGeneLabelOps(spec, gene);
      if (ops.length) figure.commit(ops);
    },
    [figure, frozen],
  );

  // Gene-labelling for the Statistics table (generalization-spec §H): present only for a volcano (the
  // geneLabels capability) open in the editor store and not frozen. The Label column reads the
  // labelled / labellable sets from the LIVE figure spec, so a canvas click and a table toggle stay in
  // lock-step; toggling writes the same shared annotation set via `onToggleGeneLabel`.
  const statsLabeling = React.useMemo((): StatsLabeling | undefined => {
    const spec = figure.spec;
    if (!spec || frozen || !activeStatsTable) return undefined;
    if (!deriveFigureModel(spec).capabilities.geneLabels) return undefined;
    const geneColumn = activeStatsTable.columns.findIndex((c) => /gene|symbol/i.test(c));
    if (geneColumn < 0) return undefined;
    return {
      geneColumn,
      labeled: labeledGenes(spec),
      labelable: labelableGenes(spec),
      onToggle: onToggleGeneLabel,
    };
  }, [figure.spec, frozen, activeStatsTable, onToggleGeneLabel]);

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
  }, [activeFigure, figure, setActiveFigureId, setView]);

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

  // C5: re-uploaded bytes refilled an EXISTING dataset — adopt them as this session's live file so
  // the figure can re-run, and clear the re-attach intent.
  function onReattach(id: string, file: File) {
    setDatasetId(id);
    setLastFile(file);
    setReattachId(null);
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

  // Open + delete handlers for figures and datasets (§3C) — they navigate by writing the
  // routing setters above and seed/reset the shared figure store.
  const { openFigure, openStats, openCompare, deleteFigure, deleteDataset } = useFigureCrud({
    figure,
    view,
    activeFigureId,
    activeDatasetId,
    setView,
    setActiveFigureId,
    setActiveDatasetId,
    setCompareIds,
  });

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

  // The dataset in focus in the Data view (picked from the rail) — the subject of the
  // context-scoped header delete.
  const focusedDataset = activeDatasetId ? datasets.find((d) => d.id === activeDatasetId) : undefined;

  return (
    <div
      className="flex h-full flex-col px-5 py-6 lg:px-7"
      // The AI panel is a fixed right-side OVERLAY (owner directive): while open it floats OVER the
      // content rather than reserving width. Content keeps its full width, so no stage is squeezed —
      // previously a `paddingRight: 376` reserve collapsed the two-column DataPanel to ~149px columns
      // (even the pre-existing data-type select clipped) whenever the panel was open at ≤~1400px. The
      // panel is a dock you open/close, so occluding the rightmost content while open is expected.
    >
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
        {/* AI Helpers (S5): the persistent ✨ toggle for the AI panel (Activity feed + capability
            backlog). Carries the pending-✨ count so attribution is visible without opening it. */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setAiPanelOpen((o) => !o)}
          aria-pressed={aiPanelOpen}
          title="AI activity — proposals, the audit trail, and the capability backlog"
          className={aiPanelOpen ? "text-stage-ai" : undefined}
        >
          {/* The ✨ glyph is the AI-attribution mark — keep it fuchsia at all times (matching the
              panel header + markers), so the entry point reads as the AI surface even when closed;
              only the "AI" word stays foreground for legibility. */}
          <Sparkles className="text-stage-ai" /> AI
          {aiProposals.length > 0 && (
            // Count ALL outstanding AI proposals (proposed-awaiting-review + accepted/staged), not
            // just the staged ones — an un-accepted suggestion is otherwise invisible until you open
            // the figure. Matches the Activity-tab badge + the panel's Pending section.
            <span
              className="ml-1 inline-flex min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-semibold tabular-nums text-stage-ai"
              style={{ backgroundColor: "color-mix(in oklab, var(--stage-ai) 16%, transparent)" }}
              aria-label={`${aiProposals.length} AI suggestion${aiProposals.length === 1 ? "" : "s"}`}
            >
              {aiProposals.length}
            </span>
          )}
        </Button>
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

      {needData && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
          <span className="leading-relaxed">
            This dataset isn&apos;t loaded in this session — its file was cleared on reload. Re-upload it
            to run the analysis on your real data.
          </span>
          <Button
            size="sm"
            variant="outline"
            className="shrink-0"
            onClick={() => {
              if (needData.datasetId) {
                setActiveDatasetId(needData.datasetId);
                setReattachId(needData.datasetId); // next drop refills THIS dataset (C5)
              }
              setNeedData(null);
              setView("data");
            }}
          >
            Re-upload in Data
          </Button>
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
            <FigureView
              figure={figure}
              activeFigure={activeFigure}
              activeDataset={activeDataset}
              frozen={frozen}
              staleness={staleness}
              canRerun={canRerun}
              running={running}
              mockMode={mockMode}
              exportOpen={exportOpen}
              setExportOpen={setExportOpen}
              activeFamily={activeFamily}
              onEditCopy={editCopy}
              onRerunFigure={rerunFigure}
              onSweep={runSweep}
              onOpenCompare={openCompare}
              onToggleFreeze={toggleFreeze}
              onMarkMove={onMarkMove}
              onToggleLabel={onToggleLabel}
              onOpenFigureData={() => setView("figuredata")}
              onNewFigure={() => {
                figure.reset();
                setActiveFigureId(null);
                setView("skill");
              }}
              onRunSkill={() => setView("skill")}
            />
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
            <FigureDataView
              activeFigure={activeFigure}
              figure={figure}
              fdParams={fdParams}
              setFdParams={setFdParams}
              fdDirty={fdDirty}
              fdScope={fdScope}
              previewSpec={previewSpec}
              markLabelsShown={markLabelsShown}
              setMarkLabelsShown={setMarkLabelsShown}
              onMarkMove={onMarkMove}
              onThresholdChange={onThresholdChange}
              autoTune={autoTune}
              aiProposals={aiProposals}
              aiCounter={aiCounter}
              running={running}
              resetFdToBase={resetFdToBase}
              rerunPending={rerunPending}
              acceptAiProposal={acceptAiProposal}
              dismissAiProposal={dismissAiProposal}
              revertAiProposal={revertAiProposal}
              addAiProposals={addAiProposals}
              onOpenFigure={openFigure}
              onPickSkill={pickSuggestedSkill}
              onRunSkill={() => setView("skill")}
            />
          ) : (
            <div className="min-h-0 flex-1 overflow-y-auto pr-0.5">
              {view === "home" && (
                <ProjectOverview
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
                  reattachDatasetId={reattachId}
                  onReattach={onReattach}
                />
              )}

              {view === "skill" && (
                <SkillView
                  installs={installs}
                  proposal={proposal}
                  workbenchDataset={workbenchDataset}
                  running={running}
                  onRun={runFlow}
                  preselect={preselect}
                  setPreselect={setPreselect}
                />
              )}

              {view === "stats" && (
                <StatsView
                  activeFigure={activeFigure}
                  table={activeStatsTable}
                  labeling={statsLabeling}
                  onOpenFigure={openFigure}
                  onRunSkill={() => setView("skill")}
                />
              )}
            </div>
          )}
        </main>
      </div>
      {/* AI Helpers (S5): the right-dock AI panel (fixed-position → overlays consistently across
          every view; the user keeps working underneath). Activity feed + capability backlog. */}
      <AiPanel
        open={aiPanelOpen}
        onClose={() => setAiPanelOpen(false)}
        turns={aiTurns}
        proposals={aiProposals}
        aiCount={aiProposals.length}
      />
    </div>
  );
}
