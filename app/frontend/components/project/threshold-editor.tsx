"use client";

import * as React from "react";
import { SlidersHorizontal } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  bucketCounts,
  clampThresholds,
  gatherPoints,
  readThresholds,
} from "@/lib/volcano/thresholds";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { SkillParams } from "@/lib/skills/api";

/**
 * Threshold editor (docs/figure-data-capabilities/generalization-spec.md §F) — the numeric half of the
 * volcano threshold direct-manipulation, in the Figure-data stage. It reads the figure's current
 * FC / p-value cuts (from the threshold line shapes), lets the scientist set them, and writes the
 * `fc_threshold` / `fdr_threshold` params. The points re-colour LIVE (the parent's preview applies the
 * staged thresholds client-side) and the up/down/n.s. count updates as you type; the ONE re-run
 * recomputes the gene table + labels. The draggable dashed lines on the canvas share this exact state.
 */

// Volcano bucket colours — KEEP IN SYNC with app/backend/skills/volcano/run.py (UP / DOWN / NS).
const BUCKET_COLORS = { up: "#22d3ee", down: "#f43f5e", ns: "#5b6b80" } as const;

function num(v: unknown, fallback: number): number {
  const n = typeof v === "number" ? v : typeof v === "string" ? parseFloat(v) : NaN;
  return Number.isFinite(n) ? n : fallback;
}

function round(v: number, dp: number): number {
  const f = 10 ** dp;
  return Math.round(v * f) / f;
}

export function ThresholdEditor({
  figureSpec,
  params,
  onParamsChange,
}: {
  /** The active figure spec — its bucket traces supply the points for the live count. */
  figureSpec: FigureSpec | null | undefined;
  params: SkillParams;
  /** The figure-data setParams (functional updates so back-to-back fc/fdr edits don't clobber). */
  onParamsChange: React.Dispatch<React.SetStateAction<SkillParams>>;
}) {
  const base = React.useMemo(() => readThresholds(figureSpec ?? null), [figureSpec]);
  const points = React.useMemo(() => gatherPoints(figureSpec ?? null), [figureSpec]);
  // Staged value = the param if set, else the figure's current threshold.
  const fc = num(params.fc_threshold, base?.fc ?? 1);
  const fdr = num(params.fdr_threshold, base?.fdr ?? 0.05);
  const readout = React.useMemo(() => bucketCounts(points, { fc, fdr }), [points, fc, fdr]);

  const setFc = (v: number) =>
    onParamsChange((p) => ({ ...p, fc_threshold: clampThresholds({ fc: v, fdr }).fc }));
  const setFdr = (v: number) =>
    onParamsChange((p) => ({ ...p, fdr_threshold: clampThresholds({ fc, fdr: v }).fdr }));

  return (
    <div className="rounded-xl border border-border bg-card/60 p-4">
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          <SlidersHorizontal className="size-3.5" /> Thresholds
        </p>
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground/80">
          Set the fold-change and p-value cuts — points re-colour{" "}
          <span className="text-foreground/80">live</span>. Re-run to update the gene table + labels.
          Or drag the dashed lines on the figure.
        </p>
      </div>

      <div className="mt-3 space-y-2">
        <NumRow label="|log2FC| ≥" value={round(fc, 3)} ariaLabel="Fold-change threshold" onSet={setFc} />
        <NumRow label="adj. p ≤" value={round(fdr, 4)} ariaLabel="Adjusted p-value threshold" onSet={setFdr} />
      </div>

      {/* Fail-safe empty state (Task B2): a volcano whose bucket traces carry no points (a partial /
          not-yet-run spec) shows "No points yet" rather than a misleading 0 / 0 / 0 readout. */}
      {points.length === 0 ? (
        <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground/70">
          No points yet — run the skill to populate the volcano, then the counts update live.
        </p>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5" aria-label="Bucket counts">
          <Count color={BUCKET_COLORS.up} label="up" n={readout.up} />
          <Count color={BUCKET_COLORS.down} label="down" n={readout.down} />
          <Count color={BUCKET_COLORS.ns} label="n.s." n={readout.ns} />
        </div>
      )}
    </div>
  );
}

function Count({ color, label, n }: { color: string; label: string; n: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
      <span className="size-2.5 rounded-full border border-white shadow-sm" style={{ backgroundColor: color }} />
      <span className="tabular font-medium text-foreground/80">{n}</span> {label}
    </span>
  );
}

function NumRow({
  label,
  value,
  ariaLabel,
  onSet,
}: {
  label: string;
  value: number;
  ariaLabel: string;
  onSet: (n: number) => void;
}) {
  // Free-typed draft, reset to `value` whenever it changes externally (after a drag or re-run) — the
  // adjust-state-during-render pattern, so no effect is needed (matches MarkRow in marks-editor.tsx).
  const [draft, setDraft] = React.useState(String(value));
  const [seed, setSeed] = React.useState(value);
  if (seed !== value) {
    setSeed(value);
    setDraft(String(value));
  }
  const commit = () => {
    const n = parseFloat(draft);
    if (Number.isFinite(n) && n !== value) onSet(n);
    else setDraft(String(value));
  };
  return (
    <label className="flex items-center gap-2">
      <span className="w-20 shrink-0 text-[11px] font-medium text-foreground/70">{label}</span>
      <Input
        value={draft}
        inputMode="decimal"
        aria-label={ariaLabel}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
        className="tabular h-7 flex-1 text-xs"
      />
    </label>
  );
}
