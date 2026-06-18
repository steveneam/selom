"use client";

import * as React from "react";
import { Loader2, ShieldAlert, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/cn";
import {
  CHART_FORMS,
  type AxisKey,
  type CalibrationState,
  type ChartForm,
  type RefPoint,
} from "@/lib/extract/calibrate";
import { AXIS_COLOR, type ActiveRef } from "./calibration-canvas";

export interface ExtractOptionsState {
  color: string;
  labels: string;
  seriesName: string;
  xName: string;
  yName: string;
}

const FORM_LABEL: Record<ChartForm, string> = { bar: "Bar", line: "Line", scatter: "Scatter" };

const STEPS: { axis: AxisKey; index: 0 | 1 }[] = [
  { axis: "x", index: 0 },
  { axis: "x", index: 1 },
  { axis: "y", index: 0 },
  { axis: "y", index: 1 },
];

export function ExtractControls({
  form,
  onForm,
  calib,
  active,
  onActivate,
  onValue,
  onToggleLog,
  options,
  onOptions,
  canExtract,
  busy,
  error,
  onExtract,
  onReset,
}: {
  form: ChartForm;
  onForm: (f: ChartForm) => void;
  calib: CalibrationState;
  active: ActiveRef | null;
  onActivate: (axis: AxisKey, index: 0 | 1) => void;
  onValue: (axis: AxisKey, index: 0 | 1, value: number | null) => void;
  onToggleLog: (axis: AxisKey) => void;
  options: ExtractOptionsState;
  onOptions: (o: ExtractOptionsState) => void;
  canExtract: boolean;
  busy: boolean;
  error: string | null;
  onExtract: () => void;
  onReset: () => void;
}) {
  const placed = STEPS.filter((s) => calib[s.axis][s.index]).length;

  return (
    <aside className="flex w-[340px] shrink-0 flex-col border-l border-border bg-card">
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-4">
        {/* Chart type */}
        <section className="space-y-2">
          <Label>Chart type</Label>
          <div className="grid grid-cols-3 gap-1.5">
            {CHART_FORMS.map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => onForm(f)}
                className={cn(
                  "rounded-md border px-2 py-1.5 text-xs font-medium transition-colors",
                  form === f
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
              >
                {FORM_LABEL[f]}
              </button>
            ))}
          </div>
        </section>

        {/* Axis calibration */}
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Axis calibration</Label>
            <span className="tabular text-[11px] text-muted-foreground">{placed}/4 set</span>
          </div>
          <p className="text-[11px] leading-relaxed text-muted-foreground/80">
            Click two ticks on each axis, then type the value at each.{" "}
            <span style={{ color: AXIS_COLOR.x }}>Cyan = X</span>,{" "}
            <span style={{ color: AXIS_COLOR.y }}>violet = Y</span>.
          </p>
          <div className="space-y-1.5">
            {STEPS.map(({ axis, index }) => (
              <CalRow
                key={`${axis}${index}`}
                axis={axis}
                index={index}
                refPoint={calib[axis][index]}
                active={active?.axis === axis && active?.index === index}
                onActivate={() => onActivate(axis, index)}
                onValue={(v) => onValue(axis, index, v)}
              />
            ))}
          </div>
          <div className="flex items-center gap-4 pt-1">
            <LogToggle axis="x" on={calib.xLog} onToggle={() => onToggleLog("x")} />
            <LogToggle axis="y" on={calib.yLog} onToggle={() => onToggleLog("y")} />
          </div>
        </section>

        {/* Optional refinements */}
        <section className="space-y-2.5">
          <Label>
            Options <span className="font-normal text-muted-foreground/60">— optional</span>
          </Label>
          <Field
            label="Series colour"
            placeholder="#0ea5b7 or 14,165,183"
            value={options.color}
            onChange={(v) => onOptions({ ...options, color: v })}
            hint="Leave blank to read the darkest marks"
          />
          {form === "bar" && (
            <Field
              label="Bar labels"
              placeholder="WT, KO, Rescue"
              value={options.labels}
              onChange={(v) => onOptions({ ...options, labels: v })}
              hint="Comma-separated, left to right"
            />
          )}
          <div className="grid grid-cols-2 gap-2">
            <Field
              label="Series name"
              placeholder="value"
              value={options.seriesName}
              onChange={(v) => onOptions({ ...options, seriesName: v })}
            />
            {form === "bar" ? (
              <Field
                label="Y label"
                placeholder="y"
                value={options.yName}
                onChange={(v) => onOptions({ ...options, yName: v })}
              />
            ) : (
              <Field
                label="X label"
                placeholder="x"
                value={options.xName}
                onChange={(v) => onOptions({ ...options, xName: v })}
              />
            )}
          </div>
          {form !== "bar" && (
            <Field
              label="Y label"
              placeholder="y"
              value={options.yName}
              onChange={(v) => onOptions({ ...options, yName: v })}
            />
          )}
        </section>
      </div>

      {/* Action footer */}
      <div className="shrink-0 space-y-2 border-t border-border p-4">
        {error && <p className="text-xs text-destructive">{error}</p>}
        <p className="flex items-start gap-1.5 text-[11px] leading-relaxed text-amber-300/90">
          <ShieldAlert className="mt-0.5 size-3.5 shrink-0" />
          Recovered values are vision-grade — review before using as data.
        </p>
        <Button className="w-full" onClick={onExtract} disabled={!canExtract}>
          {busy ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Recovering…
            </>
          ) : (
            <>
              <Sparkles className="size-4" /> Extract data
            </>
          )}
        </Button>
        <Button variant="ghost" size="sm" className="w-full" onClick={onReset}>
          Start over
        </Button>
      </div>
    </aside>
  );
}

