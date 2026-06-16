"use client";

import * as React from "react";
import { Database, LayoutGrid, Play, Plus, Sparkles, Table2, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { StaleBadge } from "./stale-badge";
import { getSkill } from "@/lib/catalog/seed";
import type { StalenessResult } from "@/lib/lineage/staleness";
import type { Dataset, Figure } from "@/lib/projects/types";

/**
 * The workrail (Pillar 1, S2.3) — replaces the project's four tabs with a sectioned
 * left navigator that IS the raw-data → output lineage. Three stage sections sit on a
 * connecting spine, top → bottom:
 *
 *   Data  →  (Run a skill)  →  Statistics  →  Figure
 *   blue       violet            green          cyan
 *
 * Each section lists its artifacts; selecting one drives the main pane. The figure is
 * the named unit (Decision D4): a figure node carries its skill, an inline staleness
 * badge, and — on select — lights its lineage (its source dataset + its stats node ring
 * up, so the chain that produced it is visible without leaving the rail). "Run a skill"
 * is an action on the spine, not a tab. Colours reuse the pipeline's --stage-* system.
 */

export type RailView = "home" | "data" | "skill" | "stats" | "figure";

/** A figure plus the derived state the rail needs to render its node. */
export interface FigureNode {
  figure: Figure;
  staleness: StalenessResult;
  hasStats: boolean;
}

/** The active figure's lineage — the dataset + stats + figure nodes to light up. */
export interface Lineage {
  datasetId?: string;
  figureId?: string;
}

export function Workrail({
  datasets,
  figureNodes,
  view,
  activeFigureId,
  lineage,
  onHome,
  onSelectData,
  onRunSkill,
  onSelectStats,
  onSelectFigure,
}: {
  datasets: Dataset[];
  figureNodes: FigureNode[];
  view: RailView;
  activeFigureId: string | null;
  lineage: Lineage;
  onHome: () => void;
  onSelectData: () => void;
  onRunSkill: () => void;
  onSelectStats: (fig: Figure) => void;
  onSelectFigure: (fig: Figure) => void;
}) {
  const statsNodes = figureNodes.filter((n) => n.hasStats);

  return (
    <nav
      aria-label="Project lineage"
      className="flex max-h-full w-64 shrink-0 flex-col gap-1 self-start overflow-y-auto rounded-2xl border border-border bg-card/40 p-3"
    >
      {/* Home / pipeline — return to the project overview. Not a stage; a meta affordance. */}
      <button
        type="button"
        onClick={onHome}
        aria-current={view === "home" ? "page" : undefined}
        className={cn(
          "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
          view === "home" ? "bg-accent/50 text-foreground" : "text-muted-foreground hover:bg-accent/30 hover:text-foreground",
        )}
      >
        <LayoutGrid className="size-4" />
        Pipeline
      </button>

      <div className="my-1 h-px bg-border" />

      {/* The lineage spine: stage dots threaded by a single vertical line. */}
      <div className="relative grid grid-cols-[18px_1fr] gap-x-2.5">
        <span aria-hidden className="absolute bottom-5 left-[8px] top-5 w-px bg-border" />

        {/* DATA */}
        <Stage color="var(--stage-data)" filled={datasets.length > 0} />
        <Section label="Data" count={datasets.length} color="var(--stage-data)">
          {datasets.length === 0 ? (
            <EmptyHint>No data yet</EmptyHint>
          ) : (
            datasets.map((d) => (
              <Row
                key={d.id}
                icon={Database}
                color="var(--stage-data)"
                title={d.filename}
                sub={d.qc ? `${d.modality} · ${d.qc.nObs.toLocaleString()} × ${d.qc.nVar.toLocaleString()}` : d.modality}
                selected={view === "data"}
                linked={lineage.datasetId === d.id}
                onClick={onSelectData}
              />
            ))
          )}
          <AddRow onClick={onSelectData} label={datasets.length === 0 ? "Add data" : "Add another dataset"} />
        </Section>

        {/* RUN A SKILL — the action in the flow, between data and its outputs. */}
        <Stage color="var(--stage-skill)" filled action />
        <div className="min-w-0 pb-4 pt-0.5">
          <button
            type="button"
            onClick={onRunSkill}
            aria-current={view === "skill" ? "page" : undefined}
            className={cn(
              "group flex w-full items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
              view === "skill"
                ? "border-[color-mix(in_oklab,var(--stage-skill)_50%,transparent)] bg-[color-mix(in_oklab,var(--stage-skill)_12%,var(--card))] text-foreground"
                : "border-dashed border-[color-mix(in_oklab,var(--stage-skill)_35%,transparent)] text-foreground hover:bg-[color-mix(in_oklab,var(--stage-skill)_8%,transparent)]",
            )}
          >
            <span
              aria-hidden
              className="grid size-6 place-items-center rounded-md [&_svg]:size-3.5"
              style={{ color: "var(--stage-skill)" }}
            >
              <Play />
            </span>
            Run a skill
          </button>
        </div>

        {/* STATISTICS — the result tables (proof). Green. */}
        <Stage color="var(--stage-publish)" filled={statsNodes.length > 0} />
        <Section label="Statistics" count={statsNodes.length} color="var(--stage-publish)">
          {statsNodes.length === 0 ? (
            <EmptyHint>Run a skill to compute a table</EmptyHint>
          ) : (
            statsNodes.map((n) => (
              <Row
                key={n.figure.id}
                icon={Table2}
                color="var(--stage-publish)"
                title={n.figure.table?.title ?? `${skillName(n.figure)} — statistics`}
                sub={n.figure.table ? `${n.figure.table.rows.length} rows · ${n.figure.table.columns.length} cols` : "derived table"}
                selected={view === "stats" && activeFigureId === n.figure.id}
                linked={lineage.figureId === n.figure.id}
                onClick={() => onSelectStats(n.figure)}
              />
            ))
          )}
        </Section>

        {/* FIGURE — the editable figures. Cyan (brand). */}
        <Stage color="var(--stage-figure)" filled={figureNodes.length > 0} last />
        <Section label="Figure" count={figureNodes.length} color="var(--stage-figure)" last>
          {figureNodes.length === 0 ? (
            <EmptyHint>No figures yet</EmptyHint>
          ) : (
            figureNodes.map((n) => (
              <Row
                key={n.figure.id}
                icon={Sparkles}
                color="var(--stage-figure)"
                title={n.figure.title}
                sub={skillName(n.figure)}
                badge={n.staleness.stale ? <StaleBadge result={n.staleness} className="px-1 py-0 text-[9px]" /> : undefined}
                selected={view === "figure" && activeFigureId === n.figure.id}
                linked={lineage.figureId === n.figure.id}
                onClick={() => onSelectFigure(n.figure)}
              />
            ))
          )}
        </Section>
      </div>
    </nav>
  );
}

function skillName(fig: Figure): string {
  return getSkill(fig.skillId ?? "")?.name ?? "figure";
}

/** A stage dot on the spine; `filled` lights it in the stage colour. */
function Stage({ color, filled, action, last }: { color: string; filled: boolean; action?: boolean; last?: boolean }) {
  return (
    <div className={cn("relative flex justify-center pt-[7px]", last ? "" : "")}>
      <span
        aria-hidden
        className={cn("relative z-10 block rounded-full ring-4 ring-card", action ? "size-2" : "size-2.5")}
        style={filled ? { backgroundColor: color } : { backgroundColor: "var(--card)", boxShadow: `inset 0 0 0 1.5px var(--border)` }}
      />
    </div>
  );
}

function Section({
  label,
  count,
  color,
  last,
  children,
}: {
  label: string;
  count: number;
  color: string;
  last?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("min-w-0", last ? "" : "pb-4")}>
      <div className="flex items-baseline gap-2 px-0.5 pb-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color }}>
          {label}
        </span>
        {count > 0 && <span className="tabular text-[11px] text-muted-foreground">{count}</span>}
      </div>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

/** One artifact row in a section. `selected` = open in main pane; `linked` = part of the
 *  active figure's lineage (softer ring). */
function Row({
  icon: Icon,
  color,
  title,
  sub,
  badge,
  selected,
  linked,
  onClick,
}: {
  icon: LucideIcon;
  color: string;
  title: string;
  sub?: string;
  badge?: React.ReactNode;
  selected?: boolean;
  linked?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "flex w-full items-center gap-2 rounded-lg border px-2 py-1.5 text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
        selected
          ? "border-transparent"
          : linked
            ? "border-transparent bg-accent/20"
            : "border-transparent hover:bg-accent/30",
      )}
      style={
        selected
          ? {
              borderColor: `color-mix(in oklab, ${color} 45%, transparent)`,
              background: `color-mix(in oklab, ${color} 12%, var(--card))`,
            }
          : linked
            ? { boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${color} 30%, transparent)` }
            : undefined
      }
    >
      <span aria-hidden className="grid size-6 shrink-0 place-items-center [&_svg]:size-3.5" style={{ color }}>
        <Icon />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-medium leading-tight text-foreground">{title}</span>
        {sub && <span className="block truncate text-[11px] leading-tight text-muted-foreground">{sub}</span>}
      </span>
      {badge}
    </button>
  );
}

function AddRow({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[12px] font-medium text-muted-foreground transition-colors hover:bg-accent/30 hover:text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
    >
      <span aria-hidden className="grid size-6 shrink-0 place-items-center [&_svg]:size-3.5">
        <Plus />
      </span>
      {label}
    </button>
  );
}

function EmptyHint({ children }: { children: React.ReactNode }) {
  return <p className="px-2 py-1 text-[11px] text-muted-foreground/80">{children}</p>;
}
