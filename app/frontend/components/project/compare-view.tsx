"use client";

import * as React from "react";
import { ArrowRight, GitCompare, Lock, Sparkles, X } from "lucide-react";
import { FigureCanvas } from "@/components/figure/figure-canvas";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/ui/cn";
import { plural } from "@/lib/ui/plural";
import { getSkill } from "@/lib/catalog/seed";
import { changedParams, diffParams, diffTables, pairTableDiffs, type DeltaStatus } from "@/lib/lineage/diff";
import { datasetChipName } from "@/lib/lineage/family";
import { figureTables } from "@/lib/lineage/figure-table";
import type { Dataset, Figure } from "@/lib/projects/types";

/** Diff-state colours (DESIGN.md palette): added = emerald, removed = rose, changed = amber. */
const DELTA_COLOR: Record<DeltaStatus, string | undefined> = {
  added: "#34d399",
  removed: "#f43f5e",
  changed: "#f59e0b",
  same: undefined,
};

function versionLabel(f: Figure): string {
  return f.variantLabel ?? (f.parentFigureId ? "Variant" : "Original");
}

/**
 * Compare view (Pillar 1, S3.2) — two versions of a figure side-by-side, plus a diff of
 * their parameters and their Statistics tables. Pick any two versions of the family as
 * baseline (A) and comparison (B); the figures render read-only on the white artboard
 * and the diffs are computed by the pure `lib/lineage/diff` helpers.
 */
