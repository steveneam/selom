"use client";

import * as React from "react";
import { ArrowUpRight, BookText, Loader2, Search } from "lucide-react";

import {
  citationByDoi,
  formatCitation,
  referenceBlock,
  searchCitations,
  type Citation,
} from "@/lib/litsynth/api";
import { cn } from "@/lib/ui/cn";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CopyButton } from "./copy-button";
import { ProseBlock } from "./prose-block";

/**
 * The write-up's reference list (docs/paper-outputs/spec.md §2).
 *
 * Three tiers, in the order a manuscript needs them:
 *  1. **The paper itself** — resolved from its DOI (`GET /citations/by-doi`), because a Methods
 *     section that reproduces a paper has to cite it.
 *  2. **The tool citations** the Methods section already carries, deduped by the synthesizer.
 *  3. **Related literature** — an optional topical PubMed search (`GET /citations/search`).
 *
 * Both lookups are **advisory tier-3**: the backend degrades to an empty result rather than
 * raising, and this component says "lookup unavailable" instead of inventing a record. It never
 * fabricates a citation to fill a gap ([[mock-fallback-never-fabricates-data]]).
 *
 * Layout follows Elicit's research report (the closest true peer found on Mobbin): a plain
 * hanging-indent list with the copy actions at the END of the list, not behind a dialog. The
 * related-literature search stays collapsed behind a count so the generated prose keeps the focus
 * (Qatalog).
 */
