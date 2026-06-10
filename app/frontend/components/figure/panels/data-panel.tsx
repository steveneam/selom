"use client";

import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Section } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure-spec";
import { COLORWAYS } from "@/lib/figure-spec";
import { getAt, set } from "@/lib/patch";
import { cn } from "@/lib/cn";

function TraceRow({
  store,
  spec,
  index,
}: {
  store: FigureStore;
  spec: FigureSpec;
  index: number;
}) {
  const trace = spec.data[index];
  const name = (trace.name as string) ?? `Trace ${index + 1}`;
  const visible = trace.visible !== false && trace.visible !== "legendonly";

  const colorway = getAt<string[]>(spec, "/layout/colorway", COLORWAYS.okabeito.colors)!;
  const rawColor = trace.marker?.color;
  const swatch =
    typeof rawColor === "string" ? rawColor : colorway[index % colorway.length] ?? "#475569";
  const perPointColors = Array.isArray(rawColor);

  return (
    <div className="flex items-center gap-2 rounded-lg border border-border/70 bg-background/40 p-1.5">
      <label className="relative shrink-0" title={perPointColors ? "Per-point colours" : swatch}>
        <span
          className="block size-6 rounded-md ring-1 ring-inset ring-black/10"
          style={{ backgroundColor: perPointColors ? undefined : swatch }}
        />
        {!perPointColors && (
          <input
            type="color"
            value={swatch}
            aria-label={`${name} colour`}
            onChange={(e) => store.commit([set(`/data/${index}/marker/color`, e.target.value)])}
            className="absolute inset-0 cursor-pointer opacity-0"
          />
        )}
      </label>

      <Input
        value={name}
        aria-label={`Trace ${index + 1} name`}
        onChange={(e) => store.set([set(`/data/${index}/name`, e.target.value)])}
        onBlur={() => store.flush()}
        className="h-7 border-transparent bg-transparent px-1.5 shadow-none focus-visible:border-input focus-visible:bg-background/60"
      />

      <button
        type="button"
        aria-label={visible ? `Hide ${name}` : `Show ${name}`}
        title={visible ? "Hide trace" : "Show trace"}
        onClick={() =>
          store.commit([set(`/data/${index}/visible`, visible ? "legendonly" : true)])
        }
        className={cn(
          "grid size-7 shrink-0 cursor-pointer place-items-center rounded-md transition-colors hover:bg-accent hover:text-accent-foreground",
          visible ? "text-foreground/80" : "text-muted-foreground/60",
        )}
      >
        {visible ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
      </button>
    </div>
  );
}

export function DataPanel({ store, spec }: { store: FigureStore; spec: FigureSpec }) {
  return (
    <div className="space-y-6">
      <Section title={`Traces · ${spec.data.length}`}>
        <div className="space-y-1.5">
          {spec.data.map((_, i) => (
            <TraceRow key={i} store={store} spec={spec} index={i} />
          ))}
        </div>
        <p className="text-[11px] leading-relaxed text-muted-foreground/80">
          Rename, recolour, or hide a series. Changing the underlying data (x / y values,
          clustering) re-runs the analysis — coming with the live backend.
        </p>
      </Section>
    </div>
  );
}
