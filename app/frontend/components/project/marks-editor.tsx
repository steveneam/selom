"use client";

import * as React from "react";
import { RotateCcw, Crosshair } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/cn";
import {
  clearManualMark,
  manualMarkCount,
  manualMarkValue,
  parseManualMarks,
  roleLabel,
  serializeManualMarks,
  setManualMark,
  type MarkRole,
  type SeededMark,
} from "@/lib/erg/marks";
import type { SkillParams } from "@/lib/skills-api";

/**
 * Marks editor (docs/erg-manual-marks/spec.md R5) — the numeric half of the operator override, in
 * the Figure-data stage where re-runs live. It reads the skill-seeded landmark times
 * (`meta.selom.marks`), lets the scientist set/confirm each a/b (or N1/P1) TIME per cell, and writes
 * the `manual_marks` param; the metric re-measures the amplitude at that time on re-run. The canvas
 * dots share this exact state — a drag and a typed time are the same edit. Device-measured marks are
 * read-only (the device wins). Reset returns a marker to the auto seed.
 */
export function MarksEditor({
  seededMarks,
  params,
  onParamsChange,
}: {
  seededMarks: SeededMark[];
  params: SkillParams;
  /** The figure-data setParams — used with functional updates so a toggle + a numeric edit fired
   *  back-to-back can't clobber each other (each reads the latest params, not a stale closure). */
  onParamsChange: React.Dispatch<React.SetStateAction<SkillParams>>;
}) {
  const manual = React.useMemo(() => parseManualMarks(params.manual_marks), [params.manual_marks]);
  const nManual = manualMarkCount(manual);
  // The dots-toggle reflects the PENDING `marks` param (what the next re-run will apply), not the
  // currently-rendered figure — otherwise toggling it on would snap back to off (the dots only
  // exist after the re-run). Fall back to the rendered figure's state when the param is unset.
  const renderedDots = seededMarks.some((m) => m.trace !== undefined);
  const dotsOn = params.marks === undefined ? renderedDots : String(params.marks) === "true";

  // Group marks by cell (segment), preserving first-seen order.
  const cells = React.useMemo(() => {
    const bySeg = new Map<string, { label: string; marks: SeededMark[] }>();
    for (const m of seededMarks) {
      const cell = bySeg.get(m.segment) ?? { label: m.label, marks: [] };
      cell.marks.push(m);
      bySeg.set(m.segment, cell);
    }
    return [...bySeg.values()];
  }, [seededMarks]);

  // All writes are functional updates that re-read the latest manual_marks from `p`, so a numeric
  // edit and the dots toggle (or two edits) fired before a re-render can't overwrite each other.
  const setMark = (segment: string, role: MarkRole, ms: number) =>
    onParamsChange((p) => ({
      ...p,
      manual_marks: serializeManualMarks(setManualMark(parseManualMarks(p.manual_marks), segment, role, ms)),
    }));
  const resetMark = (segment: string, role: MarkRole) =>
    onParamsChange((p) => ({
      ...p,
      manual_marks: serializeManualMarks(clearManualMark(parseManualMarks(p.manual_marks), segment, role)),
    }));

  return (
    <div className="rounded-xl border border-border bg-card/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            <Crosshair className="size-3.5" /> Landmark marks
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground/80">
            Set the a/b (or N1/P1) <span className="text-foreground/80">time</span> per cell — the
            amplitude is re-measured there on re-run. Or drag the dots on the figure.
          </p>
        </div>
        {nManual > 0 && (
          <button
            type="button"
            onClick={() => onParamsChange((p) => ({ ...p, manual_marks: "" }))}
            className="shrink-0 rounded-md border border-border px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            Reset all to auto
          </button>
        )}
      </div>

      <label className="mt-3 flex items-center justify-between gap-2 rounded-lg border border-border/70 bg-background/40 px-2.5 py-1.5">
        <span className="text-xs text-foreground/90">Show landmark dots on the figure</span>
        <Switch
          checked={dotsOn}
          onCheckedChange={(v) => onParamsChange((p) => ({ ...p, marks: v }))}
          aria-label="Show landmark dots"
        />
      </label>

      <div className="mt-3 space-y-2.5">
        {cells.map((cell) => (
          <div key={cell.marks[0].segment} className="rounded-lg border border-border/70 bg-background/40 p-2">
            <p className="mb-1.5 truncate text-[11px] font-medium text-foreground/80">{cell.label}</p>
            <div className="space-y-1">
              {cell.marks.map((m) => (
                <MarkRow
                  key={m.role}
                  mark={m}
                  override={manualMarkValue(manual, m.segment, m.role)}
                  onSet={(ms) => setMark(m.segment, m.role, ms)}
                  onReset={() => resetMark(m.segment, m.role)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      <p className="mt-2.5 text-[11px] text-muted-foreground/80">
        {nManual > 0
          ? `${nManual} marker${nManual > 1 ? "s" : ""} operator-set — re-run to apply.`
          : "All markers auto-detected. Adjust a time, then re-run."}
      </p>
    </div>
  );
}

function MarkRow({
  mark,
  override,
  onSet,
  onReset,
}: {
  mark: SeededMark;
  override: number | undefined;
  onSet: (ms: number) => void;
  onReset: () => void;
}) {
  const isDevice = mark.source === "device";
  const isManual = override !== undefined;
  // The shown time = the operator override if set, else the auto seed.
  const shown = override ?? mark.tMs;
  // Free-typed draft, reset to `shown` whenever it changes externally (after a re-run) — the
  // adjust-state-during-render pattern, so no effect is needed (react.dev/reference/react/useState).
  const [draft, setDraft] = React.useState(String(shown));
  const [seed, setSeed] = React.useState(shown);
  if (seed !== shown) {
    setSeed(shown);
    setDraft(String(shown));
  }

  const commit = () => {
    const n = parseFloat(draft);
    if (Number.isFinite(n) && n !== shown) onSet(n);
    else setDraft(String(shown));
  };

  return (
    <div className="flex items-center gap-2">
      <span className="w-12 shrink-0 text-[11px] font-medium text-foreground/70">{roleLabel(mark.role)}</span>
      <div className="relative flex-1">
        <Input
          value={draft}
          inputMode="decimal"
          aria-label={`${mark.label} ${roleLabel(mark.role)} time (ms)`}
          disabled={isDevice}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          }}
          className={cn("tabular h-7 pr-7 text-xs", isManual && "border-primary/50")}
        />
        <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-[10px] text-muted-foreground">
          ms
        </span>
      </div>
      <span className="tabular w-16 shrink-0 text-right text-[11px] text-muted-foreground">
        {mark.uv != null ? `${mark.uv} µV` : "—"}
      </span>
      <SourceTag source={mark.source} manual={isManual} />
      <button
        type="button"
        aria-label={`Reset ${roleLabel(mark.role)} to auto`}
        title={isManual ? "Reset to auto" : "Auto-detected"}
        onClick={onReset}
        disabled={!isManual}
        className={cn(
          "grid size-6 shrink-0 place-items-center rounded-md transition-colors",
          isManual
            ? "cursor-pointer text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            : "cursor-default text-transparent",
        )}
      >
        <RotateCcw className="size-3.5" />
      </button>
    </div>
  );
}

function SourceTag({ source, manual }: { source: SeededMark["source"]; manual: boolean }) {
  const label = source === "device" ? "device" : manual ? "manual" : "auto";
  const tone =
    label === "manual"
      ? "border-primary/40 text-primary"
      : label === "device"
        ? "border-border text-muted-foreground/70"
        : "border-border text-muted-foreground";
  return (
    <span className={cn("w-12 shrink-0 rounded border px-1 py-px text-center text-[9px] uppercase tracking-wide", tone)}>
      {label}
    </span>
  );
}
