"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { shortName, useLedger } from "@/lib/reproduction/api";
import { PaperMetaHeader } from "@/components/paper/paper-meta-header";
import { ScoreReport } from "./score-report";

/** The per-paper detail: dual-axis score, findings-first banner, heatmap, evidence table. The graded
 *  body is the shared `ScoreReport` (also rendered by the live Score stage from a driven run). */
export function PaperDetail({ slug }: { slug: string }) {
  const { data: ledger } = useLedger(slug);

  if (!ledger) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-20 text-center">
        <p className="text-sm text-muted-foreground">
          No reproduction ledger for <span className="tabular text-foreground">{slug}</span>.
        </p>
        <BackLink className="mt-4 justify-center" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10 lg:px-10">
      <BackLink />

      <PaperMetaHeader
        meta={ledger.paper}
        className="mt-4"
        eyebrow={
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary/80">
            {shortName(slug)}
          </p>
        }
        trailing={ledger.paper.geo.map((g) => (
          <span key={g} className="rounded border border-border bg-muted px-1.5 py-0.5 tabular">
            {g}
          </span>
        ))}
      />

      <ScoreReport ledger={ledger} />
    </div>
  );
}

function BackLink({ className = "" }: { className?: string }) {
  return (
    <Link
      href="/reproduction"
      className={`inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground ${className}`}
    >
      <ArrowLeft className="size-4" />
      All papers
    </Link>
  );
}