export function ReferenceList({
  citations,
  doi,
  searchSeed,
  loading = false,
}: {
  /** The deduped tool citations from the Methods section, as the synthesizer formatted them. */
  citations: string[];
  /** The reproduced paper's own DOI, if known. Absent -> tier 1 is simply not shown. */
  doi?: string | null;
  /** Seeds the related-literature query (the paper title). */
  searchSeed?: string;
  loading?: boolean;
}) {
  const paperCitation = usePaperCitation(doi);
  const paperLine = paperCitation.citation ? formatCitation(paperCitation.citation) : "";

  const all = React.useMemo(
    () => referenceBlock([paperLine, ...citations].filter(Boolean)),
    [paperLine, citations],
  );

  return (
    <ProseBlock
      id="wu-references"
      title="References"
      icon={BookText}
      sub={
        citations.length > 0 ? (
          <span className="text-[11px] text-muted-foreground/70">
            {citations.length + (paperLine ? 1 : 0)} entries
          </span>
        ) : undefined
      }
      copyText={all}
      copyLabel="Copy all"
      loading={loading}
      emptyNote="The Methods section for this paper cites no tools yet."
    >
      {(paperLine || paperCitation.loading || paperCitation.unavailable) && (
        <div className="mt-2.5">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">
            The paper you reproduced
          </p>
          {paperCitation.loading ? (
            <p className="mt-1 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              Resolving {doi}…
            </p>
          ) : paperLine ? (
            <ReferenceEntry text={paperLine} doi={paperCitation.citation?.doi} />
          ) : (
            <p className="mt-1 text-xs text-muted-foreground">
              Couldn&apos;t resolve <span className="tabular">{doi}</span> — the citation lookup is
              unavailable right now. Cite the paper from its own record.
            </p>
          )}
        </div>
      )}

      {citations.length > 0 && (
        <div className="mt-3.5">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">
            Tools and methods
          </p>
          <ul className="mt-1 space-y-1.5">
            {citations.map((c) => (
              <li key={c}>
                <ReferenceEntry text={c} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Keyed by the seed: switching which paper is being written up is a different search, so the
          query and its results reset rather than carrying over from the previous paper. */}
      <RelatedLiterature key={searchSeed ?? ""} seed={searchSeed} />
    </ProseBlock>
  );
}

/** One reference line: hanging indent, selectable, with its own copy and a DOI link when it has one. */
function ReferenceEntry({ text, doi }: { text: string; doi?: string | null }) {
  return (
    <div className="group flex items-start gap-1.5">
      <p className="min-w-0 flex-1 select-text pl-4 -indent-4 text-xs leading-relaxed text-foreground/85">
        {text}
        {doi ? (
          <>
            {" "}
            <a
              href={`https://doi.org/${doi}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-0.5 text-primary/90 hover:text-primary hover:underline"
            >
              open
              <ArrowUpRight className="size-3" />
            </a>
          </>
        ) : null}
      </p>
      <CopyButton
        text={text}
        label=""
        title="Copy this reference"
        className="h-6 px-1.5 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
      />
    </div>
  );
}

/**
 * Optional topical PubMed search for supporting references — collapsed by default so it never
 * competes with the generated prose. Advisory: `degraded` from the backend is surfaced as
 * "unavailable", never as "no results", because those are different answers.
 */
function RelatedLiterature({ seed }: { seed?: string }) {
  const [open, setOpen] = React.useState(false);
  const [q, setQ] = React.useState(seed ?? "");
  const [results, setResults] = React.useState<Citation[] | null>(null);
  const [degraded, setDegraded] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const reqRef = React.useRef(0);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    const term = q.trim();
    if (!term) return;
    const req = ++reqRef.current;
    setBusy(true);
    setDegraded(false);
    try {
      const res = await searchCitations(term, { maxResults: 8 });
      if (req !== reqRef.current) return; // a newer search won
      setResults(res.results);
      setDegraded(res.degraded);
    } catch {
      if (req === reqRef.current) {
        setResults([]);
        setDegraded(true);
      }
    } finally {
      if (req === reqRef.current) setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-3.5 inline-flex items-center gap-1.5 text-xs text-primary/90 transition-colors hover:text-primary hover:underline"
      >
        <Search className="size-3" />
        Find related literature
      </button>
    );
  }

  return (
    <div className="mt-3.5 rounded-lg border border-border bg-card/30 p-3">
      <form onSubmit={run} className="flex items-center gap-2">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. retinal organoid RPGRIP1 photoreceptor"
          aria-label="Search PubMed for related literature"
          className="h-8 text-xs"
        />
        <Button type="submit" size="sm" variant="outline" disabled={busy || !q.trim()}>
          {busy ? <Loader2 className="animate-spin" /> : <Search />}
          Search
        </Button>
      </form>
      <p className="mt-1.5 text-[11px] text-muted-foreground">
        PubMed, via the backend&apos;s cached lookup. Advisory — these are suggestions to review, not
        part of the generated Methods.
      </p>

      {results !== null && (
        <div className="mt-2.5">
          {degraded ? (
            <p className="text-xs text-muted-foreground">
              The literature lookup is unavailable right now. That is not &ldquo;no results&rdquo; —
              try again shortly.
            </p>
          ) : results.length === 0 ? (
            <p className="text-xs text-muted-foreground">No PubMed records matched that query.</p>
          ) : (
            <ul className={cn("space-y-1.5")}>
              {results.map((c) => (
                <li key={c.pmid ?? c.doi ?? c.title}>
                  <ReferenceEntry text={formatCitation(c)} doi={c.doi} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

/** Resolve the reproduced paper's own DOI to a structured record. Degrade-safe by contract. */
function usePaperCitation(doi: string | null | undefined) {
  const [citation, setCitation] = React.useState<Citation | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [unavailable, setUnavailable] = React.useState(false);

  React.useEffect(() => {
    const d = (doi ?? "").trim();
    if (!d) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reset when the doi clears
      setCitation(null);
      return;
    }
    let on = true;
    setLoading(true);
    setUnavailable(false);
    citationByDoi(d)
      .then(
        (res) => {
          if (!on) return;
          setCitation(res.citation);
          // A clean "not found" and a degraded lookup both leave us without a record; both are
          // reported as unavailable rather than silently rendering nothing.
          setUnavailable(!res.citation);
        },
        () => on && setUnavailable(true),
      )
      .finally(() => {
        if (on) setLoading(false);
      });
    return () => {
      on = false;
    };
  }, [doi]);

  return { citation, loading, unavailable };
}
