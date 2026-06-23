"use client";

import * as React from "react";
import { ChevronDown, Loader2, TriangleAlert } from "lucide-react";

import {
  BAND_TONE,
  CONFIDENCE_META,
  type DataFit,
  type FileFitReport,
} from "@/lib/reproduction/data-fit";
import { Card } from "@/components/ui/card";
import { ConfidenceChip } from "@/components/ui/confidence-chip";

/**
 * The dropped-data fit panel (Slice 2). Renders the engine's verdict on each supplement the user
 * attached: a confidence BAND (what the score means), the 0-100 fit, the best-fitting analysis, and
 * a per-analysis breakdown. Shown on the Reproduce stage BEFORE Run (so a wrong/dirty file is
 * visibly poor and swappable) and on the Score stage AFTER (what the run actually fed). Honest by
 * construction — a "Not a fit" reads as the data being wrong for the analysis, never a Selom failure.
 */
export function DataFitPanel({
  fits,
  loading,
  error,
  title = "Is your data a fit?",
  sub = "Before you run, Selom checks each file you dropped against what these analyses need — the right modality, the right columns, and clean values.",
}: {
  fits: FileFitReport[];
  loading?: boolean;
  error?: string | null;
  title?: string;
  sub?: string;
}) {
  if (!loading && !error && fits.length === 0) return null;
  return (
    <section>
      <div>
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{sub}</p>
      </div>
      <div className="mt-4 space-y-3">
        {loading && (
          <p className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" />
            Checking your data…
          </p>
        )}
        {error && (
          <p className="inline-flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
            <TriangleAlert className="size-3.5" />
            {error}
          </p>
        )}
        {fits.map((ff) => (
          <FitCard key={ff.filename} ff={ff} />
        ))}
      </div>
    </section>
  );
}

function FitCard({ ff }: { ff: FileFitReport }) {
  const [open, setOpen] = React.useState(false);
  const meta = CONFIDENCE_META[ff.confidence];
  const best = ff.fits[0];
  const swap = ff.confidence === "not_a_fit" || ff.confidence === "unreadable";
  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-start gap-3 p-3.5">
        <ConfidenceChip tone={BAND_TONE[ff.confidence]} label={meta.label} size="md" title={meta.short} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <p className="truncate text-sm font-medium text-foreground" title={ff.filename}>
              {ff.filename}
            </p>
            <span className="rounded border border-border bg-muted px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              {ff.kind.replace(/_/g, " ")}
            </span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {meta.label} — {best ? best.reason : ff.note}
          </p>
          <FitScoreBar score={ff.score} color={meta.color} bestSkill={ff.best_skill} />
          {swap && (
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              Drop a different file for this analysis, or run anyway — it stays honestly ungraded.
            </p>
          )}
        </div>
      </div>
      {ff.fits.length > 0 && (
        <div className="border-t border-border/60 bg-muted/30">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex w-full items-center justify-between px-3.5 py-2 text-[11px] font-medium text-muted-foreground hover:text-foreground"
          >
            <span>Per-analysis fit ({ff.fits.length})</span>
            <ChevronDown className={`size-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
          {open && (
            <ul className="space-y-1 px-3.5 pb-3">
              {ff.fits.map((f) => (
                <PerSkillRow key={f.skill_id} f={f} />
              ))}
            </ul>
          )}
        </div>
      )}
    </Card>
  );
}

/**
 * A single (file, skill) data-fit verdict — the Product-A own-data band. Where {@link DataFitPanel}
 * ranks many dropped supplements against many analyses (reproduction), an own-data run is one file
 * against one skill, so this renders just that band: the confidence chip, the 0-100 fit, and the
 * engine's reason. Same source of truth (engine/compat) + the same band vocabulary as Product B, so
 * "is this the right, clean data for this analysis?" reads identically across both products. Renders
 * nothing when there's no fit (an uninspectable upload → `data_fit` is null, fail-soft).
 */
export function DataFitVerdict({ fit, skillName }: { fit?: DataFit | null; skillName?: string }) {
  if (!fit) return null;
  const meta = CONFIDENCE_META[fit.confidence];
  const swap = fit.confidence === "not_a_fit" || fit.confidence === "unreadable";
  return (
    <div className="rounded-xl border border-border bg-card/60 p-4" data-testid="data-fit-verdict">
      <div className="flex items-start gap-3">
        <ConfidenceChip tone={BAND_TONE[fit.confidence]} label={meta.label} size="md" title={meta.short} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground">
            Data fit{skillName ? <span className="text-muted-foreground"> · {skillName}</span> : null}
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{fit.reason}</p>
          <FitScoreBar score={fit.score} color={meta.color} bestSkill="" />
          {swap && (
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              This isn&apos;t the data this analysis needs — the figure may be misleading. Run another
              file, or treat this result with caution.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function FitScoreBar({ score, color, bestSkill }: { score: number; color: string; bestSkill: string }) {
  return (
    <div className="mt-2 flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full transition-[width]"
          style={{ width: `${Math.max(4, score)}%`, backgroundColor: color }}
        />
      </div>
      <span className="tabular shrink-0 text-[11px] font-medium text-muted-foreground">
        {score}/100
        {bestSkill && <span className="ml-1 text-muted-foreground/70">· {bestSkill}</span>}
      </span>
    </div>
  );
}

function PerSkillRow({ f }: { f: DataFit }) {
  const meta = CONFIDENCE_META[f.confidence];
  return (
    <li className="flex items-center gap-2 text-[11px]">
      <span
        aria-hidden
        className="size-1.5 shrink-0 rounded-full"
        style={{ backgroundColor: meta.color }}
      />
      <span className="font-medium text-foreground">{f.skill_id}</span>
      <span className="tabular text-muted-foreground/70">{f.score}</span>
      <span className="min-w-0 flex-1 truncate text-muted-foreground" title={f.reason}>
        {f.reason}
      </span>
    </li>
  );
}
