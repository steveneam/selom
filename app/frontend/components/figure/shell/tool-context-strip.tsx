"use client";

import { Maximize2, Minus, Plus } from "lucide-react";

import { ZOOM_LADDER, formatZoom, stepZoom, type Zoom } from "@/lib/ui/editor-room";
import { cn } from "@/lib/ui/cn";

/**
 * The top tool-context strip — a hint line for the active tool on the left, the artboard's zoom
 * controls on the right.
 *
 * The zoom cluster is `W-2`'s second lever (owner decision #13). It lands HERE because the strip was
 * already a fixed 30px band spending the hero's pixels on a sentence that never changed — the exact
 * "fixed chrome must justify its pixels" test the retired palette board failed (§3.3). Now the band
 * carries the control the four-region convention expects.
 *
 * Zoom is a VIEW property: it magnifies the rendered artboard and writes nothing to the spec, so it
 * creates no undo entry and never touches `layout.width`/`layout.height` — those are the export size
 * the Page tab owns.
 */
export function ToolContextStrip({
  zoom,
  resolvedZoom,
  onZoomChange,
}: {
  /** The requested zoom (`"fit"` or a ladder rung). Omit both to render the strip read-only. */
  zoom?: Zoom;
  /** What the artboard is ACTUALLY scaled to, so the readout cannot claim a zoom it is not at. */
  resolvedZoom?: number;
  onZoomChange?: (next: Zoom) => void;
}) {
  const scale = resolvedZoom ?? 1;
  const canZoom = !!onZoomChange;
  const atMin = scale <= ZOOM_LADDER[0] + 1e-9;
  const atMax = scale >= ZOOM_LADDER[ZOOM_LADDER.length - 1] - 1e-9;

  return (
    <div className="flex shrink-0 items-center gap-3 border-b border-border bg-background px-3 py-1.5">
      <p className="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">
        Select tool — click a trace to focus its series; drag legends, labels, titles, and colour
        bars on the artboard to reposition them.
      </p>

      {canZoom && (
        // Named "…artboard…", not "Zoom in"/"Zoom out". Plotly's own modebar ships buttons with
        // exactly those labels a few hundred pixels away, and they do something else entirely —
        // they zoom the DATA (the axis range) while these zoom the artboard. Two controls with one
        // name and two meanings is ambiguous to anyone driving by accessible name, screen-reader
        // users first. Found because a browser check could not tell them apart either.
        <div className="flex shrink-0 items-center gap-0.5">
          <ZoomButton
            label="Zoom artboard out"
            icon={Minus}
            disabled={atMin}
            onClick={() => onZoomChange(stepZoom(scale, -1))}
          />
          {/* The readout is the RESOLVED scale, never the word "fit": in fit mode the figure is at
              some specific percentage and the user is entitled to know which. */}
          <span className="tabular w-11 text-center text-[11px] text-muted-foreground">
            {formatZoom(scale)}
          </span>
          <ZoomButton
            label="Zoom artboard in"
            icon={Plus}
            disabled={atMax}
            onClick={() => onZoomChange(stepZoom(scale, 1))}
          />
          <ZoomButton
            label="Fit artboard to view"
            icon={Maximize2}
            pressed={zoom === "fit"}
            onClick={() => onZoomChange("fit")}
          />
        </div>
      )}
    </div>
  );
}

function ZoomButton({
  label,
  icon: Icon,
  onClick,
  disabled = false,
  pressed,
}: {
  label: string;
  icon: typeof Minus;
  onClick: () => void;
  disabled?: boolean;
  pressed?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      {...(pressed === undefined ? {} : { "aria-pressed": pressed })}
      className={cn(
        "grid size-6 place-items-center rounded text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-40",
        pressed && "bg-accent text-accent-foreground",
      )}
    >
      <Icon className="size-3.5" />
    </button>
  );
}
