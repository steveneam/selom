"use client";

import * as React from "react";
import { ArrowDown, ArrowUp, ChevronDown, Download, Search, Sparkles, Table2, Tag } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import type { StatsTable } from "@/lib/skills-api";

/**
 * The gene-labelling surface for a volcano's Statistics table (generalization-spec §H): a Label
 * toggle column + a gene search. Toggling writes the SAME `label_genes` set as the canvas
 * click-to-label (a `layout.annotations` entry, instant + undoable) — both share the figure store.
 * Provided only for a geneLabels figure; absent → the table renders exactly as before.
 */
export interface StatsLabeling {
  /** The column holding the gene symbol (matched to the canvas point's `customdata`). */
  geneColumn: number;
  /** Genes that currently have a label annotation (the toggle reads checked from this). */
  labeled: Set<string>;
  /** Genes with a plotted point — only these can be labelled (a row outside the plot is disabled). */
  labelable: Set<string>;
  /** Toggle one gene's label (the parent commits the annotation op to the figure store). */
  onToggle: (gene: string) => void;
}

/**
 * Statistics node (Pillar 1) — the result table a skill computed (DE / enrichment /
 * markers), shown alongside the figure. Collapsed by default; sortable by any column;
 * exportable to CSV. The DOM is capped (large tables stay responsive); the title notes
 * any truncation. Data is the figure's stored `table`, or a derived fallback (D3).
 */
const MAX_RENDER = 200;

