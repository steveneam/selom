"use client";

import * as React from "react";
import {
  ChevronDown,
  ChevronRight,
  Database,
  GitCompare,
  LayoutGrid,
  Lock,
  Paintbrush,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Play,
  Plus,
  SlidersHorizontal,
  Table2,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/ui/cn";
import { plural } from "@/lib/ui/plural";
import { useAutoCollapse } from "@/hooks/use-auto-collapse";
import { StaleBadge } from "./stale-badge";
import { getSkill } from "@/lib/catalog/seed";
import { datasetChipName, datasetDisplayName } from "@/lib/lineage/family";
import { groupFamilies } from "@/lib/lineage/versions";
import type { StalenessResult } from "@/lib/lineage/staleness";
import type { Dataset, Figure } from "@/lib/projects/types";
import { asTables } from "@/lib/skills/stats-tables";

/**
 * The workrail (Pillar 1) — the sectioned left navigator that IS the raw-data → output
 * lineage. Three stage sections sit on a connecting spine, top → bottom:
 *
 *   Data  →  (Run a skill)  →  Statistics  →  Figure
 *   blue       violet            green          cyan
 *
 * Each section lists its artifacts and selecting one drives the main pane. The figure is
 * the named unit (Decision D4); a figure node carries its skill, an inline staleness
 * badge, a frozen "paper" lock, and — on select — lights its lineage.
 *
 * S3 additions: sibling **versions** (sweeps / re-runs / forks) **nest under their
 * original** instead of a flat list (so a parameter sweep doesn't flood the rail); each
 * **section collapses**; the **whole rail collapses** to a spine of stage dots; and the
 * rail's border + a header chip take the **active section's colour** — a restrained
 * "this is the working context" signal (and the visual language the future Ask-Selom
 * chat will scope itself by). Colours reuse the pipeline's --stage-* system.
 */

export type RailView = "home" | "data" | "skill" | "stats" | "figuredata" | "figure" | "compare";

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

/** Per-view context: the stage colour + label shown as the rail's "working context" signal. */
const CONTEXT: Record<RailView, { color: string; label: string }> = {
  home: { color: "var(--muted-foreground)", label: "Pipeline" },
  data: { color: "var(--stage-data)", label: "Data" },
  skill: { color: "var(--stage-skill)", label: "Run a skill" },
  stats: { color: "var(--stage-publish)", label: "Statistics" },
  figuredata: { color: "var(--stage-figuredata)", label: "Figure data" },
  figure: { color: "var(--stage-figure)", label: "Figure styling" },
  compare: { color: "var(--stage-figure)", label: "Compare" },
};

export function Workrail({
  datasets,
  figureNodes,
  familyColors,
  view,
  activeFigureId,
  activeDatasetId,
  lineage,
  onHome,
  onSelectData,
  onRunSkill,
  onSelectStats,
  onFigureData,
  hasActiveFigure,
  onSelectFigure,
  onDeleteFigure,
  onRenameDataset,
  onCompareFamily,
}: {
  datasets: Dataset[];
  /** Dataset id → its stable family accent colour (Pillar 1 lineage). */
  familyColors: Map<string, string>;
  figureNodes: FigureNode[];
  view: RailView;
  activeFigureId: string | null;
  activeDatasetId: string | null;
  lineage: Lineage;
  onHome: () => void;
  /** Navigate to the Data view, focusing a dataset when one was picked. */
  onSelectData: (datasetId?: string) => void;
  onRunSkill: () => void;
  onSelectStats: (fig: Figure) => void;
  /** Open the Figure-data stage for the active figure (tune inputs + re-run). */
  onFigureData: () => void;
  /** The Figure-data stage is contextual — enabled only with a figure open. */
  hasActiveFigure: boolean;
  onSelectFigure: (fig: Figure) => void;
  onDeleteFigure: (fig: Figure) => void;
  onRenameDataset: (id: string, label: string) => void;
  /** Open the compare view for a version family (the figure ids that share a parent). */
  onCompareFamily: (figureIds: string[]) => void;
}) {
  // On the FIGURE stage the rail is navigation standing beside the subject, so at ≤1280 it yields
  // and the editor arrives with it collapsed (`W-2`, owner decision #13). Measured: collapsing it
  // buys the plotting area 204px, and the ~506px target is unreachable at 1280 without both this
  // and the inspector dock. Every other stage keeps the plain manual toggle it always had, and one
  // user toggle here ends the automatic behaviour for the session.
  const [collapsed, setCollapsed] = useAutoCollapse(view === "figure");
  // Which sections / families are collapsed (default: all expanded — predictable).
  const [closedSections, setClosedSections] = React.useState<Set<string>>(() => new Set());
  const [closedFamilies, setClosedFamilies] = React.useState<Set<string>>(() => new Set());

  const datasetById = React.useMemo(() => new Map(datasets.map((d) => [d.id, d])), [datasets]);

  // Family groups over ALL figure nodes (one root resolution shared by both sections).
  const groups = React.useMemo(() => groupFamilies(figureNodes, (n) => n.figure), [figureNodes]);
  // Statistics groups = the same families, members filtered to those that have a table.
  const statsGroups = React.useMemo(
    () => groups.map((g) => ({ ...g, items: g.items.filter((n) => n.hasStats) })).filter((g) => g.items.length > 0),
    [groups],
  );
  const statsCount = statsGroups.reduce((n, g) => n + g.items.length, 0);

  const ctx = CONTEXT[view];
  const borderColor = view === "home" ? undefined : `color-mix(in oklab, ${ctx.color} 45%, var(--border))`;

  function toggleSection(key: string) {
    setClosedSections((s) => {
      const next = new Set(s);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }
  function toggleFamily(key: string) {
    setClosedFamilies((s) => {
      const next = new Set(s);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // The source-family chip for a figure/stat node: its dataset's colour + (live) name.
  function familyOf(fig: Figure): { color: string; name: string } | undefined {
    const d = fig.datasetId ? datasetById.get(fig.datasetId) : undefined;
    if (!d) return undefined;
    return { color: familyColors.get(d.id) ?? "var(--muted-foreground)", name: datasetChipName(d) };
  }

  if (collapsed) {
    return (
      <CollapsedRail
        view={view}
        ctx={ctx}
        borderColor={borderColor}
        counts={{ data: datasets.length, stats: statsCount, figure: figureNodes.length }}
        onExpand={() => setCollapsed(false)}
        onHome={onHome}
        onData={() => onSelectData()}
        onRunSkill={onRunSkill}
      />
    );
  }

  // One figure row (top-level single, or a nested version). `nested` = a version inside
  // an expanded family (indented, labelled by its variant rather than the family title).
  function figureRow(n: FigureNode, nested: boolean) {
    return (
      <Row
        key={n.figure.id}
        icon={Paintbrush}
        color="var(--stage-figure)"
        title={nested ? versionTitle(n.figure) : n.figure.title}
        family={nested ? undefined : familyOf(n.figure)}
        sub={skillName(n.figure)}
        frozen={n.figure.frozen}
        badge={n.staleness.stale ? <StaleBadge result={n.staleness} className="px-1 py-0 text-[9px]" /> : undefined}
        selected={view === "figure" && activeFigureId === n.figure.id}
        linked={lineage.figureId === n.figure.id}
        indent={nested}
        onClick={() => onSelectFigure(n.figure)}
        onDelete={() => onDeleteFigure(n.figure)}
        deleteLabel={`Delete figure “${n.figure.title}”`}
      />
    );
  }

  function statsRow(n: FigureNode, nested: boolean) {
    return (
      <Row
        key={n.figure.id}
        icon={Table2}
        color="var(--stage-publish)"
        title={nested ? versionTitle(n.figure) : statsRowTitle(n.figure)}
        family={nested ? undefined : familyOf(n.figure)}
        sub={statsRowSub(n.figure)}
        selected={view === "stats" && activeFigureId === n.figure.id}
        linked={lineage.figureId === n.figure.id}
        indent={nested}
        onClick={() => onSelectStats(n.figure)}
      />
    );
  }

  return (
    <nav
      aria-label="Project lineage"
      style={borderColor ? { borderColor } : undefined}
      className="flex max-h-full w-64 shrink-0 flex-col gap-1 self-start overflow-y-auto rounded-2xl border border-border bg-card/40 p-3 transition-colors"
    >
      {/* Context header: the active-section signal + the rail collapse toggle. */}
      <div className="mb-0.5 flex items-center gap-2">
        <span className="inline-flex min-w-0 items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
          <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ backgroundColor: ctx.color }} />
          <span className="truncate uppercase tracking-wider" style={{ color: view === "home" ? undefined : ctx.color }}>
            {ctx.label}
          </span>
        </span>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          aria-label="Collapse rail"
          title="Collapse the rail"
          className="ml-auto grid size-6 shrink-0 place-items-center rounded text-muted-foreground/70 transition-colors hover:bg-accent hover:text-foreground [&_svg]:size-3.5"
        >
          <PanelLeftClose />
        </button>
      </div>

      {/* Home / pipeline — return to the project overview. */}
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
        <Section
          label="Data"
          count={datasets.length}
          color="var(--stage-data)"
          collapsed={closedSections.has("data")}
          onToggle={() => toggleSection("data")}
        >
          {datasets.length === 0 ? (
            <EmptyHint>No data yet</EmptyHint>
          ) : (
            datasets.map((d) => (
              <DatasetRow
                key={d.id}
                dataset={d}
                color={familyColors.get(d.id) ?? "var(--stage-data)"}
                selected={view === "data" && activeDatasetId === d.id}
                linked={lineage.datasetId === d.id}
                onSelect={() => onSelectData(d.id)}
                onRename={(label) => onRenameDataset(d.id, label)}
              />
            ))
          )}
          <AddRow onClick={() => onSelectData()} label={datasets.length === 0 ? "Add data" : "Add another dataset"} />
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
            <span aria-hidden className="grid size-6 place-items-center rounded-md [&_svg]:size-3.5" style={{ color: "var(--stage-skill)" }}>
              <Play />
            </span>
            Run a skill
          </button>
        </div>

        {/* STATISTICS — the result tables (proof). Green. */}
        <Stage color="var(--stage-publish)" filled={statsCount > 0} />
        <Section
          label="Statistics"
          count={statsCount}
          color="var(--stage-publish)"
          collapsed={closedSections.has("stats")}
          onToggle={() => toggleSection("stats")}
        >
          {statsGroups.length === 0 ? (
            <EmptyHint>Run a skill to compute a table</EmptyHint>
          ) : (
            statsGroups.map((g) =>
              g.items.length === 1 ? (
                statsRow(g.items[0], false)
              ) : (
                <FamilyBlock
                  key={`stat:${g.root.id}`}
                  title={g.root.title}
                  count={g.items.length}
                  color="var(--stage-publish)"
                  family={familyOf(g.root)}
                  open={!closedFamilies.has(`stat:${g.root.id}`)}
                  onToggle={() => toggleFamily(`stat:${g.root.id}`)}
                  onCompare={() => onCompareFamily(g.items.map((n) => n.figure.id))}
                >
                  {g.items.map((n) => statsRow(n, true))}
                </FamilyBlock>
              ),
            )
          )}
        </Section>

        {/* FIGURE DATA — the inputs behind the open figure (params re-run + data checks).
            An action node like "Run a skill", but contextual: enabled only with a figure open. */}
        <Stage color="var(--stage-figuredata)" filled action />
        <div className="min-w-0 pb-4 pt-0.5">
          <button
            type="button"
            onClick={onFigureData}
            disabled={!hasActiveFigure}
            aria-current={view === "figuredata" ? "page" : undefined}
            title={hasActiveFigure ? "Adjust the inputs behind the open figure and re-run" : "Open a figure to edit its inputs"}
            className={cn(
              "group flex w-full items-center gap-2 rounded-lg border px-2.5 py-2 text-left text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50",
              view === "figuredata"
                ? "border-[color-mix(in_oklab,var(--stage-figuredata)_50%,transparent)] bg-[color-mix(in_oklab,var(--stage-figuredata)_12%,var(--card))] text-foreground"
                : "border-dashed border-[color-mix(in_oklab,var(--stage-figuredata)_35%,transparent)] text-foreground hover:bg-[color-mix(in_oklab,var(--stage-figuredata)_8%,transparent)]",
            )}
          >
            <span aria-hidden className="grid size-6 place-items-center rounded-md [&_svg]:size-3.5" style={{ color: "var(--stage-figuredata)" }}>
              <SlidersHorizontal />
            </span>
            Figure data
          </button>
        </div>

        {/* FIGURE STYLING — the editable figures. Cyan (brand). */}
        <Stage color="var(--stage-figure)" filled={figureNodes.length > 0} last />
        <Section
          label="Figure styling"
          count={figureNodes.length}
          color="var(--stage-figure)"
          collapsed={closedSections.has("figure")}
          onToggle={() => toggleSection("figure")}
          last
        >
          {groups.length === 0 ? (
            <EmptyHint>No figures yet</EmptyHint>
          ) : (
            groups.map((g) =>
              g.items.length === 1 ? (
                figureRow(g.items[0], false)
              ) : (
                <FamilyBlock
                  key={`fig:${g.root.id}`}
                  title={g.root.title}
                  count={g.items.length}
                  color="var(--stage-figure)"
                  family={familyOf(g.root)}
                  open={!closedFamilies.has(`fig:${g.root.id}`)}
                  onToggle={() => toggleFamily(`fig:${g.root.id}`)}
                  onCompare={() => onCompareFamily(g.items.map((n) => n.figure.id))}
                >
                  {g.items.map((n) => figureRow(n, true))}
                </FamilyBlock>
              ),
            )
          )}
        </Section>
      </div>
    </nav>
  );
}

function skillName(fig: Figure): string {
  return getSkill(fig.skillId ?? "")?.name ?? "figure";
}

/** The label for a figure as a version inside its family (its variant, else "Original"). */
function versionTitle(fig: Figure): string {
  return fig.variantLabel ?? (fig.parentFigureId ? "Variant" : "Original");
}

/**
 * The Statistics rail row's title + subtitle. A figure may carry several tables
 * (docs/stats-tables/spec.md D1): the row names the first and counts the rest, so a second table
 * is announced here rather than being invisible until the Statistics view is open.
 */
function statsRowTitle(fig: Figure): string {
  return asTables(fig.table)[0]?.title ?? `${skillName(fig)} — statistics`;
}

function statsRowSub(fig: Figure): string {
  const tables = asTables(fig.table);
  const first = tables[0];
  if (!first) return "derived table";
  const shape = `${plural(first.rows.length, "row")} · ${plural(first.columns.length, "col")}`;
  return tables.length > 1 ? `${shape} · +${tables.length - 1} more` : shape;
}

/** The collapsed rail — a thin spine of stage dots; click any to re-open. */
function CollapsedRail({
  view,
  ctx,
  borderColor,
  counts,
  onExpand,
  onHome,
  onData,
  onRunSkill,
}: {
  view: RailView;
  ctx: { color: string; label: string };
  borderColor?: string;
  counts: { data: number; stats: number; figure: number };
  onExpand: () => void;
  onHome: () => void;
  onData: () => void;
  onRunSkill: () => void;
}) {
  return (
    <nav
      aria-label="Project lineage (collapsed)"
      style={borderColor ? { borderColor } : undefined}
      className="flex w-12 shrink-0 flex-col items-center gap-1 self-start rounded-2xl border border-border bg-card/40 p-2 transition-colors"
    >
      <button
        type="button"
        onClick={onExpand}
        aria-label="Expand rail"
        title="Expand the rail"
        className="grid size-8 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground [&_svg]:size-4"
      >
        <PanelLeftOpen />
      </button>
      <div className="my-0.5 h-px w-5 bg-border" />
      <CollapsedDot icon={LayoutGrid} label="Pipeline" active={view === "home"} color="var(--muted-foreground)" filled onClick={onHome} />
      <CollapsedDot icon={Database} label="Data" active={view === "data"} color="var(--stage-data)" filled={counts.data > 0} onClick={onData} />
      <CollapsedDot icon={Play} label="Run a skill" active={view === "skill"} color="var(--stage-skill)" filled onClick={onRunSkill} />
      <CollapsedDot icon={Table2} label="Statistics" active={view === "stats"} color="var(--stage-publish)" filled={counts.stats > 0} onClick={onExpand} />
      <CollapsedDot icon={SlidersHorizontal} label="Figure data" active={view === "figuredata"} color="var(--stage-figuredata)" filled={counts.figure > 0} onClick={onExpand} />
      <CollapsedDot icon={Paintbrush} label="Figure styling" active={view === "figure" || view === "compare"} color="var(--stage-figure)" filled={counts.figure > 0} onClick={onExpand} />
    </nav>
  );
}

function CollapsedDot({
  icon: Icon,
  label,
  active,
  color,
  filled,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  active: boolean;
  color: string;
  filled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-current={active ? "page" : undefined}
      title={label}
      className="grid size-8 place-items-center rounded-lg transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 [&_svg]:size-4"
      style={{
        color: filled ? color : "var(--muted-foreground)",
        background: active ? `color-mix(in oklab, ${color} 14%, transparent)` : undefined,
        boxShadow: active ? `inset 0 0 0 1px color-mix(in oklab, ${color} 45%, transparent)` : undefined,
      }}
    >
      <Icon />
    </button>
  );
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

/** A collapsible section header (chevron + label + count) with its rows. */
function Section({
  label,
  count,
  color,
  collapsed,
  onToggle,
  last,
  children,
}: {
  label: string;
  count: number;
  color: string;
  collapsed: boolean;
  onToggle: () => void;
  last?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("min-w-0", last ? "" : "pb-4")}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={!collapsed}
        className="group flex w-full items-baseline gap-1.5 rounded px-0.5 pb-1.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
      >
        <ChevronRight
          className={cn(
            "size-3 self-center text-muted-foreground/60 transition-transform",
            !collapsed && "rotate-90",
          )}
        />
        <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color }}>
          {label}
        </span>
        {count > 0 && <span className="tabular text-[11px] text-muted-foreground">{count}</span>}
      </button>
      {!collapsed && <div className="space-y-1">{children}</div>}
    </div>
  );
}

/** A version family — a collapsible group of sibling versions under their original. */
function FamilyBlock({
  title,
  count,
  color,
  family,
  open,
  onToggle,
  onCompare,
  children,
}: {
  title: string;
  count: number;
  color: string;
  family?: { color: string; name: string };
  open: boolean;
  onToggle: () => void;
  onCompare: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg">
      <div className="group/fam flex items-center rounded-lg transition-colors hover:bg-accent/20">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          {open ? (
            <ChevronDown className="size-3.5 shrink-0 text-muted-foreground/70" />
          ) : (
            <ChevronRight className="size-3.5 shrink-0 text-muted-foreground/70" />
          )}
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-medium leading-tight text-foreground">{title}</span>
            <span className="flex items-center gap-1 truncate text-[11px] leading-tight text-muted-foreground">
              {family && <FamilyChip color={family.color} name={family.name} />}
              {family && <span aria-hidden className="text-muted-foreground/40">·</span>}
              <span className="tabular">{count} versions</span>
            </span>
          </span>
        </button>
        <button
          type="button"
          onClick={onCompare}
          aria-label={`Compare ${count} versions of ${title}`}
          title="Compare versions"
          className="mr-1 grid size-6 shrink-0 place-items-center rounded text-muted-foreground/60 opacity-0 transition-opacity hover:bg-accent hover:text-foreground focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 group-hover/fam:opacity-100 [&_svg]:size-3.5"
        >
          <GitCompare />
        </button>
      </div>
      {open && (
        <div
          className="ml-[15px] space-y-1 border-l border-border/70 pl-2 pt-1"
          style={{ borderColor: `color-mix(in oklab, ${color} 25%, var(--border))` }}
        >
          {children}
        </div>
      )}
    </div>
  );
}

/** One artifact row in a section. `selected` = open in main pane; `linked` = part of the
 *  active figure's lineage (softer ring). `frozen` shows a paper-version lock; `indent`
 *  is a nested version row; `onDelete` adds a hover/focus row action. */
function Row({
  icon: Icon,
  color,
  title,
  sub,
  family,
  badge,
  frozen,
  selected,
  linked,
  indent,
  onClick,
  onDelete,
  deleteLabel,
}: {
  icon: LucideIcon;
  color: string;
  title: string;
  sub?: string;
  family?: { color: string; name: string };
  badge?: React.ReactNode;
  frozen?: boolean;
  selected?: boolean;
  linked?: boolean;
  indent?: boolean;
  onClick: () => void;
  onDelete?: () => void;
  deleteLabel?: string;
}) {
  return (
    <div
      className={cn(
        "group/row relative flex items-center rounded-lg border transition-colors",
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
      <button
        type="button"
        onClick={onClick}
        aria-current={selected ? "true" : undefined}
        className={cn(
          "flex min-w-0 flex-1 items-center gap-2 rounded-lg py-1.5 pl-2 pr-2 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
          indent && "py-1",
        )}
      >
        <span aria-hidden className="grid size-6 shrink-0 place-items-center [&_svg]:size-3.5" style={{ color }}>
          <Icon />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1">
            <span className="min-w-0 truncate text-[13px] font-medium leading-tight text-foreground">{title}</span>
            {frozen && <Lock className="size-3 shrink-0 text-stage-figure" aria-label="Frozen" />}
          </span>
          {(family || sub) && (
            <span className="flex items-center gap-1 truncate text-[11px] leading-tight text-muted-foreground">
              {family && <FamilyChip color={family.color} name={family.name} />}
              {family && sub && <span aria-hidden className="text-muted-foreground/40">·</span>}
              {sub && <span className="truncate">{sub}</span>}
            </span>
          )}
        </span>
      </button>
      {badge && <span className="shrink-0 pr-1">{badge}</span>}
      {onDelete && (
        <button
          type="button"
          onClick={onDelete}
          aria-label={deleteLabel}
          title={deleteLabel}
          className="mr-1 grid size-6 shrink-0 place-items-center rounded text-muted-foreground/50 opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 group-hover/row:opacity-100 [&_svg]:size-3.5"
        >
          <Trash2 />
        </button>
      )}
    </div>
  );
}

/** A source-dataset chip: a family-colour dot + the dataset's (live) short name. */
function FamilyChip({ color, name }: { color: string; name: string }) {
  return (
    <span className="inline-flex min-w-0 shrink items-center gap-1" title={`From ${name}`}>
      <span aria-hidden className="size-1.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      <span className="truncate text-foreground/70">{name}</span>
    </span>
  );
}

/** A dataset row in the Data section — its family-coloured icon, an inline-renameable
 *  name (the Prism "rename the family" gesture; propagates to every source chip), and
 *  select. The rename pencil is revealed on hover/focus. */
function DatasetRow({
  dataset,
  color,
  selected,
  linked,
  onSelect,
  onRename,
}: {
  dataset: Dataset;
  color: string;
  selected?: boolean;
  linked?: boolean;
  onSelect: () => void;
  onRename: (label: string) => void;
}) {
  const [editing, setEditing] = React.useState(false);
  const name = datasetDisplayName(dataset);
  // Prefer the engine's precise data-type label (e.g. "ERG / electrophysiology") over the coarse
  // modality bucket, so the rail matches the data panel rather than showing a bare "unknown".
  const typeLabel = dataset.qc?.profileLabel ?? dataset.modality;
  const sub = dataset.qc
    ? `${typeLabel} · ${dataset.qc.nObs.toLocaleString()} × ${dataset.qc.nVar.toLocaleString()}`
    : dataset.modality;

  function commit(value: string) {
    setEditing(false);
    if (value.trim() !== name) onRename(value);
  }

  return (
    <div
      className={cn(
        "group/row relative flex items-center rounded-lg border transition-colors",
        selected ? "border-transparent" : linked ? "border-transparent bg-accent/20" : "border-transparent hover:bg-accent/30",
      )}
      style={
        selected
          ? { borderColor: `color-mix(in oklab, ${color} 45%, transparent)`, background: `color-mix(in oklab, ${color} 12%, var(--card))` }
          : linked
            ? { boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${color} 30%, transparent)` }
            : undefined
      }
    >
      {editing ? (
        <div className="flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5">
          <span aria-hidden className="grid size-6 shrink-0 place-items-center [&_svg]:size-3.5" style={{ color }}>
            <Database />
          </span>
          <input
            autoFocus
            defaultValue={name}
            aria-label="Dataset name"
            onBlur={(e) => commit(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              else if (e.key === "Escape") setEditing(false);
            }}
            className="min-w-0 flex-1 rounded border border-input bg-background px-1.5 py-0.5 text-[13px] font-medium text-foreground outline-none focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={onSelect}
          aria-current={selected ? "true" : undefined}
          className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          <span aria-hidden className="grid size-6 shrink-0 place-items-center [&_svg]:size-3.5" style={{ color }}>
            <Database />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13px] font-medium leading-tight text-foreground">{name}</span>
            <span className="block truncate text-[11px] leading-tight text-muted-foreground">{sub}</span>
          </span>
        </button>
      )}
      {!editing && (
        <button
          type="button"
          onClick={() => setEditing(true)}
          aria-label={`Rename dataset “${name}”`}
          title="Rename dataset"
          className="mr-1 grid size-6 shrink-0 place-items-center rounded text-muted-foreground/50 opacity-0 transition-opacity hover:bg-accent hover:text-foreground focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 group-hover/row:opacity-100 [&_svg]:size-3.5"
        >
          <Pencil />
        </button>
      )}
    </div>
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
