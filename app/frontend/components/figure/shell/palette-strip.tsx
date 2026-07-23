"use client";

import { COLORWAYS } from "@/lib/figure/figure-spec";

/**
 * The bottom palette strip — a READ-ONLY swatch preview of the default colourway (Okabe–Ito,
 * CB-safe) plus a "coming soon" note. Inert placeholder for Pillar-2 s0; the live palette board
 * (click a swatch to recolour the active series) arrives in a later slice. The real colourway swap
 * already lives in the inspector's Style tab, so nothing is lost by this being a preview for now.
 */
export function PaletteStrip() {
  return (
    <div className="flex shrink-0 items-center gap-3 border-t border-border bg-card/30 px-3 py-2">
      <div className="flex items-center gap-1" aria-hidden>
        {COLORWAYS.okabeito.colors.map((c) => (
          <span
            key={c}
            className="size-4 rounded-[4px] ring-1 ring-black/10"
            style={{ backgroundColor: c }}
          />
        ))}
      </div>
      <span className="text-[11px] text-muted-foreground">Palette board — coming soon</span>
    </div>
  );
}
