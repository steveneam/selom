import { cn } from "@/lib/ui/cn";

/**
 * Selom mark — a molecular hexagon (flat-top) with vertex + centre nodes and a
 * connecting triad, echoing the brand emblem. Strokes/nodes use `currentColor`,
 * so colour it with text utilities (e.g. `text-primary` for the cyan glow).
 */
export function SelomMark({ className }: { className?: string }) {
  // Flat-top hexagon vertices (centre 16,16, r 11), clockwise from top-right.
  const v = [
    [21.5, 6.47],
    [27, 16],
    [21.5, 25.53],
    [10.5, 25.53],
    [5, 16],
    [10.5, 6.47],
  ] as const;
  const points = v.map(([x, y]) => `${x},${y}`).join(" ");

  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className={cn("size-6", className)}
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points={points} className="opacity-70" />
      {/* triad spokes from centre to alternating vertices */}
      <line x1="16" y1="16" x2={v[0][0]} y2={v[0][1]} className="opacity-45" />
      <line x1="16" y1="16" x2={v[2][0]} y2={v[2][1]} className="opacity-45" />
      <line x1="16" y1="16" x2={v[4][0]} y2={v[4][1]} className="opacity-45" />
      {/* vertex nodes */}
      {v.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={1.7} fill="currentColor" stroke="none" />
      ))}
      {/* centre node */}
      <circle cx="16" cy="16" r={2.6} fill="currentColor" stroke="none" />
      <circle cx="16" cy="16" r={2.6} className="opacity-40" />
    </svg>
  );
}

/** Mark + uppercase tracked wordmark, matching the brand lockup. */
export function SelomWordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <SelomMark className="size-6 text-primary [filter:drop-shadow(0_0_6px_color-mix(in_oklab,var(--primary)_55%,transparent))]" />
      <span className="text-[15px] font-semibold uppercase tracking-[0.22em] text-foreground">
        Selom
      </span>
    </span>
  );
}
