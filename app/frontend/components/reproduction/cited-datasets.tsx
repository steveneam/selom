"use client";

import * as React from "react";
import { ArrowUpRight, Database, Download, FlaskConical, Lock } from "lucide-react";

import {
  ACCESS_META,
  accessionSummary,
  type AccessClass,
  type Accession,
} from "@/lib/reproduction/accessions";
import { Card } from "@/components/ui/card";

/**
 * The deposit-data handoff (Slice 5B). Famous papers deposit their data behind a repository
 * accession and attach only a QC table, so the panels that need the real matrix classify
 * `data_unmatched` (see the picker below). Rather than auto-fetch (on hold), Selom recognizes those
 * accessions off the paper text and hands the user a direct link + per-repo "which file, how"
 * instructions — they download it, attach it on the Reproduce tab, and point each panel at it with
 * the picker. Honest by construction: a raw/controlled accession says plainly it *can't* be dropped
 * in (reads need quantifying; controlled data needs an application), so the handoff never sends
 * someone chasing a file Selom can't use. Renders nothing when the paper cites no datasets.
 */
export function CitedDatasets({
  accessions,
  hasUnmatched,
}: {
  accessions: Accession[];
  hasUnmatched: boolean;
}) {
  if (accessions.length === 0) return null;
  const { total, ingestable } = accessionSummary(accessions);

  return (
    <section className="mt-10">
      <div>
        <h2 className="inline-flex items-center gap-2 text-lg font-semibold text-foreground">
          <Database className="size-4 text-muted-foreground" aria-hidden />
          Where this paper&apos;s data lives
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          {hasUnmatched ? (
            <>
              The panels above couldn&apos;t be matched to an attached file because this paper&apos;s
              data is <em>deposited</em>, not attached. Download the right file from its repository,
              add it on the Reproduce tab, then pick it for each panel above.
            </>
          ) : (
            <>
              This paper cites {total} dataset{total > 1 ? "s" : ""} (deposited, not attached as
              files). {ingestable > 0 ? `${ingestable} can be downloaded and analyzed.` : null}
            </>
          )}
        </p>
      </div>

      <div className="mt-4 space-y-3">
        {accessions.map((a) => (
          <AccessionRow key={`${a.repo}:${a.id}`} accession={a} />
        ))}
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
        Links open the repository record — Selom never downloads anything for you. Raw reads and
        controlled-access datasets can&apos;t be dropped in as-is (see each note).
      </p>
    </section>
  );
}

function AccessionRow({ accession: a }: { accession: Accession }) {
  return (
    <Card className="p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-foreground">{a.label || a.repo}</span>
        <AccessBadge access={a.access} />
        {a.section === "availability" && (
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground/70">
            data-availability
          </span>
        )}
        <a
          href={a.url}
          target="_blank"
          rel="noreferrer"
          className="ml-auto inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-1 font-mono text-xs text-foreground transition-colors hover:border-primary/50 hover:text-primary"
          title={`Open ${a.id} at ${a.label || a.repo}`}
        >
          {a.id}
          <ArrowUpRight className="size-3" />
        </a>
      </div>

      <p
        className={`mt-2 inline-flex items-start gap-1.5 text-[11px] leading-relaxed ${
          a.ingestable ? "text-muted-foreground" : "text-amber-600 dark:text-amber-400"
        }`}
      >
        <HintIcon access={a.access} ingestable={a.ingestable} />
        <span>{a.download_hint || a.note}</span>
      </p>
    </Card>
  );
}

function AccessBadge({ access }: { access: string }) {
  const meta = ACCESS_META[access as AccessClass] ?? ACCESS_META.open;
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium"
      style={{
        backgroundColor: `color-mix(in oklab, ${meta.color} 12%, transparent)`,
        borderColor: `color-mix(in oklab, ${meta.color} 38%, transparent)`,
        color: `color-mix(in oklab, ${meta.color} 82%, white)`,
      }}
      title={meta.short}
    >
      {meta.label}
    </span>
  );
}

/** Honest cue: a download arrow for fetchable data, a flask for raw (needs quantifying), a lock for
 *  controlled access — so the icon itself signals whether this is a real handoff. */
function HintIcon({ access, ingestable }: { access: string; ingestable: boolean }) {
  if (access === "controlled") return <Lock className="mt-px size-3 shrink-0" aria-hidden />;
  if (access === "raw") return <FlaskConical className="mt-px size-3 shrink-0" aria-hidden />;
  if (ingestable) return <Download className="mt-px size-3 shrink-0" aria-hidden />;
  return <Database className="mt-px size-3 shrink-0" aria-hidden />;
}
