"use client";

import * as React from "react";
import { cn } from "@/lib/ui/cn";
import { PaneShell } from "@/components/ui/pane-shell";
import { Badge } from "@/components/ui/badge";
import type { PaneState } from "@/lib/ui/pane-state";
import { fetchGaps } from "@/lib/ai/api";
import type { GapBacklogEntry } from "@/lib/ai/types";

/**
 * The capability-gap backlog view (S5, build piece d) — the AI panel's Gaps tab.
 *
 * Reads `GET /ai/gaps`: the ranked, categorized backlog of coherent-but-unfulfillable AI actions
 * (the self-improving loop's signal). READ-ONLY — this surface never mutates the action registry,
 * relaxes a validator, or widens a param_spec (the integrity boundary). Grouped by `category`
 * (e.g. `engine_capability_missing` → the P1 engine backlog) and ranked by frequency. Works
 * regardless of the gateway state; an empty backlog renders a clean empty state.
 */
export function CapabilityGapView() {
  const [entries, setEntries] = React.useState<GapBacklogEntry[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [nonce, setNonce] = React.useState(0);

  // Reset to the loading state then refetch — driven from the Retry handler (an event, not the
  // effect body), so the effect never calls setState synchronously (avoids cascading renders).
  const reload = React.useCallback(() => {
    setEntries(null);
    setError(null);
    setNonce((n) => n + 1);
  }, []);

  React.useEffect(() => {
    let live = true;
    fetchGaps()
      .then((g) => live && setEntries(g))
      .catch((e) => live && setError(e instanceof Error ? e.message : "Couldn't load the backlog."));
    return () => {
      live = false;
    };
  }, [nonce]);

  const state: PaneState<GapBacklogEntry[]> = error
    ? { status: "error", message: error, retry: reload }
    : entries == null
      ? { status: "loading", label: "Loading the capability backlog…" }
      : entries.length === 0
        ? {
            status: "empty",
            message: "No capability gaps logged. When the AI proposes something the engine can't yet do, it's recorded here — ranked — so the most-wanted capability is built first.",
          }
        : { status: "ready", data: entries };

  return (
    <PaneShell state={state} bare>
      <GapGroups entries={entries ?? []} />
    </PaneShell>
  );
}

function GapGroups({ entries }: { entries: GapBacklogEntry[] }) {
  // Group by category, each group ranked by frequency (count desc); groups ordered by total demand.
  const groups = React.useMemo(() => {
    const byCat = new Map<string, GapBacklogEntry[]>();
    for (const e of entries) {
      const list = byCat.get(e.category) ?? [];
      list.push(e);
      byCat.set(e.category, list);
    }
    return [...byCat.entries()]
      .map(([category, list]) => ({
        category,
        list: [...list].sort((a, b) => b.count - a.count),
        total: list.reduce((s, e) => s + e.count, 0),
      }))
      .sort((a, b) => b.total - a.total);
  }, [entries]);

  return (
    <div className="space-y-4">
      {groups.map((g) => (
        <section key={g.category}>
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <h4 className="text-[11px] font-semibold uppercase tracking-wider text-foreground">
              {humanize(g.category)}
            </h4>
            <Badge variant="outline" className="tabular-nums">
              {g.total} ask{g.total === 1 ? "" : "s"}
            </Badge>
          </div>
          <ul className="space-y-1.5">
            {g.list.map((e) => (
              <li
                key={e.context_hash}
                className="rounded-lg border border-border/70 bg-card/40 px-2.5 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-foreground">{humanize(e.unmet)}</span>
                  <span
                    className={cn(
                      "shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-semibold tabular-nums",
                      "bg-muted text-muted-foreground",
                    )}
                    title={`Requested ${e.count} time${e.count === 1 ? "" : "s"}`}
                  >
                    ×{e.count}
                  </span>
                </div>
                <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
                  <span>stage: {e.stage}</span>
                  {e.skill_id && <span className="font-mono">{e.skill_id}</span>}
                </p>
                {hasSample(e.sample_attempt) && (
                  <p className="mt-1 truncate font-mono text-[10px] text-muted-foreground/80" title={JSON.stringify(e.sample_attempt)}>
                    {JSON.stringify(e.sample_attempt)}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function hasSample(s: Record<string, unknown> | undefined): boolean {
  return !!s && Object.keys(s).length > 0;
}

/** "engine_capability_missing" → "Engine capability missing". */
function humanize(code: string): string {
  const s = code.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}
