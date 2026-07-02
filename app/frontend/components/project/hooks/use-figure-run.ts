"use client";

import * as React from "react";
import { getSkill } from "@/lib/catalog/seed";
import { deriveFigureModel } from "@/lib/figure/figure-model";
import { captureLabels, carryLabels, type LabelAnnotation } from "@/lib/volcano/labels";
import { projectStore } from "@/lib/projects/store";
import type { Dataset, Figure } from "@/lib/projects/types";
import type { ParamValue } from "@/lib/lineage/diff";
import type { ProposedStep } from "@/lib/intake/mock";
import type { FigureStore } from "@/hooks/use-figure-store";
import {
  DataCheckError,
  runSkill,
  runSkillByDataset,
  runtimeSkillId,
  type DataCheck,
  type SkillParams,
  type SkillProvenance,
} from "@/lib/skills/api";
import { applyAiActions } from "@/lib/ai/api";
import type { AiActionDelta } from "@/lib/ai/types";
import type { RailView } from "../workrail";

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

type Blocked = { check: DataCheck; step: ProposedStep } | null;
type NeedData = { datasetId?: string } | null;

interface UseFigureRunArgs {
  projectId: string;
  /** The live figure-edit store — fresh runs + re-runs seed it via figure.init. */
  figure: FigureStore;
  datasets: Dataset[];
  /** The dataset picked for a fresh run (falls back to the project's first). */
  datasetId: string | undefined;
  designFile: File | null;
  /** This session's real uploaded bytes (cleared on reload). */
  lastFile: File | null;
  /** Mock mode lets a run fabricate placeholder bytes (the MSW stub ignores them). */
  mockMode: boolean;
  /** The open figure — origin for re-run / sweep / edited-inputs re-run. */
  activeFigure: Figure | undefined;
  activeFigureId: string | null;
  /** Injected routing setters (useWorkspaceView) — runs navigate by writing these. */
  setActiveFigureId: React.Dispatch<React.SetStateAction<string | null>>;
  setView: React.Dispatch<React.SetStateAction<RailView>>;
  setCompareIds: React.Dispatch<React.SetStateAction<string[]>>;
}

export interface FigureRun {
  running: string | null;
  error: string | null;
  blocked: Blocked;
  needData: NeedData;
  setBlocked: React.Dispatch<React.SetStateAction<Blocked>>;
  setNeedData: React.Dispatch<React.SetStateAction<NeedData>>;
  runFlow: (step: ProposedStep, opts?: { override?: boolean }) => Promise<void>;
  rerunFigure: (fig: Figure) => Promise<void>;
  runSweep: (param: string, values: ParamValue[]) => Promise<void>;
  rerunFigureWithParams: (params: SkillParams) => Promise<void>;
  rerunFigureWithAi: (params: SkillParams, aiActions: AiActionDelta[]) => Promise<void>;
}

/**
 * The skill-run engine for ProjectWorkspace (§3C): a fresh run + the three re-run flavours
 * (stale re-run / parameter sweep / edited-inputs re-run), plus their shared run state
 * (running / error / blocked / needData). Each persists a durable figure record and
 * navigates by writing the injected useWorkspaceView setters. Lifted out of the
 * orchestrator verbatim — same control flow, same useCallback dependency sets (extended
 * only with the now-injected routing setters).
 */
