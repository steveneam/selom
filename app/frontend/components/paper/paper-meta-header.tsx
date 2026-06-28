"use client";

import * as React from "react";
import { ArrowUpRight } from "lucide-react";

import { headerCitation, type PaperMeta } from "@/lib/paper/metadata";
import { cn } from "@/lib/ui/cn";

/**
 * The ONE paper-metadata header, used identically across every surface that shows a paper at the top
 * — Skill Match, the per-paper Reproduction workspace, and the showcase detail (workspace-library
 * spec §10; the same "one shared framework" discipline as the metadata data layer). Owner-specified
 * canonical layout:
 *
 *   line 1  title
 *   line 2  all authors
 *   line 3  Year · Journal · Volume(Issue) · Pages
 *   line 4  PDF name · PMID · DOI   (+ any `trailing` chips, e.g. GEO on the detail)
 *
 * Missing parts are skipped. An optional `eyebrow` sits above the title (surface context like
 * "Reproduction · carried from Skill Match" or the paper short-code); `trailing` appends to line 4.
 */
export function PaperMetaHeader({
  meta,
  filename,
  eyebrow,
  trailing,
  className,
}: {
  meta: PaperMeta | null | undefined;
  filename?: string | null;
  eyebrow?: React.ReactNode;
  trailing?: React.ReactNode;
  className?: string;
}) {
  const m = meta ?? {};
  const title = m.title || filename || "Untitled paper";
  const authors = (m.authors ?? []).filter(Boolean).join(", ");
  const citation = headerCitation(m);
  const hasLine4 = Boolean(filename || m.pmid || m.doi || m.isPreprint || trailing);

  return (
    <header className={className}>
      {eyebrow}
      <h1 className="mt-2 max-w-3xl text-balance text-2xl font-semibold leading-tight text-foreground">
        {title}
      </h1>
      {authors && <p className="mt-1.5 max-w-3xl text-sm text-muted-foreground">{authors}</p>}
      {citation && <p className="mt-1 text-sm text-muted-foreground">{citation}</p>}
      {hasLine4 && (
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {filename && (
            <span className="tabular truncate" title={filename}>
              {filename}
            </span>
          )}
          {m.pmid && (
            <IdLink
              label="PMID"
              value={m.pmid}
              href={`https://pubmed.ncbi.nlm.nih.gov/${m.pmid}/`}
            />
          )}
          {m.doi && <IdLink label="DOI" value={m.doi} href={`https://doi.org/${m.doi}`} />}
          {m.isPreprint && (
            <span className="rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 font-medium text-amber-600 dark:text-amber-400">
              preprint
            </span>
          )}
          {trailing}
        </div>
      )}
    </header>
  );
}

function IdLink({ label, value, href }: { label: string; value: string; href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        "tabular inline-flex items-center gap-1 underline-offset-2 hover:text-foreground hover:underline",
      )}
    >
      <span className="text-muted-foreground">{label}</span>
      {value}
      <ArrowUpRight className="size-3" />
    </a>
  );
}
