"use client";

import { FigureCanvas } from "@/components/figure/figure-canvas";
import { PaneBoundary } from "@/components/ui/error-boundary";
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
  onSelectTrace,
  onMarkMove,
  onToggleLabel,
}: {
  store: FigureStore;
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
  if (!spec) return null;
  const fixed = typeof spec.layout.width === "number";

  return (
    // Top-align (not center): a tall figure overflows the scroll region, and centering would push
    // its top out of view AND make it unreachable by scrolling. A slim dark gutter (p-3 lg:p-4, not
    // p-6 lg:p-10) keeps the artboard the hero at 1280 — the workrail + inspector already claim a lot
    // of the row, so the figure gets every remaining pixel; the white card's own p-3 keeps breathing room.
    <div className="relative flex min-w-0 flex-1 items-start justify-center overflow-auto p-3 lg:p-4">
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
          elevated && "z-[45]",
        )}
        style={
          // Fill the available width (so collapsing the side rails gives the figure more room
          // instead of opening a dark gap), capped so it never stretches absurdly wide on an
          // ultra-wide monitor; still centered on the dark stage when it does cap.
          fixed ? undefined : { width: "100%", maxWidth: "88rem", height: "min(74vh, 720px)" }
        }
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
