"use client";

import { useEffect, useRef, useState } from "react";
import { FigureCanvas } from "@/components/figure/figure-canvas";
import { PaneBoundary } from "@/components/ui/error-boundary";
import { artboardFrame } from "@/lib/ui/artboard-frame";
import { fitScale, type Zoom } from "@/lib/ui/editor-room";
import { observeContainerResize } from "@/lib/figure/plot-resize";
import { cn } from "@/lib/ui/cn";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { MarkRole } from "@/lib/erg/marks";
import type { GeneLabelPoint } from "@/lib/volcano/labels";

/**
 * The artboard/stage region — the figure on its luminous white artboard floating on the dark
 * canvas. Extracted (Pillar-2 s0) so BOTH the classic EditorWorkspace (artboard + inspector) and
 * the CanvasShell (four-region Inkscape frame) render the SAME hero from ONE source. Pure f(spec):
 * every JSON-Patch edit reflects instantly, and no store is instantiated here — the caller owns it.
 */
export function ArtboardHost({
  store,
  elevated = false,
  readOnly = false,
  zoom = 1,
  onZoomResolved,
  onSelectTrace,
  onMarkMove,
  onToggleLabel,
}: {
  store: FigureStore;
  /** Magnification of the rendered card, or `"fit"` — resolved here, since only this component can
   *  measure the stage the figure has to fit into. */
  zoom?: Zoom;
  /** The scale actually applied, reported back so the toolbar can show a truthful percentage
   *  instead of the word "fit" (spec R5: the control must never claim a zoom it is not at). */
  onZoomResolved?: (scale: number) => void;
  /** During export the artboard is the subject — lift it above the scrim (z-45), below the popover. */
  elevated?: boolean;
  /** Frozen "paper" version (Pillar 1, S3): render the figure but bind no edit gestures (Decision D6). */
  readOnly?: boolean;
  /** A click on a trace reports its curveNumber so the inspector can focus that series (P3 §3.4). */
  onSelectTrace?: (trace: number) => void;
  /** Drag an ERG landmark dot → commit its new time (erg-manual-marks R5). */
  onMarkMove?: (segment: string, role: MarkRole, tMs: number) => void;
  /** Click a plotted point to toggle its gene label (generalization-spec §H, volcano). */
  onToggleLabel?: (point: GeneLabelPoint) => void;
}) {
  const spec = store.spec;
  const fixed = typeof spec?.layout.width === "number";
  const declaredW = typeof spec?.layout.width === "number" ? spec.layout.width : 0;
  const declaredH = typeof spec?.layout.height === "number" ? spec.layout.height : 0;

  // "Fit" resolves against the LIVE stage, so it is measured rather than assumed, and re-measured
  // whenever the stage changes size — which now happens without a window resize, since a rail can
  // collapse underneath it (W-1). A responsive figure is sized BY the stage, so its fit is exactly
  // 1 and this settles there immediately.
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [fitted, setFitted] = useState(1);
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const measure = () => {
      if (!fixed) {
        setFitted(1);
        return;
      }
      setFitted(fitScale({ width: el.clientWidth, height: el.clientHeight }, { width: declaredW, height: declaredH }));
    };
    measure();
    return observeContainerResize(el, measure);
  }, [fixed, declaredW, declaredH]);

  const resolvedZoom = zoom === "fit" ? fitted : zoom;
  useEffect(() => {
    onZoomResolved?.(resolvedZoom);
  }, [resolvedZoom, onZoomResolved]);

  if (!spec) return null;
  // ONE sizing rule, declared and unit-tested in lib/ui/artboard-frame (A24): a responsive figure is
  // sized BY this stage — it cannot ask for more room than the shell's bands left it — while a
  // fixed-size figure keeps its declared size and scrolls from the top.
  const frame = artboardFrame(fixed, resolvedZoom);

  return (
    // A slim dark gutter (p-3 lg:p-4, not p-6 lg:p-10) keeps the artboard the hero at 1280 — the
    // workrail + inspector already claim a lot of the row, so the figure gets every remaining pixel;
    // the white card's own p-3 keeps breathing room.
    <div
      ref={stageRef}
      className={cn(
        "relative flex min-w-0 flex-1 justify-center overflow-auto p-3 lg:p-4",
        frame.alignClass,
      )}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(48rem 28rem at 50% 12%, color-mix(in oklab, var(--primary) 9%, transparent), transparent 72%)",
        }}
      />
      <div
        className={cn(
          "relative flex rounded-xl border border-border bg-artboard p-3 shadow-2xl ring-1 ring-black/5",
          frame.cardClass,
          elevated && "z-[45]",
        )}
        style={frame.cardStyle}
      >
        <div className="min-h-0 min-w-0 flex-1">
          {/* Isolated (Task B1): a render throw in Plotly / a bespoke drag plug-in shows a fallback
              instead of unmounting the editor; `spec` resets it on a figure switch. Read-only → no
              `store` → no edit gestures; click-to-select still works (selection isn't an edit). */}
          <PaneBoundary label="canvas" title="This figure couldn't be drawn" resetKeys={[spec]}>
            <FigureCanvas
              spec={spec}
              store={readOnly ? undefined : store}
              onSelectTrace={readOnly ? undefined : onSelectTrace}
              onMarkMove={readOnly ? undefined : onMarkMove}
              onToggleLabel={readOnly ? undefined : onToggleLabel}
            />
          </PaneBoundary>
        </div>
      </div>
    </div>
  );
}