export function useFigureRun({
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
}: UseFigureRunArgs): FigureRun {
  const [running, setRunning] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  // The is-my-data-clean guardrail tripped (HTTP 422, P1c/D-e5): the run was halted by a
  // block-severity QC problem. Holds the verdict + the step so "Review & run anyway" can re-run
  // with override. Cleared at the start of every run.
  const [blocked, setBlocked] = React.useState<Blocked>(null);
  // A run was attempted on a dataset whose bytes aren't in this session (re-opened after reload),
  // against a real backend — so there's nothing real to send. Instead of POSTing a placeholder
  // file that the skill can't read (a confusing failure), we halt and prompt a re-upload.
  const [needData, setNeedData] = React.useState<NeedData>(null);

  // Resolve the bytes a run will send: this session's real upload, or a placeholder ONLY in mock
  // mode (the MSW stub ignores bytes). Against a real backend with no session bytes → null, so the
  // caller prompts a re-upload rather than POSTing an unreadable placeholder.
  const resolveRunFile = React.useCallback(
    (dataset?: { filename?: string }): File | null =>
      lastFile ?? (mockMode ? new File(["mock"], dataset?.filename ?? "data.csv") : null),
    [lastFile, mockMode],
  );

  // Capture the OPEN figure's hand-picked gene labels iff it's a volcano (the geneLabels capability), so
  // a re-run can re-anchor them onto the fresh backend spec — they'd otherwise be lost (the auto top-N
  // labels are a text trace, not annotations). generalization-spec §H follow-up. Non-volcano → [].
  const captureCarryLabels = React.useCallback(
    (): LabelAnnotation[] =>
      figure.spec && deriveFigureModel(figure.spec).capabilities.geneLabels ? captureLabels(figure.spec) : [],
    [figure],
  );

  const runFlow = React.useCallback(
    async (step: ProposedStep, opts: { override?: boolean } = {}) => {
      setError(null);
      setBlocked(null);
      setNeedData(null);
      // Attach the project's dataset even on the demo deep-link (no explicit pick),
      // so produced figures have a dataset to compute staleness against.
      const dsId = datasetId ?? datasets[0]?.id;
      const dataset = dsId ? datasets.find((d) => d.id === dsId) : undefined;
      // WS2.1 — close the upload→run→save loop: an uploaded dataset (bytes in the store) runs from its
      // dataset_id, so no multipart re-upload and no re-upload prompt after reload. AI actions + a
      // design sheet can't ride run-from-dataset_id → those stay on the multipart path.
      const useDataset = !step.aiActions?.length && !designFile && !!dataset?.uploaded;
      let file: File | null = null;
      if (!useDataset) {
        file = resolveRunFile(dataset);
        if (!file) {
          setNeedData({ datasetId: dsId });   // re-opened dataset, real backend → prompt re-upload
          return;
        }
      }
      setRunning(step.skillId);
      try {
        // Layer A 2b: an AI-refined design (confirmed unchanged) carries the set_design delta on the
        // step → route THIS fresh run through /ai/apply so the figure gets provenance.actions[] (✨),
        // exactly like a figure-data AI re-run. Deterministic result is identical (same _execute_skill_run
        // + posted params); the chokepoint stamps the trusted actor. Else the plain human run.
        const res = useDataset
          ? await runSkillByDataset(runtimeSkillId(step.skillId), dataset!.id, step.params, opts)
          : step.aiActions?.length
          ? await applyAiActions(runtimeSkillId(step.skillId), file!, step.params, step.aiActions, {
              override: opts.override,
              design: designFile,
            })
          : await runSkill(runtimeSkillId(step.skillId), file!, step.params, designFile, opts);
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
    [datasetId, datasets, figure, resolveRunFile, designFile, projectId, setActiveFigureId, setView],
  );

  // Re-run a (stale) figure: replay its skill with the SAME params against the
  // dataset's CURRENT bytes, persisting a NEW version (`parentFigureId`). The prior is
  // retained, never mutated (Pillar 1). The new version stamps the current data
  // version, so it reads fresh while the prior stays stale.
  const rerunFigure = React.useCallback(
    async (fig: Figure) => {
      if (!fig.skillId || !fig.provenance) return;
      setError(null);
      setNeedData(null);
      const dataset = fig.datasetId ? datasets.find((d) => d.id === fig.datasetId) : undefined;
      // WS2.1: re-run an uploaded dataset from its dataset_id (no re-upload prompt after reload).
      const useDataset = !designFile && !!dataset?.uploaded;
      let file: File | null = null;
      if (!useDataset) {
        file = resolveRunFile(dataset);
        if (!file) {
          setNeedData({ datasetId: fig.datasetId });
          return;
        }
      }
      // Persist hand-picked gene labels across the re-run, but only when re-running the figure that's
      // actually open in the editor (else figure.spec is a different figure's labels).
      const carryPrev = fig.id === activeFigureId ? captureCarryLabels() : [];
      setRunning(fig.skillId);
      try {
        const res = useDataset
          ? await runSkillByDataset(runtimeSkillId(fig.skillId), dataset!.id, fig.provenance.params)
          : await runSkill(runtimeSkillId(fig.skillId), file!, fig.provenance.params, designFile);
        const nextSpec = carryPrev.length ? carryLabels(res.figure, carryPrev) : res.figure;
        const saved = projectStore.addFigure(projectId, {
          title: fig.title,
          datasetId: fig.datasetId,
          skillId: fig.skillId,
          spec: nextSpec,
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
        figure.init(nextSpec);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Re-run failed. Please try again.");
      } finally {
        setRunning(null);
      }
    },
    [activeFigureId, captureCarryLabels, datasets, resolveRunFile, designFile, figure, projectId, setActiveFigureId],
  );

  // Parameter sweep (S3.1): run the open figure's skill once per value of a chosen
  // param (holding the rest fixed) → N linked sibling versions sharing the figure as
  // parent. Lands in the compare view so the sweep is immediately legible.
  const runSweep = React.useCallback(
    async (param: string, values: ParamValue[]) => {
      const origin = activeFigure;
      if (!origin?.skillId) return;
      setError(null);
      setNeedData(null);
      const dataset = origin.datasetId ? datasets.find((d) => d.id === origin.datasetId) : undefined;
      // WS2.1: sweep an uploaded dataset from its dataset_id (no re-upload for the N runs).
      const useDataset = !designFile && !!dataset?.uploaded;
      let file: File | null = null;
      if (!useDataset) {
        file = resolveRunFile(dataset);
        if (!file) {
          setNeedData({ datasetId: origin.datasetId });
          return;
        }
      }
      setRunning(origin.skillId);
      // The non-swept params hold at the figure's recorded config; the backend fills any
      // gap with the skill defaults, so a provenance-less origin sweeps from {} safely.
      const base = origin.provenance?.params ?? {};
      const saved: Figure[] = [];
      try {
        for (const value of values) {
          const params = { ...base, [param]: value };
          const res = useDataset
            ? await runSkillByDataset(runtimeSkillId(origin.skillId), dataset!.id, params)
            : await runSkill(runtimeSkillId(origin.skillId), file!, params, designFile);
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
    [activeFigure, datasets, resolveRunFile, designFile, figure, projectId, setActiveFigureId, setCompareIds, setView],
  );

  // Re-run the open figure from the Figure-data stage with EDITED inputs (P2): replay its
  // skill with new params → a NEW linked version (`parentFigureId`), the original kept.
  // Mirrors `rerunFigure`/`runSweep`; lands on the figure view with the new version open.
  const rerunFigureWithParams = React.useCallback(
    async (params: SkillParams) => {
      const origin = activeFigure;
      if (!origin?.skillId) return;
      setError(null);
      setBlocked(null);
      setNeedData(null);
      const dataset = origin.datasetId ? datasets.find((d) => d.id === origin.datasetId) : undefined;
      // WS2.1: re-run (edited inputs) an uploaded dataset from its dataset_id (no re-upload).
      const useDataset = !designFile && !!dataset?.uploaded;
      let file: File | null = null;
      if (!useDataset) {
        file = resolveRunFile(dataset);
        if (!file) {
          setNeedData({ datasetId: origin.datasetId });
          return;
        }
      }
      // Persist hand-picked gene labels across the re-run (origin is the open figure → figure.spec is
      // its spec): the fresh backend spec has none, so re-anchor them onto it (generalization-spec §H).
      const carryPrev = captureCarryLabels();
      setRunning(origin.skillId);
      try {
        const res = useDataset
          ? await runSkillByDataset(runtimeSkillId(origin.skillId), dataset!.id, params)
          : await runSkill(runtimeSkillId(origin.skillId), file!, params, designFile);
        const nextSpec = carryPrev.length ? carryLabels(res.figure, carryPrev) : res.figure;
        const saved = projectStore.addFigure(projectId, {
          title: origin.title,
          datasetId: origin.datasetId,
          skillId: origin.skillId,
          spec: nextSpec,
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
        figure.init(nextSpec);
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
    [activeFigure, captureCarryLabels, datasets, resolveRunFile, designFile, figure, projectId, setActiveFigureId],
  );

  // Re-run the open figure with USER-APPROVED AI actions (S5): the SAME path as
  // `rerunFigureWithParams`, but POSTed through `/ai/apply` so the produced figure carries
  // `provenance.actions[]` (the actor-tagged audit log the ✨ markers + Activity feed read from).
  // The deterministic run is identical (same `_execute_skill_run`) — "AI compiles away": a plain
  // re-run from the recorded params reproduces it with no gateway. The origin figure's proposal
  // queue is consumed on success (its durable proof becomes the new figure's provenance).
  const rerunFigureWithAi = React.useCallback(
    async (params: SkillParams, aiActions: AiActionDelta[]) => {
      const origin = activeFigure;
      if (!origin?.skillId) return;
      // Nothing AI-approved (all proposals reverted) → fall back to the plain edited-inputs re-run.
      if (aiActions.length === 0) return rerunFigureWithParams(params);
      setError(null);
      setBlocked(null);
      setNeedData(null);
      const dataset = origin.datasetId ? datasets.find((d) => d.id === origin.datasetId) : undefined;
      const file = resolveRunFile(dataset);
      if (!file) {
        setNeedData({ datasetId: origin.datasetId });
        return;
      }
      const carryPrev = captureCarryLabels();
      setRunning(origin.skillId);
      try {
        const res = await applyAiActions(runtimeSkillId(origin.skillId), file, params, aiActions, {
          design: designFile,
        });
        const nextSpec = carryPrev.length ? carryLabels(res.figure, carryPrev) : res.figure;
        const saved = projectStore.addFigure(projectId, {
          title: origin.title,
          datasetId: origin.datasetId,
          skillId: origin.skillId,
          spec: nextSpec,
          provenance: stampDataVersion(res.provenance, dataset),
          methods: res.methods,
          legend: res.legend,
          guardrails: res.guardrails,
          table: res.table ?? undefined,
          dataCheck: res.dataCheck,
          dataFit: res.dataFit ?? undefined,
          parentFigureId: origin.id,
          variantLabel: "AI-assisted",
        });
        projectStore.setFigureProposals(origin.id, []);
        setActiveFigureId(saved.id);
        figure.init(nextSpec);
      } catch (e) {
        if (e instanceof DataCheckError)
          setBlocked({ check: e.dataCheck, step: { skillId: origin.skillId, params, rationale: "", confidence: 0 } });
        else setError(e instanceof Error ? e.message : "AI re-run failed. Please try again.");
      } finally {
        setRunning(null);
      }
    },
    [activeFigure, rerunFigureWithParams, captureCarryLabels, datasets, resolveRunFile, designFile, figure, projectId, setActiveFigureId],
  );

  return {
    running,
    error,
    blocked,
    needData,
    setBlocked,
    setNeedData,
    runFlow,
    rerunFigure,
    runSweep,
    rerunFigureWithParams,
    rerunFigureWithAi,
  };
}
