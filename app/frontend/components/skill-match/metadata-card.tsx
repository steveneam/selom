"use client";

import { ExternalLink, FileText } from "lucide-react";

import { Card } from "@/components/ui/card";
import { citationLine } from "@/lib/skill-match/api";
import type { ExtractResult } from "@/lib/skill-match/types";

/** The dropped paper's bibliographic record (paper_metadata), shown up top once the PDF is read. */
export function MetadataCard({ result }: { result: ExtractResult }) {
  const m = result.metadata;
  const authors = (m?.authors ?? []).join(", ");
  const citation = citationLine(m);
  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
          <FileText className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <p className="min-w-0 flex-1 text-sm font-semibold text-foreground">
              {m?.title || result.filename}
            </p>
            {m?.is_preprint && (
              <span className="shrink-0 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Preprint
              </span>
            )}
          </div>
          {authors && <p className="mt-0.5 text-xs text-muted-foreground">{authors}</p>}
          {citation && <p className="mt-0.5 truncate text-xs text-muted-foreground">{citation}</p>}
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            <span className="tabular" title="source file">
              {result.filename}
            </span>
            {m?.doi && <IdLink label="DOI" value={m.doi} href={`https://doi.org/${m.doi}`} />}
            {m?.pmid && (
              <IdLink label="PMID" value={m.pmid} href={`https://pubmed.ncbi.nlm.nih.gov/${m.pmid}/`} />
            )}
          </div>
        </div>
      </div>
      {!m && (
        <p className="mt-3 text-[11px] text-muted-foreground">
          Bibliographic metadata couldn&apos;t be resolved (offline or no DOI found) — routing still
          works on the extracted text.
        </p>
      )}
    </Card>
  );
}

function IdLink({ label, value, href }: { label: string; value: string; href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 text-primary/80 hover:text-primary hover:underline"
    >
      <span className="text-muted-foreground">{label}</span>
      <span className="tabular">{value}</span>
      <ExternalLink className="size-3" />
    </a>
  );
}
