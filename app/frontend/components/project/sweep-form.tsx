"use client";

import * as React from "react";
import { Lightbulb, Loader2, Play, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/ui/cn";
import { type ParamField } from "@/lib/catalog/params";
import { useSkillParams } from "@/lib/catalog/use-skill-params";
import { explain } from "@/lib/ai/api";
import { buildSweepSpace } from "@/lib/ai/explain-inputs";
import { ExplainSourceBadge } from "@/components/ai/explain-source-badge";
import type { ExplainResponse } from "@/lib/ai/types";
import type { SkillParams } from "@/lib/skills/api";
import type { ParamValue } from "@/lib/lineage/diff";

const MAX_VALUES = 6;

/**
 * Parameter sweep (Pillar 1, S3.1) — pick one parameter, give it N values, and run the
 * skill once per value to produce N linked sibling versions (`parentFigureId` +
 * `variantLabel`). Inline progressive disclosure (not a modal): it expands under the
 * version bar of the figure it forks from.
 */
export function SweepForm({
  skillId,
  baseParams,
  running,
  onRun,
  onCancel,
}: {
  skillId: string;
  /** The origin figure's params — the sweep varies one of them, holds the rest. */
  baseParams: SkillParams;
  running: boolean;
  onRun: (param: string, values: ParamValue[]) => void;
  onCancel: () => void;
}) {
  // The sweepable knobs are the skill's spec-driven param fields (loaded async).
  const { fields: sweepable, loading } = useSkillParams(skillId);
  const [param, setParam] = React.useState("");
  const field = sweepable.find((f) => f.key === param);
  const [raw, setRaw] = React.useState("");

  // Pick a default parameter once the fields load (or the skill changes).
  React.useEffect(() => {
    if (sweepable.length > 0 && !sweepable.some((f) => f.key === param)) {
      setParam(pickDefaultParam(sweepable));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-pick only when the field set changes
  }, [sweepable]);

  // Re-suggest values when the chosen parameter changes.
  React.useEffect(() => {
    setRaw(suggestValues(field, field ? baseParams[field.key] : undefined));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [param]);

  const values = React.useMemo(() => parseValues(field, raw), [field, raw]);
  const canRun = !!field && values.length >= 2 && !running;

  // "Suggest" — ask the grounded recommender which knob is worth sweeping (informational, not a
  // mutation). It preselects the top-ranked param (which re-suggests that knob's values); the user
  // still reviews + clicks Run. Deterministic by default; the ✨ badge shows only when a key is live.
  const [suggesting, setSuggesting] = React.useState(false);
  const [suggestion, setSuggestion] = React.useState<ExplainResponse | null>(null);
  const [suggestError, setSuggestError] = React.useState<string | null>(null);

  async function suggest() {
    setSuggesting(true);
    setSuggestError(null);
    try {
      const res = await explain({
        request: "propose_sweep",
        stage: "analyze",
        skill_id: skillId,
        sweep_space: buildSweepSpace(sweepable, baseParams),
      });
      setSuggestion(res);
      const top = res.suggestions?.[0]?.param;
      if (top && sweepable.some((f) => f.key === top)) setParam(top);
    } catch (e) {
      setSuggestError(e instanceof Error ? e.message : "Couldn't suggest parameters.");
    } finally {
      setSuggesting(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-card/60 px-3.5 py-3 text-xs text-muted-foreground">
        Loading parameters…
      </div>
    );
  }

  if (sweepable.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card/60 px-3.5 py-3 text-xs text-muted-foreground">
        This skill has no parameters to sweep.{" "}
        <button onClick={onCancel} className="text-foreground underline-offset-2 hover:underline">
          Close
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-stage-skill/35 bg-[color-mix(in_oklab,var(--stage-skill)_6%,var(--card))] p-3.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-foreground">Sweep a parameter</p>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={suggest}
            disabled={suggesting}
            title="Suggest which parameter is worth sweeping"
            className="inline-flex cursor-pointer items-center gap-1 rounded border border-border bg-background/60 px-2 py-0.5 text-[11px] font-medium text-foreground/80 transition-colors hover:bg-accent hover:text-foreground disabled:cursor-default disabled:opacity-60 [&_svg]:size-3"
          >
            {suggesting ? <Loader2 className="animate-spin" /> : <Lightbulb />} Suggest
          </button>
          <button
            onClick={onCancel}
            aria-label="Close sweep"
            className="grid size-6 cursor-pointer place-items-center rounded text-muted-foreground/70 hover:bg-accent hover:text-foreground [&_svg]:size-3.5"
          >
            <X />
          </button>
        </div>
      </div>
      <p className="mt-0.5 text-[11px] text-muted-foreground">
        Run this skill once per value → linked sibling versions you can compare.
      </p>

      {suggestError ? (
        <p className="mt-2 text-[11px] text-amber-600 dark:text-amber-400">{suggestError}</p>
      ) : suggestion && (suggestion.suggestions?.length ?? 0) > 0 ? (
        // Ranked picks as clickable chips (the recommender returns top-3; render all, don't just
        // auto-apply #0). These are ALWAYS the deterministic ranking — no AI badge here (the AI only
        // varies the explain_score prose; the picks stay grounded + reproducible). Selected chip is
        // highlighted, so when the user picks a non-suggested knob the panel reads as advice, not a
        // stale contradiction. Dismissable.
        <div className="mt-2 rounded-md border border-border bg-background/50 px-2.5 py-2">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              Suggested knobs · ranked by range
            </span>
            <button
              type="button"
              onClick={() => setSuggestion(null)}
              aria-label="Dismiss suggestions"
              className="grid size-4 cursor-pointer place-items-center rounded text-muted-foreground/70 hover:bg-accent hover:text-foreground [&_svg]:size-3"
            >
              <X />
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {suggestion.suggestions!.map((s) => {
              const selected = s.param === param;
              return (
                <button
                  key={s.param}
                  type="button"
                  onClick={() => setParam(s.param)}
                  title={s.reason}
                  aria-pressed={selected}
                  className={cn(
                    "inline-flex cursor-pointer items-center rounded-full border px-2 py-0.5 text-[11px] transition-colors",
                    selected
                      ? "border-stage-skill/60 bg-stage-skill/15 text-foreground"
                      : "border-border bg-background/60 text-foreground/80 hover:bg-accent hover:text-foreground",
                  )}
                >
                  {s.label}
                </button>
              );
            })}
          </div>
          {suggestion.suggestions!.find((s) => s.param === param) && (
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              {suggestion.suggestions!.find((s) => s.param === param)!.reason}
            </p>
          )}
          {/* #10 — the AI's narrative reasoning, surfaced ONLY when the gateway produced it
              (source==="ai"). The picks above stay deterministic + unbadged (grounded, reproducible);
              this prose is the AI value-add, carrying the ✨ "AI" badge so the glyph never lies. */}
          {suggestion.source === "ai" && suggestion.text && (
            <div className="mt-2 flex flex-col gap-1 border-t border-border/60 pt-2">
              <ExplainSourceBadge source="ai" />
              <p className="text-[11px] leading-relaxed text-foreground/80">{suggestion.text}</p>
            </div>
          )}
        </div>
      ) : null}

      <div className="mt-3 grid gap-3 sm:grid-cols-[160px_1fr]">
        <label className="block">
          <span className="text-[11px] font-medium text-muted-foreground">Parameter</span>
          <select
            value={param}
            onChange={(e) => setParam(e.target.value)}
            className="mt-1 h-9 w-full rounded-md border border-input bg-background/60 px-2.5 text-sm text-foreground outline-none focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
          >
            {sweepable.map((f) => (
              <option key={f.key} value={f.key} className="bg-card text-foreground">
                {f.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-[11px] font-medium text-muted-foreground">
            Values <span className="text-muted-foreground/70">(comma-separated)</span>
          </span>
          <input
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            placeholder={field ? hintFor(field) : ""}
            className="tabular mt-1 h-9 w-full rounded-md border border-input bg-background/60 px-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground/60 focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
          />
        </label>
      </div>

      <div className="mt-3 flex items-center justify-between gap-3">
        <span className={cn("text-[11px]", values.length >= 2 ? "text-foreground" : "text-muted-foreground")}>
          {values.length >= 2
            ? `→ ${values.length} version${values.length === 1 ? "" : "s"}: ${values.map(String).join(", ")}`
            : "Enter at least two distinct values."}
          {field && parseValues(field, raw).length === MAX_VALUES && " (max)"}
        </span>
        <Button size="sm" disabled={!canRun} onClick={() => field && onRun(field.key, values)}>
          <Play /> {running ? "Running sweep…" : "Run sweep"}
        </Button>
      </div>
    </div>
  );
}

/** Prefer the first numeric/select knob (those sweep most meaningfully). */
function pickDefaultParam(schema: ParamField[]): string {
  const numeric = schema.find((f) => f.type === "range" || f.type === "number" || f.type === "select");
  return (numeric ?? schema[0])?.key ?? "";
}

/** A sensible starting set of values for a parameter, given its type + current value. */
function suggestValues(field: ParamField | undefined, current: ParamValue | undefined): string {
  if (!field) return "";
  if (field.type === "range" || field.type === "number") {
    const c = typeof current === "number" ? current : Number(field.default);
    const step = field.step ?? 1;
    const lo = Math.max(field.min ?? -Infinity, round(c / 2, step));
    const hi = round(c, step);
    return lo !== hi ? `${lo}, ${hi}` : `${round(c, step)}, ${round(c + step * 2, step)}`;
  }
  if (field.type === "switch") return "false, true";
  if (field.type === "select") return (field.options ?? []).slice(0, 4).map((o) => o.value).join(", ");
  return current != null ? String(current) : "";
}

function hintFor(field: ParamField): string {
  if (field.type === "switch") return "false, true";
  if (field.type === "select") return (field.options ?? []).map((o) => o.value).join(", ");
  return "e.g. 0.5, 1.0, 1.5";
}

/** Parse the comma-separated input into typed, distinct values (capped). */
function parseValues(field: ParamField | undefined, raw: string): ParamValue[] {
  if (!field) return [];
  const parts = raw.split(",").map((s) => s.trim()).filter(Boolean);
  const out: ParamValue[] = [];
  const seen = new Set<string>();
  for (const p of parts) {
    let v: ParamValue | undefined;
    if (field.type === "range" || field.type === "number") {
      const n = Number(p);
      if (Number.isFinite(n)) v = n;
    } else if (field.type === "switch") {
      if (/^(true|1|on|yes)$/i.test(p)) v = true;
      else if (/^(false|0|off|no)$/i.test(p)) v = false;
    } else {
      v = p;
    }
    if (v === undefined) continue;
    const key = String(v);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(v);
    if (out.length >= MAX_VALUES) break;
  }
  return out;
}

function round(n: number, step: number): number {
  if (!Number.isFinite(step) || step <= 0) return n;
  const r = Math.round(n / step) * step;
  // Avoid 0.30000000000000004 — clamp to the step's decimal places.
  const dp = (String(step).split(".")[1] ?? "").length;
  return Number(r.toFixed(dp));
}
