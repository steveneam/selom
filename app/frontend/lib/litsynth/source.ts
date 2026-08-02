"use client";

/**
 * Where a paper's write-up comes from (docs/paper-outputs/spec.md §2).
 *
 * The Write-up stage has ONE surface and two sources, resolved here so the components never branch
 * on "is this mine or an example" beyond a label:
 *
 *  - `run`       — the user's own driven reproduction. Methods are composed from the run ledger's
 *                  in-scope analysis panels via POST /methods/compose; the score comes from the
 *                  run's own scorecard.
 *  - `reference` — a published reproduction (rpgrip1 · jev · hani). Every section comes from the
 *                  paper-level routes directly.
 *
 * Pure module: no React, no fetch. `use-write-up.ts` does the loading.
 */

import type { Ledger, Panel, Scorecard } from "@/lib/reproduction/types";
import type { FigureLegend, MethodsSection, SkillRunRef } from "./api";

/** The published reproductions the reference example can draw from (`papers_api.SLUGS`). */
export const REFERENCE_SLUGS = ["rpgrip1", "jev", "hani"] as const;
export type ReferenceSlug = (typeof REFERENCE_SLUGS)[number];

export function isReferenceSlug(slug: string): slug is ReferenceSlug {
  return (REFERENCE_SLUGS as readonly string[]).includes(slug);
}

/**
 * Scopes a numeric reproduction cannot apply to — mirrors `reproduction.core.OUT_OF_SCOPE_SCOPES`.
 * A Methods section must not describe a wet-lab readout or a never-deposited demo as if Selom had
 * reproduced it, which is why the same filter runs on both sides of the wire.
 */
export const OUT_OF_SCOPE_SCOPES: ReadonlySet<string> = new Set([
  "wet_lab",
  "data_not_deposited",
  "modality_unsupported",
]);

/** A ledger panel as it actually arrives on the wire: `reproduction.core.Panel` also carries the
 *  resolved `params`, which the shared view type omits (the heatmap has no use for them). */
type PanelWithParams = Panel & { params?: Record<string, unknown> };

/** Stable key for "the same method, run the same way" — mirrors the server's sorted-key JSON. */
function fingerprint(skillId: string, params: Record<string, unknown>): string {
  const sorted = Object.keys(params)
    .sort()
    .reduce<Record<string, unknown>>((acc, k) => {
      acc[k] = params[k];
      return acc;
    }, {});
  return `${skillId}:${JSON.stringify(sorted)}`;
}

/**
 * The ordered, deduped skill runs a Methods section should describe for a driven ledger.
 *
 * A deliberate mirror of `litsynth/from_ledger.ledger_skill_runs`: figure/panel order, skipping
 * out-of-scope panels and form/claim panels with no skill, collapsing repeats of the same
 * `(skill_id, params)` to one entry in first-seen order — so a method stated once isn't repeated
 * per panel.
 *
 * The one filter it CANNOT mirror is the server's `load_skill` check (a ledger may name a
 * chart-form placeholder or an unbuilt skill, which has no prose). That resolution needs the skill
 * registry, so `POST /methods/compose` answers 400 for an unknown id — the stage surfaces that as
 * an honest error rather than guessing which panels to drop.
 */
export function runsFromLedger(ledger: Ledger | null | undefined): SkillRunRef[] {
  if (!ledger?.panels) return [];
  const runs: SkillRunRef[] = [];
  const seen = new Set<string>();
  for (const panel of ledger.panels as PanelWithParams[]) {
    if (!panel.skill_id || OUT_OF_SCOPE_SCOPES.has(panel.scope)) continue;
    const params = panel.params ?? {};
    const key = fingerprint(panel.skill_id, params);
    if (seen.has(key)) continue;
    seen.add(key);
    runs.push({ skill_id: panel.skill_id, params });
  }
  return runs;
}

/** A one-clause dataset lead for the Methods intro — mirrors `from_ledger.dataset_descriptor`. */
export function datasetDescriptor(geo: string[] | undefined, title: string | undefined): string | null {
  if (geo && geo.length > 0) return `Data deposited under ${geo.join(", ")} were analyzed`;
  return (title ?? "").trim() || null;
}

/**
 * Which source a Write-up stage is rendering.
 *
 * The `run` variant carries the already-loaded ledger rather than a run id: the stage has to fetch
 * the run anyway to know whether it survived (runs are session-scoped), and fetching it twice to
 * answer the same question would be a wasted round trip on every render of the stage.
 */
export type WriteUpSource =
  | { kind: "run"; ledger: Ledger }
  | { kind: "reference"; slug: ReferenceSlug };

/** The four sections a write-up is made of, however they were sourced. */
export interface WriteUp {
  methods: MethodsSection | null;
  legends: FigureLegend[];
  scorecard: Scorecard | null;
  /**
   * Sections this source genuinely cannot fill, so the UI can say so instead of rendering an empty
   * box. Today: run-sourced legends — `/papers/{slug}/legends` is slug-only and there is no
   * run-scoped legend route (spec §2, recorded as a backend follow-up).
   */
  unavailable: { legends?: string };
}
