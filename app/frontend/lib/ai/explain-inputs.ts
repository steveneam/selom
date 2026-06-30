/**
 * Pure mappers from FE domain shapes → the `/ai/explain` request payloads.
 *
 * The boundary adapters for the two informational helpers (S5 NEXT#1). Kept here —
 * pure + unit-tested — so the components stay declarative and the wire shape is asserted
 * in one place. Neither helper mutates anything; these only *describe* deterministic
 * artifacts (a scorecard, a sweep space) for the gateway to summarise.
 */

import type { ParamField } from "@/lib/catalog/params";
import type { SkillParams } from "@/lib/skills/api";
import type { Scorecard } from "@/lib/reproduction/types";

/**
 * Flatten a reproduction `Scorecard` into the shape the backend `explain_score` reads.
 *
 * The FE `Scorecard` nests the headline under `score.reproducibility`; the backend
 * deterministic path reads a flat `score` / `tier` / `panel_count` (`ai/gateway.py`).
 * We map at the boundary rather than reshape the backend. Null numeric fields are
 * *omitted* (not sent as `null`) so the backend falls back to its own "n/a" defaults
 * instead of printing `null/100`. Returns `null` when there is no graded score yet.
 */
export function buildScorecardPayload(sc: Scorecard | null | undefined): Record<string, unknown> | null {
  if (!sc || !sc.score) return null;
  const s = sc.score;
  const payload: Record<string, unknown> = {
    tier: s.tier,
    panel_count: sc.panel_scores.length,
    findings: sc.findings,
    coverage: s.coverage,
  };
  if (s.reproducibility != null) payload.score = s.reproducibility;
  if (s.selom_confidence != null) payload.selom_confidence = s.selom_confidence;
  return payload;
}

/** One knob in the sweep space the backend ranker reads (`ai/gateway.py::rank_sweep_space`). */
export interface SweepKnob {
  label: string;
  type: ParamField["type"];
  min?: number;
  max?: number;
  step?: number;
  /** The declared option values (`select` knobs). */
  options?: string[];
  /** The figure's current value for this knob — context for the live AI; ignored by the ranker. */
  current?: string | number | boolean;
}

/**
 * Describe the skill's sweepable knobs as the `sweep_space` the recommender ranks.
 *
 * Built from the SAME `ParamField[]` the `SweepForm` already loads + the figure's current
 * params, so the ranking can only ever pick a knob the form can actually sweep. Carries each
 * knob's declared value-space (range / options / on-off) — the only thing the deterministic
 * ranker is allowed to reason about (it never claims figure impact without running).
 */
export function buildSweepSpace(fields: ParamField[], params: SkillParams): Record<string, SweepKnob> {
  const space: Record<string, SweepKnob> = {};
  for (const f of fields) {
    const knob: SweepKnob = { label: f.label, type: f.type };
    if (f.min != null) knob.min = f.min;
    if (f.max != null) knob.max = f.max;
    if (f.step != null) knob.step = f.step;
    if (f.options?.length) knob.options = f.options.map((o) => o.value);
    const current = params[f.key] ?? f.default;
    if (current != null) knob.current = current;
    space[f.key] = knob;
  }
  return space;
}
