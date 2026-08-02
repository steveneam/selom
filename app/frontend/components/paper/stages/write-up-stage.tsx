"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight, FlaskConical, NotebookPen, Sparkles, TriangleAlert } from "lucide-react";

import { useWriteUp } from "@/lib/litsynth/use-write-up";
import { REFERENCE_SLUGS, type ReferenceSlug, type WriteUpSource } from "@/lib/litsynth/source";
import { shortName, usePapers } from "@/lib/reproduction/api";
import { useReproductionRun } from "@/lib/reproduction/run";
import type { SavedPaper } from "@/lib/workspace/types";
import { cn } from "@/lib/ui/cn";
import { LegendList } from "@/components/methods/legend-list";
import { ProseBlock } from "@/components/methods/prose-block";
import { ReferenceList } from "@/components/methods/reference-list";
import { ReproducibilityStatement } from "@/components/methods/reproducibility-statement";

/**
 * The Write-up stage — the paper pipeline's terminal output (docs/paper-outputs/spec.md).
 *
 * Skill Match → Reproduce → Score answers "can this paper be reproduced". This stage answers the
 * question that follows: **what do I paste into my manuscript?** It surfaces the lit-synthesizer and
 * every paper-level output, all of which shipped working with zero FE call sites (`R-01` + `R-03`).
 *
 * ONE surface, two sources:
 *  - the user's own driven reproduction, when the paper has a surviving run, or
 *  - a **live** reference write-up from a published reproduction otherwise.
 *
 * The empty state is deliberately not a ghost skeleton (the pattern the Score stage uses). The whole
 * value here is the prose, and grey bars have none — so a user who hasn't run anything yet sees real
 * output from a paper Selom has already reproduced, labelled as an example, and learns exactly what
 * they will get.
 */
export function WriteUpStage({ paper }: { paper: SavedPaper }) {
  const runId = paper.reproductionRunId;
  const { ledger, status, error, loading: runLoading } = useReproductionRun(runId);
  const [exampleSlug, setExampleSlug] = React.useState<ReferenceSlug>("rpgrip1");

  // A run id with no ledger behind it is the normal expiry case, not a bug: runs are session-scoped
  // (the file contents are never stored). Say so, then fall back to the reference example rather
  // than leaving four empty boxes. Without a run id there is no ledger either, so the presence of
  // the ledger is the whole decision.
  const runGone = Boolean(runId) && !runLoading && !ledger;

  const source: WriteUpSource = ledger
    ? { kind: "run", ledger }
    : { kind: "reference", slug: exampleSlug };

  const wu = useWriteUp(source);
  const isReference = source.kind === "reference";

  const { data: papers } = usePapers();
  const reference = papers.find((p) => p.slug === exampleSlug);

  // Tier 1 of the reference list — the paper being written up. For your own run that's the saved
  // paper's DOI; for the example it's the published paper's.
  const doi = isReference ? reference?.doi : paper.doi;
  const searchSeed = isReference ? reference?.title : (paper.title ?? undefined);
  const scoreHref = isReference
    ? `/reproduction/${exampleSlug}`
    : `/paper/${paper.id}?stage=score`;

  return (
    <div className="space-y-8">
      {runLoading ? (
        <p className="text-sm text-muted-foreground">Reading back your reproduction…</p>
      ) : runGone ? (
        <RunGoneBanner paperId={paper.id} failed={status === "failed" || Boolean(error)} />
      ) : null}

      <header>
        <h2 className="text-lg font-semibold text-foreground">
          {isReference ? "What a write-up looks like" : "Your write-up"}
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          {isReference ? (
            <>
              Reproduce this paper and Selom writes the manuscript text for it. Until then, here is
              the <span className="text-foreground">real</span> write-up for a paper Selom has
              already reproduced — generated from its reproduction, not a sample.
            </>
          ) : (
            <>
              Paste-ready manuscript text, generated from the analyses Selom actually ran on your
              data — every method described in figure order, with the tools it used cited. Drafts:
              edit before you submit.
            </>
          )}
        </p>
      </header>

      {isReference && (
        <ExampleSwitcher
          slugs={REFERENCE_SLUGS}
          current={exampleSlug}
          onSelect={setExampleSlug}
          href={`/reproduction/${exampleSlug}`}
        />
      )}

      <ProseBlock
        id="wu-methods"
        title="Methods"
        icon={NotebookPen}
        sub={
          wu.methods?.skill_ids.length ? (
            <span className="text-[11px] text-muted-foreground/70">
              {wu.methods.skill_ids.length} method
              {wu.methods.skill_ids.length === 1 ? "" : "s"}
            </span>
          ) : undefined
        }
        text={wu.methods?.text}
        note="Draft prose — check it against what you actually ran, and edit before use."
        loading={wu.loading}
        error={wu.errors.methods}
        emptyNote="No in-scope analysis panel was reproduced for this paper, so there is no method to describe."
      />

      <LegendList
        legends={wu.legends}
        loading={wu.loading}
        error={wu.errors.legends}
        unavailable={wu.unavailable.legends}
      />

      <ReproducibilityStatement
        scorecard={wu.scorecard}
        scoreHref={scoreHref}
        loading={wu.loading}
        error={wu.errors.scorecard}
      />

      <ReferenceList
        citations={wu.methods?.citations ?? []}
        doi={doi}
        searchSeed={searchSeed}
        loading={wu.loading}
      />

      {isReference && (
        <p className="flex items-center gap-1.5 border-t border-border pt-6 text-xs text-muted-foreground">
          <Sparkles className="size-3.5 shrink-0 text-primary/70" />
          <span>
            Want this for your paper?{" "}
            <Link
              href={`/paper/${paper.id}?stage=reproduce`}
              className="text-primary hover:underline"
            >
              Attach its supplementary data and run reproduction
            </Link>
            .
          </span>
        </p>
      )}
    </div>
  );
}

