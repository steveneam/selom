"use client";

import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Section } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure-spec";
import { COLORWAYS } from "@/lib/figure-spec";
import {
  type FigureModel,
  type Series,
  seriesColorOps,
  seriesVisibilityOps,
} from "@/lib/figure-model";
import { set } from "@/lib/patch";
import { cn } from "@/lib/cn";

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
}: {
  store: FigureStore;
  series: Series;
  index: number;
}) {
  const colorway = COLORWAYS.okabeito.colors;
  const swatch = series.color ?? colorway[index % colorway.length] ?? "#475569";
  const editableColor = series.colorChannels.length > 0 && !series.perPoint;
  const grouped = series.traceIndices.length > 1;

  return (
    <div className="flex items-center gap-2 rounded-lg border border-border/70 bg-background/40 p-1.5">
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

export function DataPanel({
  store,
  model,
}: {
  store: FigureStore;
  spec: FigureSpec;
  model: FigureModel;
}) {
  const { series } = model;
  const traceCount = model.traceKinds.length;
  const grouped = series.length < traceCount;

  return (
    <div className="space-y-6">
      <Section title={`Series · ${series.length}`}>
        <div className="space-y-1.5">
          {series.map((s, i) => (
            <SeriesRow key={s.key} store={store} series={s} index={i} />
          ))}
        </div>
        <p className="text-[11px] leading-relaxed text-muted-foreground/80">
          {grouped
            ? `${traceCount} traces grouped into ${series.length} series. `
            : ""}
          Rename, recolour, or hide a series. Changing the underlying data (x / y values,
          clustering) re-runs the analysis — coming with the live backend.
        </p>
      </Section>
    </div>
  );
}
