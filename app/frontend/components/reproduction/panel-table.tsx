"use client";

import * as React from "react";

import { tierLabel } from "@/lib/reproduction/api";
import type { Ledger, Panel, PanelScore, Validation } from "@/lib/reproduction/types";
import { AttributionChip, BlameChip, ProvenanceBadge, TierChip, VerdictChip } from "./atoms";

/**
 * The golden-vs-computed evidence table — the non-color reading of the heatmap. Each scored
 * panel shows its printed target (golden) against what Selom computed, with a verdict +
 * blame per metric. Out-of-scope panels are listed separately (excluded from the score).
 */
export function PanelTable({ ledger }: { ledger: Ledger }) {
  const panelByKey = new Map(ledger.panels.map((p) => [`${p.figure}${p.panel}`, p]));
  const scoreByKey = new Map((ledger.scorecard?.panel_scores ?? []).map((s) => [s.panel_key, s]));
  const oos = (ledger.scorecard?.panel_scores ?? []).filter((s) => !s.in_scope);

  return (
    <div className="space-y-3">
      {ledger.validations.map((v) => (
        <PanelRow
          key={v.panel_key}
          v={v}
          panel={panelByKey.get(v.panel_key)}
          score={scoreByKey.get(v.panel_key)}
        />
      ))}

      {oos.length > 0 && (
        <div className="rounded-lg border border-dashed border-border bg-card/40 px-4 py-3">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Out of scope — excluded from the score
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {oos.map((s) => (
              <span
                key={s.panel_key}
                className="flex items-center gap-1.5 rounded-md border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
                title={s.note}
              >
                <span className="tabular font-medium text-foreground/80">{s.panel_key}</span>
                {s.provenance && <ProvenanceBadge provenance={s.provenance} />}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PanelRow({
  v,
  panel,
  score,
}: {
  v: Validation;
  panel?: Panel;
  score?: PanelScore;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex flex-wrap items-center gap-2 border-b border-border bg-card/60 px-4 py-2.5">
        <span className="tabular text-sm font-semibold text-foreground">{v.panel_key}</span>
        {panel?.skill_id && (
          <span className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {panel.skill_id}
          </span>
        )}
        {score && <TierChip tier={score.tier} color={score.color} />}
        {score && <AttributionChip attribution={score.attribution} />}
        {score?.provenance && <ProvenanceBadge provenance={score.provenance} />}
        <span className="ml-auto tabular text-xs text-muted-foreground">
          {score?.reproducibility != null ? `${score.reproducibility} · ${tierLabel(score.tier)}` : ""}
        </span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-muted-foreground">
            <th className="px-4 py-1.5 font-medium">Metric</th>
            <th className="px-3 py-1.5 text-right font-medium">Golden</th>
            <th className="px-3 py-1.5 text-right font-medium">Computed</th>
            <th className="px-3 py-1.5 font-medium">Verdict</th>
            <th className="px-4 py-1.5 font-medium">Blame</th>
          </tr>
        </thead>
        <tbody>
          {v.results.map((r, i) => (
            <tr key={`${r.metric}-${i}`} className="border-t border-border/60">
              <td className="px-4 py-2 align-top">
                <span className="text-foreground/90">{r.metric}</span>
                {r.note && (
                  <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                    {r.note}
                  </span>
                )}
              </td>
              <td className="tabular px-3 py-2 text-right align-top text-foreground/80">
                {fmt(r.golden)}
              </td>
              <td className="tabular px-3 py-2 text-right align-top text-foreground/80">
                {fmt(r.computed)}
              </td>
              <td className="px-3 py-2 align-top">
                <VerdictChip verdict={r.verdict} />
              </td>
              <td className="px-4 py-2 align-top">
                <BlameChip blame={r.blame} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function fmt(v: number | string | null): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(3);
  return v;
}
