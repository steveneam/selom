"use client";

import * as React from "react";
import Link from "next/link";
import { ScanLine } from "lucide-react";

import { digitizeHref, panelAssetUrl, tierLabel } from "@/lib/reproduction/api";
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
  const allScores = ledger.scorecard?.panel_scores ?? [];
  const oos = allScores.filter((s) => !s.in_scope);
  // In-scope panels the live drive couldn't auto-score (no printed target, no matched data, or the
  // metric wasn't readable) — shown honestly so they aren't silently absent (L4) and so each grey
  // heatmap cell has a scroll target. Empty for the staged showcase ledgers (all validated).
  const validatedKeys = new Set(ledger.validations.map((v) => v.panel_key));
  const ungraded = allScores.filter(
    (s) => s.in_scope && s.reproducibility == null && !validatedKeys.has(s.panel_key),
  );

  return (
    <div className="space-y-3">
      {ledger.validations.map((v) => (
        <PanelRow
          key={v.panel_key}
          v={v}
          panel={panelByKey.get(v.panel_key)}
          score={scoreByKey.get(v.panel_key)}
          slug={ledger.paper.slug}
        />
      ))}

      {ungraded.length > 0 && (
        <div className="rounded-lg border border-dashed border-border bg-card/40 px-4 py-3">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Computed — not auto-validated
          </p>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-muted-foreground">
            In scope, but Selom couldn&apos;t auto-score these — no printed target, no matched data, or
            the metric wasn&apos;t readable from the run. Shown honestly; excluded from the score, never
            counted as a defect.
          </p>
          <ul className="mt-2.5 space-y-1.5">
            {ungraded.map((s) => {
              const panel = panelByKey.get(s.panel_key);
              return (
                <li
                  key={s.panel_key}
                  id={`panel-${s.panel_key}`}
                  className="flex scroll-mt-6 flex-wrap items-center gap-x-2 gap-y-1 text-xs"
                >
                  <span className="tabular font-medium text-foreground/80">{s.panel_key}</span>
                  {panel?.skill_id && (
                    <span className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                      {panel.skill_id}
                    </span>
                  )}
                  {s.note && <span className="text-muted-foreground">{s.note}</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {oos.length > 0 && (
        <div className="rounded-lg border border-dashed border-border bg-card/40 px-4 py-3">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Out of scope — excluded from the score
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {oos.map((s) => (
              <span
                key={s.panel_key}
                id={`panel-${s.panel_key}`}
                className="flex scroll-mt-6 items-center gap-1.5 rounded-md border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
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
  slug,
}: {
  v: Validation;
  panel?: Panel;
  score?: PanelScore;
  slug: string;
}) {
  const lift = panel?.lift ?? null;
  return (
    <div
      id={`panel-${v.panel_key}`}
      className="scroll-mt-6 overflow-hidden rounded-lg border border-border bg-card"
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-border bg-card/60 px-4 py-2.5">
        {lift?.thumbnail_url && <PanelThumb lift={lift} slug={slug} panelKey={v.panel_key} />}
        <span className="tabular text-sm font-semibold text-foreground">{v.panel_key}</span>
        {panel?.skill_id && (
          <span className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {panel.skill_id}
          </span>
        )}
        {score && <TierChip tier={score.tier} color={score.color} />}
        {score && <AttributionChip attribution={score.attribution} />}
        {score?.provenance && <ProvenanceBadge provenance={score.provenance} />}
        <div className="ml-auto flex items-center gap-2.5">
          {lift?.digitizable && panel && (
            <DigitizeLink slug={slug} panelKey={v.panel_key} lift={lift} form={panel.chart_form} />
          )}
          <span className="tabular text-xs text-muted-foreground">
            {score?.reproducibility != null ? `${score.reproducibility} · ${tierLabel(score.tier)}` : ""}
          </span>
        </div>
      </div>
      {/* table-fixed + a shared colgroup so Metric/Golden/Computed/Verdict/Blame land at the SAME
          x-position on every panel card — the columns line up when scanning down the page (without
          this, each card's table auto-sizes independently and the columns jump left/right). */}
      <table className="w-full table-fixed text-sm">
        <colgroup>
          <col />
          <col className="w-24" />
          <col className="w-24" />
          <col className="w-28" />
          <col className="w-48" />
        </colgroup>
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

/** The lifted published-figure panel, shown as a small reference thumbnail next to its key.
 *  Click opens the full lift in a new tab. Purely a visual reference — never scored. */
function PanelThumb({
  lift,
  slug,
  panelKey,
}: {
  lift: NonNullable<Panel["lift"]>;
  slug: string;
  panelKey: string;
}) {
  const [ok, setOk] = React.useState(true);
  const src = panelAssetUrl(lift.thumbnail_url);
  if (!ok) return null; // graceful: if the asset can't load (e.g. mock mode), show nothing
  return (
    <a
      href={src}
      target="_blank"
      rel="noopener noreferrer"
      title={`Published ${slug} Fig ${panelKey} panel (opens full image)`}
      className="group relative block h-11 w-16 shrink-0 overflow-hidden rounded border border-border bg-white transition-shadow hover:ring-1 hover:ring-primary/40"
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- backend-served asset, not a static import */}
      <img
        src={src}
        alt={`Published ${slug} figure ${panelKey} panel`}
        width={64}
        height={44}
        loading="lazy"
        onError={() => setOk(false)}
        className="h-full w-full object-contain transition-transform duration-200 group-hover:scale-105"
      />
    </a>
  );
}

/** The understated "Digitize this panel" entry — opens the picker on the lifted panel.
 *  Dashed + muted so it never competes with the scored tier chips; the tooltip and the picker
 *  banner both spell out that digitized values are vision-grade and NOT part of the score. */
function DigitizeLink({
  slug,
  panelKey,
  lift,
  form,
}: {
  slug: string;
  panelKey: string;
  lift: NonNullable<Panel["lift"]>;
  form: string;
}) {
  return (
    <Link
      href={digitizeHref(slug, panelKey, lift.thumbnail_url, form)}
      title="Trace this panel's data — vision-grade, never counted in the Reproducibility Score"
      className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-border bg-transparent px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
    >
      <ScanLine className="size-3.5" aria-hidden />
      Digitize
      <span className="sr-only"> this panel (vision-grade, not part of the score)</span>
    </Link>
  );
}

function fmt(v: number | string | null): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(3);
  return v;
}
