"use client";

import { useEffect, useRef } from "react";
import { Eye, EyeOff, Grid2x2, LineChart } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Section, SwitchField } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import { COLORWAYS } from "@/lib/figure/figure-spec";
import {
  type FigureModel,
  type Series,
  layoutModeOp,
  overlayAxisOp,
  seriesColorOps,
  seriesVisibilityOps,
} from "@/lib/figure/figure-model";
import { set } from "@/lib/figure/patch";
import { cn } from "@/lib/ui/cn";

/**
 * One editable SERIES — one or more traces sharing an identity (the ERG grid's 42 line
 * traces collapse to 6 conditions). The swatch writes the *real* colour channel
 * (`line.color` for a line grid, `marker.color` for a scatter), recolouring every trace
 * in the series at once. A single-trace series stays renamable; a grouped one shows a
 * static label + its trace count.
 */
function SeriesRow({
  store,
  series,
  index,
  focused,
}: {
  store: FigureStore;
  series: Series;
  index: number;
  /** Click-to-select (P3 §3.4): this series was picked on the canvas — highlight + scroll to it. */
  focused?: boolean;
}) {
  const colorway = COLORWAYS.okabeito.colors;
  const swatch = series.color ?? colorway[index % colorway.length] ?? "#475569";
  const editableColor = series.colorChannels.length > 0 && !series.perPoint;
  const grouped = series.traceIndices.length > 1;
  const rowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (focused) rowRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focused]);

  return (
    <div
      ref={rowRef}
      className={cn(
        "flex items-center gap-2 rounded-lg border bg-background/40 p-1.5 transition-colors",
        focused ? "border-primary/60 ring-1 ring-ring/40" : "border-border/70",
      )}
    >
      <label
        className="relative shrink-0"
        title={series.perPoint ? "Per-point colours" : editableColor ? swatch : "No editable colour"}
      >
        <span
          className="block size-6 rounded-md ring-1 ring-inset ring-black/10"
          style={{ backgroundColor: series.perPoint || !editableColor ? undefined : swatch }}
        />
        {editableColor && (
          <input
            type="color"
            value={swatch}
            aria-label={`${series.label} colour`}
            onChange={(e) => store.commit(seriesColorOps(series, e.target.value))}
            className="absolute inset-0 cursor-pointer opacity-0"
          />
        )}
      </label>

      {grouped ? (
        <span className="flex min-w-0 flex-1 items-center gap-1.5 px-1.5">
          <span className="truncate text-sm text-foreground/90">{series.label}</span>
          <span className="shrink-0 text-[10px] tabular text-muted-foreground/70">
            · {series.traceIndices.length}
          </span>
        </span>
      ) : (
        <Input
          value={series.label}
          aria-label={`Series ${index + 1} name`}
          onChange={(e) => store.set([set(`/data/${series.traceIndices[0]}/name`, e.target.value)])}
          onBlur={() => store.flush()}
          className="h-7 border-transparent bg-transparent px-1.5 shadow-none focus-visible:border-input focus-visible:bg-background/60"
        />
      )}

      <button
        type="button"
        aria-label={series.visible ? `Hide ${series.label}` : `Show ${series.label}`}
        title={series.visible ? "Hide series" : "Show series"}
        onClick={() => store.commit(seriesVisibilityOps(series, !series.visible))}
        className={cn(
          "grid size-7 shrink-0 cursor-pointer place-items-center rounded-md transition-colors hover:bg-accent hover:text-accent-foreground",
          series.visible ? "text-foreground/80" : "text-muted-foreground/60",
        )}
      >
        {series.visible ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
      </button>
    </div>
  );
}

/**
 * Grid ↔ overlay layout switch for a small-multiples trace grid (the ERG waveform grid), with
 * per-axis show/hide once overlaid. Overlay is a render-time projection
 * (lib/figure-model.projectOverlay) — each click is one undoable patch on `meta.selom`, so the
 * canonical grid spec is never mutated and the figure can always switch back.
 */
function LayoutControl({ store, model }: { store: FigureStore; model: FigureModel }) {
  const modes = [
    { id: "grid", label: "Grid", icon: Grid2x2, hint: "Stacked small multiples" },
    { id: "overlay", label: "Overlay", icon: LineChart, hint: "All traces on one set of axes" },
  ] as const;
  return (
    <Section title="Layout">
      <div className="grid grid-cols-2 gap-1 rounded-lg border border-border bg-muted/40 p-1">
        {modes.map((m) => {
          const active = model.layoutMode === m.id;
          const Icon = m.icon;
          return (
            <button
              key={m.id}
              type="button"
              aria-pressed={active}
              title={m.hint}
              onClick={() => { if (!active) store.commit([layoutModeOp(m.id)]); }}
              className={cn(
                "flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&_svg]:size-3.5",
                active
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon /> {m.label}
            </button>
          );
        })}
      </div>
      {model.layoutMode === "overlay" ? (
        <div className="space-y-1 rounded-lg border border-border/70 bg-background/40 px-2.5 py-1.5">
          <SwitchField
            label="Time axis (x)"
            checked={model.overlayAxes.x}
            onChange={(v) => store.commit([overlayAxisOp("x", v)])}
          />
          <SwitchField
            label="Amplitude axis (y)"
            checked={model.overlayAxes.y}
            onChange={(v) => store.commit([overlayAxisOp("y", v)])}
          />
        </div>
      ) : (
        <p className="text-[11px] leading-relaxed text-muted-foreground/80">
          Overlay draws every trace on one set of axes, like a normal line graph.
        </p>
      )}
    </Section>
  );
}

export function DataPanel({
  store,
  model,
  focusedSeriesKey,
}: {
  store: FigureStore;
  spec: FigureSpec;
  model: FigureModel;
  /** The series picked by clicking a line on the canvas (P3 §3.4) — highlighted + scrolled to. */
  focusedSeriesKey?: string | null;
}) {
  const { series } = model;
  const traceCount = model.traceKinds.length;
  const grouped = series.length < traceCount;

  return (
    <div className="space-y-6">
      {model.overlayCapable && <LayoutControl store={store} model={model} />}
      <Section title={`Series · ${series.length}`}>
        <div className="space-y-1.5">
          {series.map((s, i) => (
            <SeriesRow key={s.key} store={store} series={s} index={i} focused={s.key === focusedSeriesKey} />
          ))}
        </div>
        <p className="text-[11px] leading-relaxed text-muted-foreground/80">
          {grouped
            ? `${traceCount} traces grouped into ${series.length} series. `
            : ""}
          Click a line on the figure to focus its series here. Rename, recolour, or hide a series.
          Changing the underlying data (x / y values, clustering) re-runs the analysis in Figure data.
        </p>
      </Section>
    </div>
  );
}