function CalRow({
  axis,
  index,
  refPoint,
  active,
  onActivate,
  onValue,
}: {
  axis: AxisKey;
  index: 0 | 1;
  refPoint: RefPoint | null;
  active: boolean;
  onActivate: () => void;
  onValue: (v: number | null) => void;
}) {
  const isPlaced = !!refPoint;
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg border px-2 py-1.5 transition-colors",
        active ? "border-primary bg-primary/5 ring-1 ring-primary/40" : "border-border",
      )}
    >
      <button type="button" onClick={onActivate} className="flex min-w-0 flex-1 items-center gap-2 text-left">
        <span
          className="grid size-5 shrink-0 place-items-center rounded-full text-[9px] font-bold leading-none text-white"
          style={{ backgroundColor: AXIS_COLOR[axis] }}
        >
          {axis.toUpperCase()}
          {index + 1}
        </span>
        <span className="truncate text-xs text-muted-foreground">
          {active ? "Click the chart…" : isPlaced ? "Placed — click to move" : "Set this point"}
        </span>
      </button>
      <Input
        type="number"
        inputMode="decimal"
        aria-label={`${axis.toUpperCase()} reference ${index + 1} value`}
        placeholder="value"
        disabled={!isPlaced}
        value={refPoint?.value ?? ""}
        onChange={(e) => onValue(e.target.value === "" ? null : Number(e.target.value))}
        className="h-7 w-20 shrink-0"
      />
    </div>
  );
}

function LogToggle({ axis, on, onToggle }: { axis: AxisKey; on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      role="switch"
      aria-checked={on}
      className={cn(
        "inline-flex items-center gap-1.5 text-[11px] font-medium transition-colors",
        on ? "text-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      <span
        className={cn(
          "flex h-3.5 w-6 items-center rounded-full px-0.5 transition-colors",
          on ? "bg-primary" : "bg-input",
        )}
      >
        <span className={cn("size-2.5 rounded-full bg-white transition-transform", on && "translate-x-2.5")} />
      </span>
      {axis.toUpperCase()} log
    </button>
  );
}

function Field({
  label,
  placeholder,
  value,
  onChange,
  hint,
}: {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
}) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      <Input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} className="h-7" />
      {hint && <p className="text-[10px] text-muted-foreground/70">{hint}</p>}
    </div>
  );
}
