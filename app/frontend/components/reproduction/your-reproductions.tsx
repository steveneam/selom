"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight, FileStack, Hourglass } from "lucide-react";

import { authorSummary, citationLine } from "@/lib/skill-match/api";
import { useWorkspace } from "@/lib/workspace/store";
import type { SavedPaper } from "@/lib/workspace/types";

/**
 * "Your papers" — an ADDITIVE strip on the Reproduction index for papers the user matched in Skill
 * Match (saved to the Workspace Library). Renders nothing when there are none, so the default index
 * is byte-identical to the showcase spectrum the owner likes; when present, it sits BELOW the dogfood
 * spectrum and links each paper into its per-paper Reproduction workspace (umbrella stage 2).
 */
export function YourReproductions() {
  const ws = useWorkspace();
  const papers = ws.papers;
  if (papers.length === 0) return null;

  return (
    <section className="mt-14">
      <div className="flex items-baseline justify-between gap-4 border-t border-border pt-8">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Your papers</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Papers you matched in Skill Match. Open one to add its supplementary data and reproduce its
            figures — they&apos;ll be graded here, just like the examples above.
          </p>
        </div>
        <Link
          href="/skill-match"
          className="shrink-0 text-xs text-primary/90 hover:text-primary hover:underline"
        >
          Match another →
        </Link>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {papers.map((p) => (
          <YourPaperCard key={p.id} paper={p} />
        ))}
      </div>
    </section>
  );
}

function YourPaperCard({ paper }: { paper: SavedPaper }) {
  const authors = authorSummary(paper.authors);
  const cite = citationLine(paper);
  const nSupp = (paper.supplements ?? []).length;

  return (
    <Link
      href={`/paper/${paper.id}?stage=reproduce`}
      className="group flex flex-col rounded-xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-ring/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="line-clamp-2 text-sm font-medium leading-snug text-foreground/90">
          {paper.title || paper.filename}
        </h3>
        <ArrowUpRight className="size-4 shrink-0 text-muted-foreground/60 transition-colors group-hover:text-foreground" />
      </div>
      {(authors || cite) && (
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {[authors, cite].filter(Boolean).join(" · ")}
        </p>
      )}

      <div className="mt-auto pt-4">
        <p className="tabular text-[11px] text-muted-foreground">
          <span className="font-medium text-foreground/80">{paper.skills.length}</span> skill
          {paper.skills.length === 1 ? "" : "s"} ·{" "}
          <span className="font-medium text-foreground/80">{paper.figureCount}</span> figure
          {paper.figureCount === 1 ? "" : "s"}
        </p>
        <div className="mt-2 flex items-center gap-2">
          {nSupp > 0 ? (
            <span className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
              <FileStack className="size-3" />
              {nSupp} supplement{nSupp > 1 ? "s" : ""}
            </span>
          ) : null}
          <span className="inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            <Hourglass className="size-3" />
            Awaiting reproduction
          </span>
        </div>
      </div>
    </Link>
  );
}
