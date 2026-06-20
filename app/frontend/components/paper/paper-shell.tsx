"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, FlaskConical } from "lucide-react";

import { useWorkspace, wselect } from "@/lib/workspace/store";
import { usePaperRun } from "@/lib/reproduction/run";
import {
  PaperPipeline,
  type PipelineForward,
  type PipelineStage,
} from "@/components/paper/pipeline";
import { PaperMetaHeader } from "@/components/paper/paper-meta-header";
import { SkillMatchStage } from "@/components/paper/stages/skill-match-stage";
import { ReproduceStage } from "@/components/paper/stages/reproduce-stage";
import { ScoreStage } from "@/components/paper/stages/score-stage";

/**
 * The umbrella Paper shell — one workspace over a single saved Paper, with the three pipeline stages
 * (Skill Match → Reproduce → Score) as URL-driven tabs (`?stage=`). The chrome above the divider
 * (Library back-link → pipeline → metadata header) is persistent and identical on every stage; only
 * the stage body swaps. This collapses the former per-paper surfaces (`/skill-match/[id]` +
 * `/reproduction/paper/[id]`) into one route (workspace-library spec §10 + umbrella-shell.md).
 */
const STAGE_KEYS: readonly PipelineStage[] = ["skill-match", "reproduce", "score"];

const EYEBROW: Record<PipelineStage, string> = {
  "skill-match": "Skill Match · saved",
  reproduce: "Reproduction · carried from Skill Match",
  score: "Reproducibility score",
};

export function PaperShell({ id }: { id: string }) {
  const ws = useWorkspace();
  const params = useSearchParams();
  const router = useRouter();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- flip once after hydration (SSR-safe gate)
    setMounted(true);
  }, []);

  // The live-reproduction run controller (one instance for the shell → shared by the forward button
  // and the Reproduce stage). Keyed by the route id, so it's valid before the paper resolves.
  const run = usePaperRun(id);

  const raw = params.get("stage");
  const stage: PipelineStage = STAGE_KEYS.includes(raw as PipelineStage)
    ? (raw as PipelineStage)
    : "skill-match";

  // The workspace store is client-only (localStorage); reading `?stage` via useSearchParams shifts
  // hydration timing such that the first client render can already see the hydrated store while the
  // server saw it empty. Render nothing until mounted so the server and first client render agree —
  // otherwise React reports a hydration mismatch.
  if (!mounted) return null;

  const paper = wselect.paper(ws, id);

  if (!paper) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-20 text-center">
        <p className="text-sm text-muted-foreground">This paper isn&apos;t in your Library.</p>
        <p className="mt-1.5 text-xs text-muted-foreground">
          Match a paper in{" "}
          <Link href="/skill-match" className="text-primary hover:underline">
            Skill Match
          </Link>{" "}
          first, or pick one from your{" "}
          <Link href="/library" className="text-primary hover:underline">
            Library
          </Link>
          .
        </p>
      </div>
    );
  }

  const links: Partial<Record<PipelineStage, string>> = {
    "skill-match": `/paper/${paper.id}?stage=skill-match`,
    reproduce: `/paper/${paper.id}?stage=reproduce`,
    score: `/paper/${paper.id}?stage=score`,
  };

  // The prominent top-right action mirrors the pipeline's forward step on every stage so the next move
  // is always obvious in the same place: on Skill Match it carries the paper to Reproduce; on Reproduce
  // it's the run trigger (staged until the live drive lands — a later backend contract).
  const forward: PipelineForward | undefined =
    stage === "skill-match"
      ? {
          label: "Reproduce",
          icon: FlaskConical,
          onClick: () => router.push(links.reproduce!),
          title: "Move to the Reproduce stage to add supplementary data",
        }
      : stage === "reproduce"
        ? {
            label: run.phase === "running" ? "Running…" : "Run reproduction",
            icon: FlaskConical,
            disabled: !run.canRun,
            onClick: run.start,
            title:
              run.phase === "running"
                ? "Reproduction is running…"
                : run.canRun
                  ? "Run the matched skills on your data and grade every figure"
                  : "Attach the paper PDF and at least one Excel/CSV supplement to run reproduction",
          }
        : undefined;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10 lg:px-10">
      <Link
        href="/library"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Library
      </Link>

      {/* The shared workflow pipeline doubles as the stage nav — each pill links to its `?stage`. On
          the Skill Match stage, "Reproduce →" is the prominent forward step (switches to that stage). */}
      <PaperPipeline current={stage} className="mt-4" links={links} forward={forward} />

      <PaperMetaHeader
        meta={paper}
        filename={paper.filename}
        className="mt-6"
        eyebrow={
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary/80">
            {EYEBROW[stage]}
          </p>
        }
      />

      <div className="mt-8">
        {stage === "skill-match" && <SkillMatchStage paper={paper} />}
        {stage === "reproduce" && <ReproduceStage paper={paper} run={run} />}
        {stage === "score" && <ScoreStage paper={paper} />}
      </div>
    </div>
  );
}
