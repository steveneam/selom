"use client";

import * as React from "react";
import { cn } from "@/lib/ui/cn";
import type { ParamField } from "@/lib/catalog/params";
import type { SkillParams } from "@/lib/skills/api";

/**
 * One inline parameter control (range / number / text / switch / select), driven by a
 * declarative `ParamField` from `lib/catalog/params`. Shared by the Workbench (run a
 * skill) and the Figure-data stage (re-run the active figure's skill with new inputs),
 * so the same knobs render identically wherever a skill is parameterised.
 */
export function ParamControl({
  field,
  value,
  onChange,
  disabled = false,
  badge,
}: {
  field: ParamField;
  value: SkillParams[string] | undefined;
  onChange: (v: SkillParams[string]) => void;
  /** Render greyed + non-interactive (a `enabledWhen` gate isn't satisfied). The control stays
   *  visible so its capability is discoverable; it just can't be changed until the gate matches. */
  disabled?: boolean;
  /** Optional adornment rendered inline beside the label (e.g. the AI ✨ attribution marker). Placed
   *  next to the label — never over the right-aligned value readout — so it can't occlude the value. */
  badge?: React.ReactNode;
}) {
  const v = value ?? field.default;
  // Standard disabled affordance (MD): reduced opacity + cursor change + semantic disabled.
  const disabledWrap = disabled ? "opacity-50" : "";

  if (field.type === "switch") {
    const on = Boolean(v);
    return (
      <label className={cn("flex items-center justify-between gap-3 sm:col-span-2", disabledWrap)}>
        <span>
          <span className="flex items-center gap-1.5 text-xs font-medium text-foreground">{field.label}{badge}</span>
          {field.help && <span className="block text-[11px] text-muted-foreground">{field.help}</span>}
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-label={field.label}
          disabled={disabled}
          onClick={() => onChange(!on)}
          className={cn(
            "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full px-0.5 transition-colors",
            on ? "bg-primary" : "bg-input",
            disabled && "cursor-not-allowed",
          )}
        >
          <span
            className={cn(
              "block size-4 rounded-full bg-white shadow-sm transition-transform",
              on ? "translate-x-4" : "translate-x-0",
            )}
          />
        </button>
      </label>
    );
  }

  if (field.type === "select") {
    return (
      <label className={cn("block sm:col-span-2", disabledWrap)}>
        <span className="flex items-center gap-1.5 text-xs font-medium text-foreground">{field.label}{badge}</span>
        <select
          value={String(v)}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            "mt-1 h-9 w-full rounded-md border border-input bg-background/60 px-2.5 text-sm text-foreground outline-none focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30",
            disabled && "cursor-not-allowed",
          )}
        >
          {field.options?.map((o) => (
            <option key={o.value} value={o.value} className="bg-card text-foreground">
              {o.label}
            </option>
          ))}
        </select>
        {field.help && <span className="mt-1 block text-[11px] text-muted-foreground">{field.help}</span>}
      </label>
    );
  }

  if (field.type === "range") {
    // Show the value at the step's precision: integer steps read "15"/"50" (not "15.0"),
    // fine steps keep their decimals ("0.20" for step 0.05).
    const decimals =
      field.step != null && field.step < 1 ? (String(field.step).split(".")[1]?.length ?? 1) : 0;
    return (
      <label className={cn("block sm:col-span-2", disabledWrap)}>
        <span className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-xs font-medium text-foreground">{field.label}{badge}</span>
          <span className="tabular text-xs text-primary">{Number(v).toFixed(decimals)}</span>
        </span>
        <input
          type="range"
          min={field.min}
          max={field.max}
          step={field.step}
          value={Number(v)}
          aria-label={field.label}
          disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
          className={cn("mt-1.5 w-full accent-[var(--primary)]", disabled && "cursor-not-allowed")}
        />
        {field.help && <span className="mt-1 block text-[11px] text-muted-foreground">{field.help}</span>}
      </label>
    );
  }

  return (
    <label className={cn("block", disabledWrap)}>
      {/* Reserve two lines for the label so a wrapped label (e.g. "Scale bar — amplitude (µV)")
          and a one-line label ("Scale bar — time (ms)") keep their inputs aligned in the 2-col grid. */}
      <span className="flex min-h-8 items-start gap-1.5 text-xs font-medium leading-4 text-foreground">{field.label}{badge}</span>
      <input
        type={field.type === "number" ? "number" : "text"}
        value={String(v)}
        min={field.min}
        max={field.max}
        step={field.step}
        placeholder={field.placeholder}
        disabled={disabled}
        onChange={(e) => onChange(field.type === "number" ? Number(e.target.value) : e.target.value)}
        className={cn(
          "mt-1 h-9 w-full rounded-md border border-input bg-background/60 px-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground/60 focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30",
          disabled && "cursor-not-allowed",
        )}
      />
      {field.help && <span className="mt-1 block text-[11px] text-muted-foreground">{field.help}</span>}
    </label>
  );
}