export function StatsPanel({
  table,
  className,
  defaultOpen = false,
  labeling,
}: {
  table: StatsTable;
  className?: string;
  defaultOpen?: boolean;
  labeling?: StatsLabeling;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  const [sort, setSort] = React.useState<{ col: number; dir: 1 | -1 } | null>(null);
  const [query, setQuery] = React.useState("");

  const sorted = React.useMemo(() => {
    if (!sort) return table.rows;
    const { col, dir } = sort;
    return [...table.rows].sort((a, b) => cmp(a[col], b[col]) * dir);
  }, [table.rows, sort]);
  // Gene search (labelling only): filter to rows whose gene contains the query.
  const rows = React.useMemo(() => {
    if (!labeling || !query.trim()) return sorted;
    const q = query.trim().toLowerCase();
    return sorted.filter((r) => String(r[labeling.geneColumn] ?? "").toLowerCase().includes(q));
  }, [sorted, labeling, query]);
  const shown = rows.slice(0, MAX_RENDER);

  function toggleSort(col: number) {
    // asc → desc → unsorted
    setSort((s) => (s?.col === col ? (s.dir === 1 ? { col, dir: -1 } : null) : { col, dir: 1 }));
  }

  function exportCsv() {
    const lines = [table.columns, ...table.rows].map((r) => r.map(csvCell).join(","));
    const blob = new Blob([lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(table.title ?? "statistics").replace(/[^\w.-]+/g, "_").toLowerCase() || "statistics"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className={cn("rounded-xl border border-border bg-card/60", className)} data-testid="stats-panel">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2.5 rounded-xl px-4 py-2.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
      >
        <Table2 className="size-4 text-primary" />
        <span className="text-sm font-medium text-foreground">{table.title ?? "Statistics"}</span>
        {table.synthesized && <SynthesizedBadge />}
        <span className="hidden text-xs text-muted-foreground sm:inline">
          {table.rows.length} rows · {table.columns.length} columns
        </span>
        <ChevronDown className={cn("ml-auto size-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="border-t border-border">
          {table.synthesized && (
            <p className="flex items-start gap-1.5 border-b border-border/60 bg-primary/[0.04] px-4 py-2 text-[11px] leading-relaxed text-muted-foreground">
              <Sparkles className="mt-px size-3 shrink-0 text-primary/80" />
              <span>
                Computed by Selom from the figure — this skill doesn&apos;t emit a table, so we re-shaped
                the values it plotted (read, not re-computed) into an editable one.
              </span>
            </p>
          )}
          {labeling && (
            <div className="flex items-center gap-2 border-b border-border/60 px-4 py-2">
              <Search className="size-3.5 shrink-0 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search genes to label…"
                aria-label="Search genes"
                className="h-7 text-xs"
              />
              {labeling.labeled.size > 0 && (
                <span className="tabular shrink-0 whitespace-nowrap text-[11px] text-muted-foreground">
                  <span className="font-medium text-foreground/80">{labeling.labeled.size}</span> labelled
                </span>
              )}
            </div>
          )}
          <div className="flex items-center justify-between gap-2 px-4 py-2">
            <span className="text-[11px] text-muted-foreground">
              {shown.length < rows.length ? `Showing ${shown.length} of ${rows.length} rows` : `${rows.length} rows`}
              {labeling ? " · toggle Label to pin a gene on the figure" : " · click a header to sort"}
            </span>
            <Button variant="outline" size="sm" className="h-7 gap-1.5 px-2 text-xs" onClick={exportCsv} data-testid="stats-csv">
              <Download /> CSV
            </Button>
          </div>
          <div className="max-h-[300px] overflow-auto border-t border-border">
            <table className="w-full border-collapse text-xs">
              <thead className="sticky top-0 bg-card">
                <tr>
                  {labeling && (
                    <th className="select-none border-b border-border px-3 py-2 text-left font-semibold text-muted-foreground">
                      Label
                    </th>
                  )}
                  {table.columns.map((c, i) => (
                    <th
                      key={i}
                      onClick={() => toggleSort(i)}
                      className="cursor-pointer select-none border-b border-border px-3 py-2 text-left font-semibold text-muted-foreground hover:text-foreground"
                    >
                      <span className="inline-flex items-center gap-1">
                        {c}
                        {sort?.col === i && (sort.dir === 1 ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {shown.map((r, ri) => {
                  const gene = labeling ? String(r[labeling.geneColumn] ?? "") : "";
                  return (
                    <tr key={ri} className="hover:bg-accent/40">
                      {labeling && (
                        <td className="border-b border-border/60 px-3 py-1.5">
                          <LabelToggle
                            gene={gene}
                            on={labeling.labeled.has(gene)}
                            disabled={!labeling.labelable.has(gene)}
                            onToggle={labeling.onToggle}
                          />
                        </td>
                      )}
                      {r.map((cell, ci) => (
                        <td
                          key={ci}
                          className={cn(
                            "tabular border-b border-border/60 px-3 py-1.5",
                            typeof cell === "number" ? "text-right text-foreground/90" : "text-foreground/80",
                          )}
                        >
                          {typeof cell === "number" ? fmtNum(cell) : String(cell)}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/** One gene's Label toggle (generalization-spec §H): a Tag chip, filled when the gene is pinned on
 *  the figure. Disabled when the gene has no plotted point (nothing on the figure to anchor a label). */
function LabelToggle({
  gene,
  on,
  disabled,
  onToggle,
}: {
  gene: string;
  on: boolean;
  disabled: boolean;
  onToggle: (gene: string) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={`${on ? "Remove" : "Add"} label for ${gene || "this gene"}`}
      disabled={disabled || !gene}
      onClick={() => onToggle(gene)}
      title={
        disabled
          ? "Not plotted on this figure"
          : on
            ? `Remove the ${gene} label`
            : `Label ${gene} on the figure`
      }
      className={cn(
        "inline-flex size-6 items-center justify-center rounded-md border transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
        disabled
          ? "cursor-not-allowed border-transparent text-muted-foreground/30"
          : on
            ? "border-primary/40 bg-primary/15 text-primary hover:bg-primary/25"
            : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground",
      )}
    >
      <Tag className="size-3.5" />
    </button>
  );
}

/** Marks a Statistics table that Selom synthesized from the figure (L3) rather than the skill
 *  emitting natively — kept visually distinct from a native table (table-synthesis spec S3). */
function SynthesizedBadge() {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary"
      title="Computed by Selom from the figure — this skill emits no native table"
    >
      <Sparkles className="size-2.5" />
      Computed by Selom
    </span>
  );
}

function cmp(a: string | number, b: string | number): number {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

function csvCell(v: string | number): string {
  const s = String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function fmtNum(n: number): string {
  if (!Number.isFinite(n)) return String(n);
  if (n !== 0 && (Math.abs(n) < 1e-3 || Math.abs(n) >= 1e6)) return n.toExponential(2);
  return String(n);
}
