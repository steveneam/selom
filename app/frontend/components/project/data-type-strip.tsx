"use client";

import * as React from "react";
import { Microscope, Loader2, AlertTriangle, RotateCcw } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ConfidenceChip } from "@/components/ui/confidence-chip";
import type { ConfidenceTone } from "@/lib/ui/confidence";
import type { Modality, QcReport } from "@/lib/projects/types";
import type { DataTypeOverride } from "@/lib/intake/inspect";

/**
 * The detected data-type header for a dropped dataset — the visible result of the layered
 * detector (format → content → filename → user). Shows the friendly label, how sure we are, and
 * the *why* (so the classification is transparent, never a black box), plus a "Set data type"
 * override (the user-input layer). When the filename disagrees with the content it raises a calm
 * mismatch nudge; when the engine has runner-up guesses it offers them as one-click alternatives;
 * an explicit override can be reset back to auto. The chosen type drives which cleaning pane
 * appears below, so the call is deliberate: getting the type right is what stops gene-subset
 * cleaning landing on an ERG / measurements table — and the same robustness applies to every
 * modality (scRNA, bulk, DE, proteomics, metabolomics), not just ERG.
 */

const OVERRIDE_OPTIONS: { code: DataTypeOverride; label: string }[] = [
  { code: "erg", label: "ERG / electrophysiology" },
  { code: "sc_counts", label: "Single-cell RNA-seq" },
  { code: "bulk_counts", label: "Bulk RNA-seq counts" },
  { code: "de_results", label: "Differential-expression results" },
  { code: "proteomics", label: "Proteomics intensities" },
  { code: "generic_table", label: "Data table (no cleaning)" },
];
const OVERRIDE_CODES = new Set<string>(OVERRIDE_OPTIONS.map((o) => o.code));

// The detector's three levels → the shared confidence tones. `likely` maps to the quiet slate
// `neutral` (deliberately recessive, so a middling guess doesn't shout); `certain` reads strong-green
// and `unsure` amber, matching every other confidence surface.
const CONFIDENCE_TONE: Record<"certain" | "likely" | "unsure", ConfidenceTone> = {
  certain: "positive",
  likely: "neutral",
  unsure: "caution",
};

export function DataTypeStrip({
  qc,
  modality,
  inspecting,
  canOverride,
  onSetDataType,
  onResetDataType,
}: {
  qc?: QcReport;
  modality: Modality;
  inspecting: boolean;
  /** Real bytes present, so a live re-classify is possible. False ⇒ persisted profile, read-only. */
  canOverride: boolean;
  onSetDataType: (code: DataTypeOverride) => void;
  /** Clear an explicit override and fall back to the auto-detected type (re-inspect, no hint). */
  onResetDataType?: () => void;
}) {
  const label = qc?.profileLabel ?? modality;
  const confidence = qc?.confidence;
  const reason = qc?.reason;
  const code = qc?.profileCode;
  const overridden = qc?.overridden ?? false;
  const mismatch = qc?.mismatch;

  // The engine's runner-up guesses (ranked), as one-click alternatives — only those the user can
  // actually pick, never the current choice. Surfaced when we hold live bytes and haven't been
  // overridden (an override already is the user's deliberate call).
  const alternatives = canOverride && !overridden
    ? (qc?.candidates ?? [])
        .filter((c) => c.code !== code && OVERRIDE_CODES.has(c.code))
        .slice(0, 2)
    : [];

  return (
    <div className="rounded-lg border border-border bg-background/40 p-3">
      <div className="flex items-start gap-3">
        <span aria-hidden className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg border border-border bg-card text-muted-foreground [&_svg]:size-4">
          {inspecting ? <Loader2 className="animate-spin" /> : <Microscope />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
              {/* A4 fix: without a live qc verdict, `label` below is only the filename heuristic —
                  say so, rather than implying a real classification happened. */}
              {inspecting ? "Detecting data type" : qc ? "Detected data type" : "Guessed from filename"}
            </span>
            {confidence && !inspecting && (
              <ConfidenceChip
                tone={CONFIDENCE_TONE[confidence]}
                label={confidence}
                size="xs"
                className="capitalize"
              />
            )}
          </div>
          <p className="mt-0.5 truncate text-sm font-semibold text-foreground">
            {inspecting ? "Classifying…" : label}
          </p>
          {reason && !inspecting && (
            <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">{reason}</p>
          )}
        </div>
      </div>

      {/* Mismatch nudge — the filename disagrees with what the content looks like. Content wins
          (best practice: a renamed file shouldn't overrule its bytes); this just flags it so the
          user can override if the name was right. Full-border warn tint, not a side stripe. */}
      {mismatch && !overridden && !inspecting && (
        <div className="mt-2.5 flex items-start gap-1.5 rounded-md border border-warn/30 bg-warn/10 px-2 py-1.5 text-[11px] leading-relaxed text-warn">
          <AlertTriangle aria-hidden className="mt-px size-3.5 shrink-0" />
          <span>{mismatch}</span>
        </div>
      )}

      {/* Runner-up guesses — one-click alternatives from the ranked candidate list (faster than
          hunting in the dropdown). Quiet chips so the primary verdict stays the focus. */}
      {alternatives.length > 0 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-muted-foreground">Or:</span>
          {alternatives.map((c) => (
            <button
              key={c.code}
              type="button"
              title={c.reason}
              onClick={() => onSetDataType(c.code as DataTypeOverride)}
              className="inline-flex items-center rounded-md border border-border bg-card px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {c.label}
            </button>
          ))}
        </div>
      )}

      {/* User layer — proposed, not imposed: the scientist owns the final call. Uses the same Radix
          Select as the intake questionnaire + inspector, so the form-control vocabulary is
          consistent across the surface (not a one-off native control). */}
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-border/60 pt-2.5">
        {overridden && canOverride && onResetDataType ? (
          <button
            type="button"
            onClick={onResetDataType}
            className="inline-flex shrink-0 items-center gap-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&_svg]:size-3"
          >
            <RotateCcw aria-hidden />
            Reset to auto-detected
          </button>
        ) : (
          <span className="shrink-0 text-[11px] text-muted-foreground">
            {canOverride ? "Not right?" : "Re-upload to reclassify"}
          </span>
        )}
        <Select
          value={code && OVERRIDE_OPTIONS.some((o) => o.code === code) ? code : undefined}
          disabled={!canOverride}
          onValueChange={(v) => onSetDataType(v as DataTypeOverride)}
        >
          <SelectTrigger
            aria-label="Set the data type"
            title={canOverride ? "Override the detected data type" : "Re-upload this file to reclassify it"}
            className="h-8 w-[58%] text-xs"
          >
            <SelectValue placeholder="Set data type…" />
          </SelectTrigger>
          <SelectContent>
            {OVERRIDE_OPTIONS.map((o) => (
              <SelectItem key={o.code} value={o.code} className="text-xs">
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
