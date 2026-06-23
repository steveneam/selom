"use client";

import * as React from "react";
import { ArrowRight, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/cn";
import type { Modality, QcReport } from "@/lib/projects/types";

/**
 * Before & after cleaning — Selom's "no black box" promise made literal.
 *
 * Shows the matrix shape *as dropped* (raw) vs *after cleaning*, with the change
 * highlighted, and lists every cleaning step as a TOGGLE: cleaning is proposed,
 * not imposed, so the scientist can switch a step off and watch the "after"
 * recompute before they proceed.
 */

function labelsFor(m: Modality): { obs: string; var: string } {
  switch (m) {
    case "scRNA-seq":
      return { obs: "cells", var: "genes" };
    case "bulk RNA-seq":
      return { obs: "samples", var: "genes" };
    case "proteomics":
      return { obs: "samples", var: "proteins" };
    default:
      return { obs: "rows", var: "features" };
  }
}

export function CleaningReport({
  qc,
  modality,
  disabledSteps,
  onToggleStep,
}: {
  qc: QcReport;
  modality: Modality;
  /** Step ids the user has switched off (controlled by the parent so a run can honour them). */
  disabledSteps: Set<string>;
  onToggleStep: (id: string) => void;
}) {
  const steps = qc.cleaningSteps ?? [];
  // Axis labels come from the engine (cells/genes, samples/genes, rows/columns…) when classified
  // live; fall back to the modality default for the offline/mock path.
  const eng = labelsFor(modality);
  const L = { obs: qc.obsLabel ?? eng.obs, var: qc.varLabel ?? eng.var };
  const rawObs = qc.nObsRaw ?? qc.nObs;
  const rawVar = qc.nVarRaw ?? qc.nVar;
  // Dynamic: only a count matrix gets the before/after cleaning editor. A results / generic / ERG
  // table is used as-is — an honest empty state, never the gene-subset cleaning forced on every file.
  const applies = qc.applies ?? steps.length > 0;

  if (!applies) {
    return (
      <div className="space-y-3">
        <p className="text-sm font-semibold text-foreground">Cleaning</p>
        <div className="rounded-lg border border-border bg-background/40 p-3">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Your data</p>
          <p className="tabular mt-1.5 text-lg font-semibold leading-none text-foreground">
            {rawObs.toLocaleString()} <span className="text-xs font-normal text-muted-foreground">{L.obs}</span>
            <span className="px-1.5 text-xs font-normal text-muted-foreground">×</span>
            {rawVar.toLocaleString()} <span className="text-xs font-normal text-muted-foreground">{L.var}</span>
          </p>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            {qc.cleaning?.[0] ?? "Used as-is — no cleaning needed for this data type."}
          </p>
        </div>
        {qc.guardrails.length > 0 && <Guardrails guardrails={qc.guardrails} />}
      </div>
    );
  }

  const obsAfter = rawObs + steps.filter((s) => !disabledSteps.has(s.id)).reduce((a, s) => a + (s.obsDelta ?? 0), 0);
  const varAfter = rawVar + steps.filter((s) => !disabledSteps.has(s.id)).reduce((a, s) => a + (s.varDelta ?? 0), 0);

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-semibold text-foreground">Before &amp; after cleaning</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Cleaning is proposed, not imposed — toggle any step off and the result updates before you proceed.
        </p>
      </div>

      {/* raw → cleaned */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-stretch gap-2">
        <ShapeCard tone="raw" title="As you dropped it" obs={rawObs} vars={rawVar} L={L} />
        <ArrowRight className="size-4 self-center text-muted-foreground" aria-hidden />
        <ShapeCard
          tone="clean"
          title="After cleaning"
          obs={obsAfter}
          vars={varAfter}
          obsDelta={obsAfter - rawObs}
          varDelta={varAfter - rawVar}
          L={L}
        />
      </div>

      {/* editable steps */}
      {steps.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border">
          {steps.map((s) => {
            const on = !disabledSteps.has(s.id);
            return (
              <li key={s.id} className="flex items-start gap-3 p-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cn("text-sm font-medium", on ? "text-foreground" : "text-muted-foreground line-through")}>
                      {s.label}
                    </span>
                    <EffectChip
                      obsDelta={s.obsDelta}
                      varDelta={s.varDelta}
                      kind={s.kind}
                      muted={!on}
                      L={L}
                    />
                  </div>
                  {s.detail && <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">{s.detail}</p>}
                </div>
                <Toggle on={on} label={`${on ? "Disable" : "Enable"} ${s.label}`} onClick={() => onToggleStep(s.id)} />
              </li>
            );
          })}
        </ul>
      )}

      {/* guardrails ride alongside — the WHY behind the steps */}
      {qc.guardrails.length > 0 && <Guardrails guardrails={qc.guardrails} />}
    </div>
  );
}

/** Honest data-quality flags — the WHY behind (or instead of) the cleaning steps. */
function Guardrails({ guardrails }: { guardrails: QcReport["guardrails"] }) {
  return (
    <div className="space-y-1.5">
      {guardrails.map((g, i) => (
        <div
          key={i}
          className={cn(
            "flex items-start gap-2 rounded-md border px-3 py-2 text-xs",
            g.level === "error"
              ? "border-destructive/40 bg-destructive/10 text-destructive"
              : g.level === "warn"
                ? "border-warn/40 bg-warn/10 text-warn"
                : "border-border bg-background/40 text-muted-foreground",
          )}
        >
          <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span className="leading-relaxed">{g.msg}</span>
        </div>
      ))}
    </div>
  );
}

function ShapeCard({
  tone,
  title,
  obs,
  vars,
  obsDelta = 0,
  varDelta = 0,
  L,
}: {
  tone: "raw" | "clean";
  title: string;
  obs: number;
  vars: number;
  obsDelta?: number;
  varDelta?: number;
  L: { obs: string; var: string };
}) {
  const changed = obsDelta !== 0 || varDelta !== 0;
  const fmt = (n: number) => `${n > 0 ? "+" : ""}${n.toLocaleString()}`;
  return (
    <div
      className={cn(
        "rounded-lg border p-3",
        tone === "clean"
          ? "border-stage-publish/40 bg-[color-mix(in_oklab,var(--stage-publish)_8%,transparent)]"
          : "border-border bg-background/40",
      )}
    >
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{title}</p>
      <p className="tabular mt-1.5 text-lg font-semibold leading-none text-foreground">
        {obs.toLocaleString()} <span className="text-xs font-normal text-muted-foreground">{L.obs}</span>
      </p>
      <p className="tabular mt-1 text-sm text-muted-foreground">
        {vars.toLocaleString()} {L.var}
      </p>
      {/* Delta line is ALWAYS reserved (even when empty) so toggling a step never
          changes the card height and reflows the panel. */}
      <p className="tabular mt-1.5 min-h-4 text-[11px] text-warn">
        {tone === "clean" ? (
          changed ? (
            <>
              {obsDelta !== 0 && `${fmt(obsDelta)} ${L.obs}`}
              {obsDelta !== 0 && varDelta !== 0 && " · "}
              {varDelta !== 0 && `${fmt(varDelta)} ${L.var}`}
            </>
          ) : (
            <span className="text-muted-foreground">no rows removed</span>
          )
        ) : null}
      </p>
    </div>
  );
}

function EffectChip({
  obsDelta,
  varDelta,
  kind,
  muted,
  L,
}: {
  obsDelta?: number;
  varDelta?: number;
  kind: "filter" | "transform" | "selection";
  muted: boolean;
  L: { obs: string; var: string };
}) {
  let text: string;
  if (obsDelta) text = `${obsDelta.toLocaleString()} ${L.obs}`;
  else if (varDelta) text = `${varDelta.toLocaleString()} ${L.var}`;
  else text = kind === "selection" ? "flags features" : "rescales values";
  return (
    <span
      className={cn(
        "tabular rounded-md border px-1.5 py-px text-[10px] font-medium",
        muted ? "border-border text-muted-foreground/70" : "border-border bg-muted/50 text-muted-foreground",
      )}
    >
      {text}
    </span>
  );
}

function Toggle({ on, onClick, label }: { on: boolean; onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onClick}
      className={cn(
        "relative mt-0.5 inline-flex h-5 w-9 shrink-0 items-center rounded-full px-0.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
        on ? "bg-primary" : "bg-input",
      )}
    >
      <span
        className={cn(
          "block size-4 rounded-full bg-white shadow-sm transition-transform",
          on ? "translate-x-4" : "translate-x-0",
        )}
      />
    </button>
  );
}
