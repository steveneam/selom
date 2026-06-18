"use client";

import * as React from "react";
import { cn } from "@/lib/cn";
import type { AxisKey, CalibrationState } from "@/lib/extract/calibrate";
import { toFraction } from "@/lib/extract/calibrate";

export interface ActiveRef {
  axis: AxisKey;
  index: 0 | 1;
}

/** Cyan for the X axis, violet for the Y axis (the Selom stage accents). */
export const AXIS_COLOR: Record<AxisKey, string> = { x: "#0ea5b7", y: "#a855f7" };

/**
 * The calibration surface: the dropped panel on a luminous artboard, a crosshair
 * targeting cursor while a reference is being placed, live hover guides for precision,
 * and the placed X1/X2/Y1/Y2 markers overlaid at their fractional positions. Clicking
 * reports the click as an image fraction (resize-robust); the parent converts to natural
 * pixels at request time. Reports the image's natural dimensions on load.
 */
export function CalibrationCanvas({
  src,
  calib,
  active,
  onPlace,
  onImageLoad,
}: {
  src: string;
  calib: CalibrationState;
  active: ActiveRef | null;
  onPlace: (axis: AxisKey, index: 0 | 1, frac: { fx: number; fy: number }) => void;
  onImageLoad: (dims: { naturalW: number; naturalH: number }) => void;
}) {
  const imgRef = React.useRef<HTMLImageElement>(null);
  const [hover, setHover] = React.useState<{ fx: number; fy: number } | null>(null);

  function fractionFromEvent(e: React.MouseEvent): { fx: number; fy: number } {
    const el = imgRef.current;
    if (!el) return { fx: 0, fy: 0 };
    const rect = el.getBoundingClientRect();
    return toFraction(e.clientX - rect.left, e.clientY - rect.top, rect.width, rect.height);
  }

  const markers = (["x", "y"] as AxisKey[]).flatMap((axis) =>
    calib[axis].flatMap((r, i) => (r ? [{ axis, index: i as 0 | 1, fx: r.fx, fy: r.fy }] : [])),
  );

  return (
    <div className="relative inline-block leading-[0]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        ref={imgRef}
        src={src}
        alt="Chart panel to recover"
        draggable={false}
        onLoad={(e) =>
          onImageLoad({ naturalW: e.currentTarget.naturalWidth, naturalH: e.currentTarget.naturalHeight })
        }
        onClick={(e) => {
          if (active) onPlace(active.axis, active.index, fractionFromEvent(e));
        }}
        onMouseMove={(e) => {
          if (active) setHover(fractionFromEvent(e));
        }}
        onMouseLeave={() => setHover(null)}
        className={cn(
          "block max-h-[68vh] max-w-full select-none rounded-md",
          active ? "cursor-crosshair" : "cursor-default",
        )}
      />

      {/* live targeting guides */}
      {active && hover && (
        <>
          <span
            aria-hidden
            className="pointer-events-none absolute inset-y-0 w-px"
            style={{ left: `${hover.fx * 100}%`, backgroundColor: AXIS_COLOR[active.axis] }}
          />
          <span
            aria-hidden
            className="pointer-events-none absolute inset-x-0 h-px"
            style={{ top: `${hover.fy * 100}%`, backgroundColor: AXIS_COLOR[active.axis] }}
          />
        </>
      )}

      {/* placed reference markers */}
      {markers.map((m) => (
        <span
          key={`${m.axis}${m.index}`}
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-1/2"
          style={{ left: `${m.fx * 100}%`, top: `${m.fy * 100}%` }}
        >
          <span
            className="grid size-5 place-items-center rounded-full text-[9px] font-bold leading-none text-white shadow ring-2 ring-white/80"
            style={{ backgroundColor: AXIS_COLOR[m.axis] }}
          >
            {m.axis.toUpperCase()}
            {m.index + 1}
          </span>
        </span>
      ))}
    </div>
  );
}
