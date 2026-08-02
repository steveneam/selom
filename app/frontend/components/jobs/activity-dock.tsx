"use client";

import * as React from "react";
import { AlertCircle, CheckCircle2, ChevronDown, Loader2, X } from "lucide-react";

import {
  clearFinishedActivities,
  dismissActivity,
  getActivities,
  getActivitiesServerSnapshot,
  subscribeActivities,
  type Activity,
} from "@/lib/jobs/activity";

/**
 * The run-activity dock — the one place a long run reports that it is happening, and that it
 * finished. Mounted once in the app shell (beside <UndoToast/>) so it survives the navigation a
 * finished run triggers: a reproduction pushes you to the Score stage, a skill run swaps the
 * workspace view, and inline progress at the launch point would be unmounted mid-flight.
 *
 * SHAPE — decided against precedents, not copied from one (docs/jobs-surface/spec.md §2):
 *
 *  * A **collapsed pill by default**, expanding to a list — FLORA's pattern. Selom's normal case
 *    is exactly one run at a time (the run engine holds a single `running` skill and disables the
 *    launch controls), so one line of text is the complete story; a permanently-expanded card
 *    would be a mostly-empty panel parked on top of a figure canvas.
 *  * **Elapsed time, counting up. Never a percentage or an ETA.** The job wire shape
 *    (`Job.public()`) carries no progress fraction and no estimate, and the runner cannot predict
 *    how long a UMAP on 60k cells takes. A countdown here would be fabricated data.
 *  * A finished run **stays visible**. Successes auto-clear after a few seconds (the figure
 *    itself is the real confirmation); **failures never auto-clear**, because an error the user
 *    did not see is an error that did not get reported.
 */

/** How long a SUCCEEDED entry lingers before it clears itself. Failures never auto-clear. */
const AUTO_DISMISS_MS = 6000;

function isActive(a: Activity): boolean {
  return a.status === "queued" || a.status === "running";
}

/** `m:ss` — an honest count-up, the only duration signal this contract can support. */
export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

/** The one-line summary the collapsed pill shows. */
export function summarize(entries: readonly Activity[]): string {
  const active = entries.filter(isActive);
  if (active.length === 1) return `Running ${active[0].label}`;
  if (active.length > 1) return `${active.length} runs in progress`;
  const failed = entries.filter((a) => a.status === "failed").length;
  if (failed === 1) return "A run failed";
  if (failed > 1) return `${failed} runs failed`;
  return entries.length === 1 ? `${entries[0].label} finished` : "Runs finished";
}

export function ActivityDock() {
  const entries = React.useSyncExternalStore(
    subscribeActivities,
    getActivities,
    getActivitiesServerSnapshot,
  );
  const [expanded, setExpanded] = React.useState(false);
  const [now, setNow] = React.useState(() => Date.now());

  const active = entries.filter(isActive);
  const hasActive = active.length > 0;

  // Tick the elapsed clock only while something is actually running.
  React.useEffect(() => {
    if (!hasActive) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [hasActive]);

  // Clear finished successes on a timer — but never while the list is open (the user is reading
  // it) and never for a failure, whose message is the only record of what went wrong.
  const doneIds = entries
    .filter((a) => a.status === "succeeded")
    .map((a) => a.id)
    .join(",");
  React.useEffect(() => {
    if (expanded || !doneIds) return;
    const ids = doneIds.split(",");
    const id = setTimeout(() => ids.forEach((entryId) => dismissActivity(entryId)), AUTO_DISMISS_MS);
    return () => clearTimeout(id);
  }, [doneIds, expanded]);

  if (entries.length === 0) return null;

  const summary = summarize(entries);
  const elapsed = hasActive ? formatElapsed(now - Math.min(...active.map((a) => a.startedAt))) : "";

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 max-w-[calc(100vw-3rem)] ${
        expanded ? "w-[22rem]" : "w-auto"
      }`}
    >
      {/* The announcement carries the SUMMARY only — never the elapsed clock, which changes every
          second and would make a screen reader unusable. */}
      <p role="status" aria-live="polite" className="sr-only">
        {summary}
      </p>
      <div className="overflow-hidden rounded-xl border border-border bg-card/95 shadow-lg shadow-black/30 backdrop-blur-sm">
        <div className="flex items-center gap-2 px-3 py-2">
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            aria-expanded={expanded}
            aria-controls="activity-dock-list"
            className="flex min-w-0 flex-1 items-center gap-2 rounded-md text-left text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            <StatusIcon entries={entries} />
            <span className="min-w-0 flex-1 truncate">{summary}</span>
            {elapsed && (
              <span className="tabular shrink-0 text-xs text-muted-foreground">{elapsed}</span>
            )}
            <ChevronDown
              aria-hidden
              className={`size-4 shrink-0 text-muted-foreground transition-transform ${
                expanded ? "" : "rotate-180"
              }`}
            />
          </button>
        </div>

        {expanded && (
          <div id="activity-dock-list" className="border-t border-border">
            <ul className="max-h-72 overflow-y-auto">
              {entries.map((entry) => (
                <ActivityRow key={entry.id} entry={entry} now={now} />
              ))}
            </ul>
            {entries.some((a) => !isActive(a)) && (
              <div className="flex justify-end border-t border-border px-3 py-1.5">
                <button
                  type="button"
                  onClick={clearFinishedActivities}
                  className="rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                >
                  Clear finished
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusIcon({ entries }: { entries: readonly Activity[] }) {
  if (entries.some(isActive)) {
    return (
      <Loader2
        aria-hidden
        className="size-4 shrink-0 animate-spin text-muted-foreground motion-reduce:animate-none"
      />
    );
  }
  if (entries.some((a) => a.status === "failed")) {
    return <AlertCircle aria-hidden className="size-4 shrink-0 text-destructive" />;
  }
  return <CheckCircle2 aria-hidden className="size-4 shrink-0 text-emerald-500" />;
}

function ActivityRow({ entry, now }: { entry: Activity; now: number }) {
  // A live run counts up; a finished one reports what it actually took.
  const took = formatElapsed((entry.endedAt ?? now) - entry.startedAt);
  // The second line, in priority order: the failure, the server's own progress line, then the
  // input it is running on. Nothing here is synthesized.
  const detail = entry.error ?? entry.detail ?? "";

  return (
    <li className="flex items-start gap-2.5 border-b border-border/60 px-3 py-2 last:border-b-0">
      <span className="pt-0.5">
        <StatusIcon entries={[entry]} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-2">
          <span className="min-w-0 flex-1 truncate text-sm text-foreground">{entry.label}</span>
          <span className="tabular shrink-0 text-xs text-muted-foreground">{took}</span>
        </span>
        {(detail || entry.context) && (
          <span
            className={`mt-0.5 block truncate text-xs ${
              entry.error ? "text-destructive" : "text-muted-foreground"
            }`}
            title={detail || entry.context}
          >
            {detail || entry.context}
          </span>
        )}
        {entry.background && !entry.error && (
          <span className="mt-0.5 block text-xs text-muted-foreground">
            Running in the background — you can keep working.
          </span>
        )}
      </span>
      {!isActive(entry) && (
        <button
          type="button"
          onClick={() => dismissActivity(entry.id)}
          aria-label={`Dismiss ${entry.label}`}
          className="grid size-6 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 [&_svg]:size-3.5"
        >
          <X />
        </button>
      )}
    </li>
  );
}
