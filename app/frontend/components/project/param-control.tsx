"use client";

import * as React from "react";
import { cn } from "@/lib/cn";
import type { ParamField } from "@/lib/catalog/params";
import type { SkillParams } from "@/lib/skills-api";

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
}: {
  field: ParamField;
  value: SkillParams[string] | undefined;
  onChange: (v: SkillParams[string]) => void;
}) {
  const v = value ?? field.default;

  if (field.type === "switch") {
    const on = Boolean(v);
    return (
      <label className="flex items-center justify-between gap-3 sm:col-span-2">
        <span>
          <span className="block text-xs font-medium text-foreground">{field.label}</span>
          {field.help && <span className="block text-[11px] text-muted-foreground">{field.help}</span>}
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-label={field.label}
          onClick={() => onChange(!on)}
          className={cn(
            "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full px-0.5 transition-colors",
            on ? "bg-primary" : "bg-input",
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
      <label className="block sm:col-span-2">
        <span className="text-xs font-medium text-foreground">{field.label}</span>
        <select
          value={String(v)}
          onChange={(e) => onChange(e.target.value)}
          className="mt-1 h-9 w-full rounded-md border border-input bg-background/60 px-2.5 text-sm text-foreground outline-none focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
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
    return (
      <label className="block sm:col-span-2">
        <span className="flex items-center justify-between">
          <span className="text-xs font-medium text-foreground">{field.label}</span>
          <span className="tabular text-xs text-primary">{Number(v).toFixed(1)}</span>
        </span>
        <input
          type="range"
          min={field.min}
          max={field.max}
          step={field.step}
          value={Number(v)}
          aria-label={field.label}
          onChange={(e) => onChange(Number(e.target.value))}
          className="mt-1.5 w-full accent-[var(--primary)]"
        />
        {field.help && <span className="mt-1 block text-[11px] text-muted-foreground">{field.help}</span>}
      </label>
    );
  }

  return (
    <label className="block">
      <span className="text-xs font-medium text-foreground">{field.label}</span>
      <input
        type={field.type === "number" ? "number" : "text"}
        value={String(v)}
        min={field.min}
        max={field.max}
        step={field.step}
        placeholder={field.placeholder}
        onChange={(e) => onChange(field.type === "number" ? Number(e.target.value) : e.target.value)}
        className="mt-1 h-9 w-full rounded-md border border-input bg-background/60 px-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground/60 focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
      />
      {field.help && <span className="mt-1 block text-[11px] text-muted-foreground">{field.help}</span>}
    </label>
  );
}
