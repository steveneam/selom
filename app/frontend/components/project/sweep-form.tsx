"use client";

import * as React from "react";
import { Play, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { skillParamSchema, type ParamField } from "@/lib/catalog/params";
import type { SkillParams } from "@/lib/skills-api";
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
  const schema = React.useMemo(() => skillParamSchema(skillId), [skillId]);
  const sweepable = schema; // every knob is sweepable; numeric/select read best
  const [param, setParam] = React.useState(() => pickDefaultParam(sweepable));
  const field = sweepable.find((f) => f.key === param);
  const [raw, setRaw] = React.useState(() => suggestValues(field, baseParams[param ?? ""]));

  // Re-suggest values when the chosen parameter changes.
  React.useEffect(() => {
    setRaw(suggestValues(field, field ? baseParams[field.key] : undefined));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [param]);

  const values = React.useMemo(() => parseValues(field, raw), [field, raw]);
  const canRun = !!field && values.length >= 2 && !running;

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
        <button
          onClick={onCancel}
          aria-label="Close sweep"
          className="grid size-6 place-items-center rounded text-muted-foreground/70 hover:bg-accent hover:text-foreground [&_svg]:size-3.5"
        >
          <X />
        </button>
      </div>
      <p className="mt-0.5 text-[11px] text-muted-foreground">
        Run this skill once per value → linked sibling versions you can compare.
      </p>

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
