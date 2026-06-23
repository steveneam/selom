"use client";

import * as React from "react";
import { Microscope, Loader2, Check } from "lucide-react";
import { cn } from "@/lib/cn";
import type { Modality, QcReport } from "@/lib/projects/types";
import type { DataTypeOverride } from "@/lib/intake/inspect";

/**
 * The detected data-type header for a dropped dataset — the visible result of the layered
 * detector (format → keywords → modality). Shows the friendly label, how sure we are, and the
 * *why* (so the classification is transparent, never a black box), plus a "Set data type"
 * override (the L3 user-input layer). The override drives which cleaning pane appears below, so
 * the call is deliberate: getting the type right is what stops gene-subset cleaning landing on
 * an ERG / measurements table.
 */

const OVERRIDE_OPTIONS: { code: DataTypeOverride; label: string }[] = [
  { code: "erg", label: "ERG / electrophysiology" },
  { code: "sc_counts", label: "Single-cell RNA-seq" },
  { code: "bulk_counts", label: "Bulk RNA-seq counts" },
  { code: "de_results", label: "Differential-expression results" },
  { code: "proteomics", label: "Proteomics intensities" },
  { code: "generic_table", label: "Data table (no cleaning)" },
];

const CONFIDENCE_STYLE: Record<string, string> = {
  certain: "border-stage-publish/40 bg-[color-mix(in_oklab,var(--stage-publish)_12%,transparent)] text-stage-publish",
  likely: "border-border bg-muted/60 text-muted-foreground",
  unsure: "border-warn/40 bg-warn/10 text-warn",
};

export function DataTypeStrip({
  qc,
  modality,
  inspecting,
  canOverride,
  onSetDataType,
}: {
  qc?: QcReport;
  modality: Modality;
  inspecting: boolean;
  /** Real bytes present, so a live re-classify is possible. False ⇒ persisted profile, read-only. */
  canOverride: boolean;
  onSetDataType: (code: DataTypeOverride) => void;
}) {
  const label = qc?.profileLabel ?? modality;
  const confidence = qc?.confidence;
  const reason = qc?.reason;
  const code = qc?.profileCode;

  return (
    <div className="rounded-lg border border-border bg-background/40 p-3">
      <div className="flex items-start gap-3">
        <span aria-hidden className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg border border-border bg-card text-muted-foreground [&_svg]:size-4">
          {inspecting ? <Loader2 className="animate-spin" /> : <Microscope />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
              Detected data type
            </span>
            {confidence && (
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-1.5 py-px text-[10px] font-medium capitalize",
                  CONFIDENCE_STYLE[confidence] ?? CONFIDENCE_STYLE.unsure,
                )}
              >
                {confidence === "certain" && <Check className="size-3" />}
                {confidence}
              </span>
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

      {/* L3 override — proposed, not imposed: the scientist owns the final call. */}
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-border/60 pt-2.5">
        <label htmlFor="data-type-override" className="text-[11px] text-muted-foreground">
          {canOverride ? "Not right?" : "Re-upload to reclassify"}
        </label>
        <select
          id="data-type-override"
          value={code && OVERRIDE_OPTIONS.some((o) => o.code === code) ? code : ""}
          disabled={!canOverride}
          onChange={(e) => {
            const v = e.target.value as DataTypeOverride;
            if (v) onSetDataType(v);
          }}
          aria-label="Set the data type"
          title={canOverride ? "Override the detected data type" : "Re-upload this file to reclassify it"}
          className={cn(
            "max-w-[60%] rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
            !canOverride && "cursor-not-allowed opacity-50",
          )}
        >
          <option value="">Set data type…</option>
          {OVERRIDE_OPTIONS.map((o) => (
            <option key={o.code} value={o.code}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
