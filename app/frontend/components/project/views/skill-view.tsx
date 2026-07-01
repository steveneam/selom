"use client";

import * as React from "react";
import { WorkbenchPanel } from "../workbench-panel";
import { AskAi } from "@/components/ai/ask-ai";
import { getSkill } from "@/lib/catalog/seed";
import { workspaceStore } from "@/lib/workspace/store";
import type { Dataset } from "@/lib/projects/types";

/** A skill the command palette / route composer asked to pre-select in the Workbench, with an
 *  optional param prefill. The nonce (`n`) makes a repeat request (same skill, again) a fresh prop. */
export type Preselect = { id: string; n: number; params?: Record<string, string | number | boolean> };

type WorkbenchProps = React.ComponentProps<typeof WorkbenchPanel>;

/**
 * The run-skill view (`view === "skill"`): the Workbench + the route-stage "Ask AI which analysis"
 * composer. Presentational — the run engine + preselect state live in the composition root; this
 * renders WorkbenchPanel with the data-aware route context and pre-selects the AI's suggested skill.
 */
export function SkillView({
  installs,
  proposal,
  running,
  onRun,
  preselect,
  setPreselect,
  workbenchDataset,
}: {
  installs: WorkbenchProps["installs"];
  proposal: WorkbenchProps["proposal"];
  running: WorkbenchProps["running"];
  onRun: WorkbenchProps["onRun"];
  preselect: Preselect | null;
  setPreselect: React.Dispatch<React.SetStateAction<Preselect | null>>;
  workbenchDataset: Dataset | null;
}) {
  return (
    <WorkbenchPanel
      installs={installs}
      proposal={proposal}
      route={
        workbenchDataset
          ? { routing: workbenchDataset.routing ?? null, dataFit: workbenchDataset.dataFit ?? null }
          : null
      }
      modality={workbenchDataset?.modality ?? null}
      running={running}
      onRun={onRun}
      preselect={preselect}
      routeComposer={
        <AskAi
          stage="route"
          mode="select"
          label="Ask AI which analysis"
          placeholder="e.g. which test for two groups?"
          hint="Pre-selects a skill below to confirm and run."
          // Data-aware (Slice 2): the active dataset's columns/kind ride along so the
          // gateway scores its suggested skill against the real data (the route-stage
          // select_skill compat gate). The engine kind lives on the persisted routing.
          context={{
            skillId: null,
            params: {},
            dataColumns: workbenchDataset?.dataFit?.columns ?? null,
            dataKind: workbenchDataset?.routing?.kind ?? null,
            dataNumericCols: workbenchDataset?.dataFit?.n_numeric_cols ?? null,
          }}
          onSelect={(skillId) => {
            const catalogId = `selom.${skillId}`;
            const skill = getSkill(catalogId);
            if (!skill) return null;
            workspaceStore.installSkill(catalogId);
            setPreselect((p) => ({ id: catalogId, n: (p?.n ?? 0) + 1 }));
            return skill.name;
          }}
        />
      }
    />
  );
}