/** Pick which published reproduction the example is drawn from. Three papers — pills, not a select. */
function ExampleSwitcher({
  slugs,
  current,
  onSelect,
  href,
}: {
  slugs: readonly ReferenceSlug[];
  current: ReferenceSlug;
  onSelect: (slug: ReferenceSlug) => void;
  href: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-dashed border-border bg-card/30 px-3 py-2.5">
      <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        Example from
      </span>
      {slugs.map((slug) => (
        <button
          key={slug}
          type="button"
          onClick={() => onSelect(slug)}
          aria-pressed={slug === current}
          className={cn(
            "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
            slug === current
              ? "border-primary/50 bg-primary/10 text-primary"
              : "border-border bg-muted/40 text-muted-foreground hover:border-primary/40 hover:text-foreground",
          )}
        >
          {shortName(slug)}
        </button>
      ))}
      <Link
        href={href}
        className="ml-auto inline-flex items-center gap-1 text-xs text-primary/90 hover:text-primary hover:underline"
      >
        See it graded
        <ArrowUpRight className="size-3" />
      </Link>
    </div>
  );
}

/** Runs are session-scoped — honest, calm, and points at the one action that fixes it. */
function RunGoneBanner({ paperId, failed }: { paperId: string; failed: boolean }) {
  return (
    <div className="flex flex-wrap items-start gap-2 rounded-xl border border-dashed border-amber-500/30 bg-amber-500/5 px-4 py-3">
      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">
          {failed
            ? "That reproduction run didn't finish, so there's no write-up for it yet"
            : "This reproduction run is no longer available"}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          {failed
            ? "Check the supplementary data matches the paper, then run it again."
            : "Runs are kept for the session only (the file contents aren't stored). Re-attach the data and run reproduction again."}{" "}
          The example below is a published reproduction, not your paper.
        </p>
      </div>
      <Link
        href={`/paper/${paperId}?stage=reproduce`}
        className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
      >
        <FlaskConical className="size-3.5" />
        Back to Reproduce
      </Link>
    </div>
  );
}