export function CompareView({
  family,
  datasets,
  familyColors,
  onClose,
  onOpenFigure,
}: {
  family: Figure[];
  datasets: Dataset[];
  familyColors: Map<string, string>;
  onClose: () => void;
  onOpenFigure: (f: Figure) => void;
}) {
  const [aId, setAId] = React.useState(() => family[0]?.id);
  const [bId, setBId] = React.useState(() => family[family.length - 1]?.id);

  const a = family.find((f) => f.id === aId) ?? family[0];
  const b = family.find((f) => f.id === bId) ?? family[family.length - 1];

  if (!a || !b) {
    return (
      <EmptyCompare onClose={onClose} />
    );
  }

  const skill = getSkill(a.skillId ?? b.skillId ?? "");
  const dataset = a.datasetId ? datasets.find((d) => d.id === a.datasetId) : undefined;

  const paramDeltas = changedParams(diffParams(a.provenance?.params, b.provenance?.params));
  // `diffTables` is a single-table row-alignment algorithm, so the CALLER pairs by index — and it
  // pairs EVERY index, not just the first (stats-tables spec D1/D4: array order is the runner's and
  // carries meaning, so index i on one side is the same result as index i on the other).
  //
  // ⚑ This read `figureTables(a)[0]` until 2026-08-05, and the milestone review was right that it
  // was worse than an omission. The card said "The results tables are identical" — plural, a claim
  // about ALL of them — while comparing one, so two versions whose Cohen's κ differed reported
  // themselves identical as long as the matrix matched. It also falsified the approved rationale
  // for moving κ and λ out of their titles in the first place ("a one-row table sorts, exports,
  // DIFFS IN COMPARE and is readable"), and `lollipop`'s pairwise p-values — the provenance of
  // stars drawn on the canvas — silently dropped out of every version comparison.
  //
  // Stacked, one card per pair, for D2's reason: a diff behind a fold hides the same numbers as a
  // diff that was never computed.
  const tableDiffs = pairTableDiffs(figureTables(a), figureTables(b));

  return (
    <div className="flex h-full flex-col gap-4">
      {/* header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-base font-semibold tracking-tight text-foreground">
            <GitCompare className="size-4 text-stage-figure" />
            Compare versions
          </h2>
          <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-muted-foreground">
            {skill?.name ?? "skill"}
            {dataset && (
              <>
                <span aria-hidden className="text-muted-foreground/40">·</span>
                <span className="inline-flex items-center gap-1">
                  <span
                    aria-hidden
                    className="size-1.5 rounded-full"
                    style={{ backgroundColor: familyColors.get(dataset.id) ?? "var(--stage-data)" }}
                  />
                  {datasetChipName(dataset)}
                </span>
              </>
            )}
            <span aria-hidden className="text-muted-foreground/40">·</span>
            <span className="tabular">{family.length} versions</span>
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          <X /> Close
        </Button>
      </div>

      {/* version pickers */}
      <div className="grid gap-2 sm:grid-cols-2">
        <VersionPicker label="Baseline (A)" tone="a" versions={family} selectedId={a.id} onSelect={setAId} />
        <VersionPicker label="Compare to (B)" tone="b" versions={family} selectedId={b.id} onSelect={setBId} />
      </div>

      {/* side-by-side figures + diffs */}
      <div className="grid min-h-0 flex-1 gap-4 overflow-y-auto pb-1 lg:grid-cols-2">
        <FigurePane figure={a} tone="a" onOpen={() => onOpenFigure(a)} />
        <FigurePane figure={b} tone="b" onOpen={() => onOpenFigure(b)} />
      </div>

      {/* diff */}
      <div className="grid gap-4 lg:grid-cols-2">
        <DiffCard title="Parameters">
          {paramDeltas.length === 0 ? (
            <p className="px-3 py-3 text-xs text-muted-foreground">No parameter changes between these versions.</p>
          ) : (
            <ul className="divide-y divide-border/60">
              {paramDeltas.map((d) => (
                <li key={d.key} className="flex items-center gap-2 px-3 py-2 text-xs">
                  <span className="min-w-0 flex-1 truncate font-medium text-foreground">{d.key}</span>
                  <span className="tabular text-muted-foreground line-through decoration-muted-foreground/40">
                    {d.a === undefined ? "—" : String(d.a)}
                  </span>
                  <ArrowRight className="size-3 shrink-0 text-muted-foreground/60" />
                  <span className="tabular font-medium" style={{ color: DELTA_COLOR[d.status] }}>
                    {d.b === undefined ? "—" : String(d.b)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </DiffCard>

        {tableDiffs.length === 0 ? (
          <DiffCard title="Results table">
            <p className="px-3 py-3 text-xs text-muted-foreground">Neither version has a Statistics table.</p>
          </DiffCard>
        ) : (
          tableDiffs.map(({ index, title, diff }) => (
            <TableDiffCard key={index} title={title} diff={diff} />
          ))
        )}
      </div>
    </div>
  );
}

/**
 * One table's row-level diff. Titled by the table's OWN title (the same thing that labels its
 * panel in the Statistics view), so a stack of them is readable — "Ranked values" above
 * "Pairwise p-values" rather than two cards both called "Results table".
 */
function TableDiffCard({ title, diff }: { title: string; diff: NonNullable<ReturnType<typeof diffTables>> }) {
  const changedRows = diff.rows.filter((r) => r.status !== "same");
  return (
    <DiffCard
      title={title}
      summary={<DiffSummary added={diff.added} removed={diff.removed} changed={diff.changed} />}
    >
      {changedRows.length === 0 ? (
        // Singular, and scoped to THIS table. The old copy said "The results tables are identical"
        // while only the first had been compared — a plural claim backed by a single comparison.
        <p className="px-3 py-3 text-xs text-muted-foreground">This table is identical in both versions.</p>
      ) : (
        <div className="max-h-[260px] overflow-auto">
          <table className="w-full border-collapse text-xs">
            <thead className="sticky top-0 bg-card">
              <tr>
                {diff.columns.map((c) => (
                  <th key={c} className="border-b border-border px-3 py-1.5 text-left font-semibold text-muted-foreground">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {changedRows.slice(0, 60).map((row) => (
                <tr key={row.key} className="align-top">
                  {row.cells.map((cell, ci) => (
                    <td
                      key={ci}
                      className="tabular border-b border-border/50 px-3 py-1.5"
                      style={
                        cell.status !== "same"
                          ? { color: DELTA_COLOR[cell.status], background: `color-mix(in oklab, ${DELTA_COLOR[cell.status]} 8%, transparent)` }
                          : undefined
                      }
                    >
                      {renderCell(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {changedRows.length > 60 && (
            <p className="px-3 py-2 text-[11px] text-muted-foreground">
              Showing the first 60 of {plural(changedRows.length, "changed row")}.
            </p>
          )}
        </div>
      )}
    </DiffCard>
  );
}

function renderCell(cell: { a?: string | number; b?: string | number; status: DeltaStatus }): React.ReactNode {
  if (cell.status === "removed") return <span className="line-through opacity-80">{fmt(cell.a)}</span>;
  if (cell.status === "added") return fmt(cell.b);
  if (cell.status === "changed") {
    return (
      <span className="inline-flex items-center gap-1">
        <span className="opacity-60 line-through">{fmt(cell.a)}</span>
        <ArrowRight className="size-2.5" />
        <span>{fmt(cell.b)}</span>
      </span>
    );
  }
  return <span className="text-foreground/80">{fmt(cell.b)}</span>;
}

function fmt(v: string | number | undefined): string {
  if (v === undefined) return "—";
  if (typeof v === "number" && Number.isFinite(v) && v !== 0 && (Math.abs(v) < 1e-3 || Math.abs(v) >= 1e6)) {
    return v.toExponential(2);
  }
  return String(v);
}

/** A read-only figure on the light artboard (the Light-Artboard Rule), with its label. */
function FigurePane({ figure, tone, onOpen }: { figure: Figure; tone: "a" | "b"; onOpen: () => void }) {
  return (
    <div className="flex min-h-[300px] flex-col overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <span
          className={cn(
            "grid size-5 place-items-center rounded-md text-[10px] font-bold",
            tone === "b" ? "bg-stage-figure/15 text-stage-figure" : "bg-secondary text-secondary-foreground",
          )}
        >
          {tone.toUpperCase()}
        </span>
        <span className="min-w-0 flex-1 truncate text-xs font-medium text-foreground">{versionLabel(figure)}</span>
        {figure.frozen && <Lock className="size-3 shrink-0 text-stage-figure" aria-label="Frozen" />}
        <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={onOpen}>
          <Sparkles /> Open
        </Button>
      </div>
      <div className="min-h-0 flex-1 p-2.5">
        {figure.spec ? (
          <div className="h-full min-h-[240px] overflow-hidden rounded-lg bg-artboard p-2">
            <FigureCanvas spec={figure.spec} displayModeBar={false} />
          </div>
        ) : (
          <div className="grid h-full min-h-[240px] place-items-center rounded-lg border border-dashed border-border text-center">
            <p className="max-w-[14rem] text-[11px] text-muted-foreground">
              This version was made before figures were stored durably, so its spec isn’t available to preview.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function VersionPicker({
  label,
  tone,
  versions,
  selectedId,
  onSelect,
}: {
  label: string;
  tone: "a" | "b";
  versions: Figure[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="rounded-lg border border-border bg-card/40 p-2">
      <p className="px-1 pb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {versions.map((v) => {
          const selected = v.id === selectedId;
          return (
            <button
              key={v.id}
              type="button"
              onClick={() => onSelect(v.id)}
              aria-pressed={selected}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
                selected
                  ? tone === "b"
                    ? "border-stage-figure/50 bg-stage-figure/15 text-stage-figure"
                    : "border-border bg-secondary text-secondary-foreground"
                  : "border-border text-muted-foreground hover:bg-accent/40 hover:text-foreground",
              )}
            >
              {v.frozen && <Lock className="size-2.5" />}
              {versionLabel(v)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function DiffCard({ title, summary, children }: { title: string; summary?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card/40">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <span className="text-xs font-semibold text-foreground">{title}</span>
        {summary}
      </div>
      {children}
    </div>
  );
}

function DiffSummary({ added, removed, changed }: { added: number; removed: number; changed: number }) {
  if (added + removed + changed === 0) return <span className="text-[11px] text-muted-foreground">no changes</span>;
  return (
    <span className="flex items-center gap-2 text-[11px]">
      {added > 0 && <span style={{ color: DELTA_COLOR.added }}>+{added} new</span>}
      {removed > 0 && <span style={{ color: DELTA_COLOR.removed }}>−{removed} dropped</span>}
      {changed > 0 && <span style={{ color: DELTA_COLOR.changed }}>~{changed} changed</span>}
    </span>
  );
}

function EmptyCompare({ onClose }: { onClose: () => void }) {
  return (
    <div className="grid h-full place-items-center text-center">
      <div className="space-y-2">
        <p className="text-sm font-medium text-foreground">Nothing to compare</p>
        <p className="text-xs text-muted-foreground">This figure has no other versions yet. Run a sweep or re-run to make one.</p>
        <Button variant="outline" size="sm" onClick={onClose}>Back</Button>
      </div>
    </div>
  );
}
