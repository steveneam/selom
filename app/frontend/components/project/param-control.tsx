"use client";

import * as React from "react";
import { Plus, X } from "lucide-react";
import { cn } from "@/lib/ui/cn";
import { parsePairs, serializePairs, type ParamField } from "@/lib/catalog/params";
import type { SkillParams } from "@/lib/skills/api";

/**
 * One inline parameter control (range / number / text / switch / select / column / pairs), driven
 * by a declarative `ParamField` from `lib/catalog/params`. Shared by the Workbench (run a skill)
 * and the Figure-data stage (re-run the active figure's skill with new inputs), so the same knobs
 * render identically wherever a skill is parameterised.
 *
 * `column` and `pairs` are the data-aware widgets: they only ever arrive here already carrying the
 * dataset's real vocabulary (the merge in `lib/catalog/params` downgrades them to `text` when there
 * is none), so there is no empty-picker state to render.
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
    const on = isOn(v);
    return (
      // A DIV, not a LABEL. The `badge` slot renders a BUTTON (the AI ✨ marker with its Revert
      // action), and inside a `<label>` the first labelable descendant becomes the label's control
      // — the badge, not the switch. Clicking the label text or the help paragraph then fired
      // REVERT instead of toggling, silently discarding an AI proposal. The switch carries its own
      // `aria-label`, so the accessible name is unaffected by dropping the wrapper.
      <div className={cn("flex items-center justify-between gap-3 sm:col-span-2", disabledWrap)}>
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
            disabled ? "cursor-not-allowed" : "cursor-pointer hover:opacity-90",
          )}
        >
          <span
            className={cn(
              "block size-4 rounded-full bg-white shadow-sm transition-transform",
              on ? "translate-x-4" : "translate-x-0",
            )}
          />
        </button>
      </div>
    );
  }

  if (field.type === "select") {
    return (
      <label className={cn("block sm:col-span-2", disabledWrap)}>
        <span className="flex items-center gap-1.5 text-xs font-medium text-foreground">{field.label}{badge}</span>
        <select
          value={String(v)}
          disabled={disabled}
          // Explicit, or the wrapping <label> folds the help paragraph into the accessible NAME —
          // a screen reader then announces the whole sentence as the field's name, and two fields
          // whose help mentions each other become mutually ambiguous.
          aria-label={field.label}
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

  if (field.type === "combobox") {
    // Pick-or-type: the dataset's columns are offered, but a value that does not exist YET stays
    // typeable — `deg.groupby` resolves to Leiden clusters the runner computes on the spot, so a
    // closed select would make the runner's commonest resolved value unofferable. A native
    // input+datalist is the accessible form of this and needs no popover.
    const listId = `${field.key}-options`;
    return (
      <label className={cn("block", disabledWrap)}>
        <span className="flex min-h-8 items-start gap-1.5 text-xs font-medium leading-4 text-foreground">{field.label}{badge}</span>
        <input
          list={listId}
          value={String(v)}
          disabled={disabled}
          aria-label={field.label}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            "mt-1 h-9 w-full rounded-md border border-input bg-background/60 px-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground/60 focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30",
            disabled && "cursor-not-allowed",
          )}
        />
        <datalist id={listId}>
          {field.columns?.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </datalist>
        {field.help && <span className="mt-1 block text-[11px] text-muted-foreground">{field.help}</span>}
      </label>
    );
  }

  if (field.type === "column" || field.type === "level") {
    // One select for both: a column picker and a level picker differ only in the vocabulary the
    // resolver filled (`columns` vs the per-render `options`) and in what a blank value means.
    const choices = field.type === "level" ? (field.options ?? []) : (field.columns ?? []);
    return (
      <label className={cn("block", disabledWrap)}>
        <span className="flex min-h-8 items-start gap-1.5 text-xs font-medium leading-4 text-foreground">{field.label}{badge}</span>
        <select
          value={String(v)}
          disabled={disabled}
          aria-label={field.label}
          // A native select clips rather than wraps, and real column / level names are long
          // ("AAV8-RK-GFP-polyA-stuffer"). Hover recovers the full value at no layout cost.
          title={String(v) || undefined}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            "mt-1 h-9 w-full rounded-md border border-input bg-background/60 px-2.5 text-sm text-foreground outline-none focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30",
            disabled && "cursor-not-allowed",
          )}
        >
          {/* The blank choice is the backend's auto-detect, named rather than left as an empty row. */}
          <option value="" className="bg-card text-foreground">{field.placeholder ?? "auto-detect"}</option>
          {/* A saved figure can name a column/level THIS dataset lacks. Keep it selectable and say
              so — silently dropping it would rewrite the user's spec on open. */}
          {String(v) && !choices.some((c) => c.value === String(v)) && (
            <option value={String(v)} className="bg-card text-foreground">
              {String(v)} — not in this dataset
            </option>
          )}
          {choices.map((c) => (
            <option key={c.value} value={c.value} className="bg-card text-foreground">
              {c.label}
            </option>
          ))}
        </select>
        {field.help && <span className="mt-1 block text-[11px] text-muted-foreground">{field.help}</span>}
      </label>
    );
  }

  if (field.type === "pairs") {
    return <PairsControl field={field} value={v} onChange={onChange} disabled={disabled} badge={badge} />;
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
        aria-label={field.label}
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

/**
 * The `pairs` row-list: one "A vs B" comparison per row, each a pair of level selects with its own
 * remove control, and an explicit "+ Add comparison" beneath — the shape every mature filter/series
 * builder converges on (beehiiv "+ Condition" · Confluence / ClickUp / Braintrust "+ Add filter" ·
 * Glide's numbered ITEM blocks with a per-item trash and "+ Add item").
 *
 * Fully controlled: the rows ARE `parsePairs(value)`, and every edit serializes straight back to the
 * same `"A~B, C~D"` string the backend already parses. No local draft list, so nothing can drift out
 * of sync with a Reset, an accepted AI proposal, or a figure switch.
 */
function PairsControl({
  field,
  value,
  onChange,
  disabled,
  badge,
}: {
  field: ParamField;
  value: SkillParams[string];
  onChange: (v: SkillParams[string]) => void;
  disabled: boolean;
  badge?: React.ReactNode;
}) {
  const rows = parsePairs(String(value ?? ""));
  const levels = field.options ?? [];
  const emit = (next: [string, string][]) => onChange(serializePairs(next));
  const setSide = (i: number, side: 0 | 1, v: string) =>
    emit(rows.map((r, j) => (j === i ? (side === 0 ? [v, r[1]] : [r[0], v]) : r)));

  const selectCls = cn(
    "h-8 min-w-0 flex-1 rounded-md border border-input bg-background/60 px-2 text-xs text-foreground outline-none focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30",
    disabled && "cursor-not-allowed",
  );
  // A saved pair can name a level this dataset lacks (a renamed group, a different export). Keep it
  // selectable and labelled rather than snapping the row to some other level behind the user's back.
  const optionsFor = (current: string) => (
    <>
      <option value="">Choose…</option>
      {current && !levels.some((o) => o.value === current) && (
        <option value={current}>{current} — not in this dataset</option>
      )}
      {levels.map((o) => (
        <option key={o.value} value={o.value} className="bg-card text-foreground">
          {o.label}
        </option>
      ))}
    </>
  );

  return (
    // A composite control, so it carries its own group role + name — a wrapping <label> would
    // associate the whole row-list with only its first select.
    <div role="group" aria-label={field.label} className={cn("sm:col-span-2", disabled && "opacity-50")}>
      <span className="flex items-center gap-1.5 text-xs font-medium text-foreground">{field.label}{badge}</span>
      {rows.length > 0 && (
        <ul className="mt-1.5 space-y-1.5">
          {rows.map(([a, b], i) => (
            <li key={i} className="flex items-center gap-1.5">
              <select
                value={a}
                disabled={disabled}
                title={a || undefined}
                aria-label={`Comparison ${i + 1}, first group`}
                onChange={(e) => setSide(i, 0, e.target.value)}
                className={selectCls}
              >
                {optionsFor(a)}
              </select>
              <span aria-hidden className="shrink-0 text-[11px] text-muted-foreground">vs</span>
              <select
                value={b}
                disabled={disabled}
                title={b || undefined}
                aria-label={`Comparison ${i + 1}, second group`}
                onChange={(e) => setSide(i, 1, e.target.value)}
                className={selectCls}
              >
                {optionsFor(b)}
              </select>
              <button
                type="button"
                disabled={disabled}
                aria-label={`Remove comparison ${i + 1}`}
                onClick={() => emit(rows.filter((_, j) => j !== i))}
                className={cn(
                  "grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground [&_svg]:size-3.5",
                  disabled && "cursor-not-allowed",
                )}
              >
                <X />
              </button>
            </li>
          ))}
        </ul>
      )}
      <button
        type="button"
        disabled={disabled}
        onClick={() => emit([...rows, ["", ""]])}
        className={cn(
          "mt-1.5 inline-flex items-center gap-1 rounded-md border border-dashed border-input px-2 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground [&_svg]:size-3",
          disabled && "cursor-not-allowed",
        )}
      >
        <Plus /> Add comparison
      </button>
      {field.help && <span className="mt-1 block text-[11px] text-muted-foreground">{field.help}</span>}
    </div>
  );
}

/**
 * A bool param's on-state, mirroring the backend's `to_bool` rather than JS truthiness.
 *
 * `Boolean("false") === true`, so a bool arriving as a STRING drew the switch in the opposite state
 * — and the params that reach here are not always real booleans: query-string params arrive as
 * strings (`contract.resolved_params` exists to re-coerce them), a saved figure's recorded params
 * round-trip through JSON, and an AI-staged proposal is free to hand over `"false"`. The worst case
 * is that last one, because it draws an ON switch under an "AI-staged change" marker for a value
 * the run will treat as OFF.
 */
function isOn(v: unknown): boolean {
  if (typeof v === "string") return !["false", "0", "no", "off", ""].includes(v.trim().toLowerCase());
  return Boolean(v);
}
