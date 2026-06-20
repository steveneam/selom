"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, FlaskConical } from "lucide-react";

import { useCatalog } from "@/lib/catalog/registry";
import { skillColor } from "@/lib/catalog/modality";
import type { SkillCatalogEntry } from "@/lib/catalog/types";
import { oosLabel } from "@/lib/skill-match/api";
import { useWorkspace, wselect } from "@/lib/workspace/store";
import type { SavedPaper } from "@/lib/workspace/types";
import { PaperPipeline } from "@/components/paper/pipeline";
import { PaperMetaHeader } from "@/components/paper/paper-meta-header";

/**
 * The SAVED Skill-Match view for a paper already in the Library — the stage-1 destination the pipeline
 * "Skill Match" pill links back to (the match a paper's Reproduction was derived from), reachable by
 * paper id without re-dropping the PDF. It renders the compact routed summary that the Library keeps
 * (D3: the L3 skill inventory + per-figure tier rollup, not the full FeasibilityMap), so for the exact
 * per-figure breakdown + the inline PDF viewer you re-drop the paper in Skill Match.
 */
export function SavedSkillMatch({ id }: { id: string }) {
  const ws = useWorkspace();
  const paper = wselect.paper(ws, id);
  const router = useRouter();

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

  return (
    <div className="mx-auto max-w-6xl px-6 py-10 lg:px-10">
      <Link
        href="/library"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Library
      </Link>

      {/* Pipeline — you're at Skill Match (saved); the "Reproduce" pill (and button) carry the paper
          forward to its Reproduction workspace. */}
      <PaperPipeline
        current="skill-match"
        className="mt-4"
        links={{ reproduce: `/reproduction/paper/${paper.id}` }}
        forward={{
          label: "Reproduce",
          icon: FlaskConical,
          onClick: () => router.push(`/reproduction/paper/${paper.id}`),
          title: "Open this paper in Reproduction to add supplementary data",
        }}
      />

      <PaperMetaHeader
        meta={paper}
        filename={paper.filename}
        className="mt-6"
        eyebrow={
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary/80">
            Skill Match · saved
          </p>
        }
      />

      <Inventory paper={paper} />

      <p className="mt-8 text-xs text-muted-foreground">
        This is the saved match summary. For the per-figure breakdown and the inline PDF viewer,{" "}
        <Link href="/skill-match" className="text-primary hover:underline">
          drop the paper again in Skill Match
        </Link>
        .
      </p>
    </div>
  );
}

/** The saved skill inventory + per-figure tier rollup (the compact summary kept on the Paper anchor). */
function Inventory({ paper }: { paper: SavedPaper }) {
  const { catalog } = useCatalog();
  const bySlug = React.useMemo(() => {
    const m = new Map<string | undefined, SkillCatalogEntry>();
    for (const e of catalog) m.set(e.id.split(".").pop(), e);
    return m;
  }, [catalog]);
  const installed = React.useMemo(
    () => new Set(catalog.filter((e) => e.tier === "verified").map((e) => e.id.split(".").pop())),
    [catalog],
  );
  const tier = paper.tierSummary;

  return (
    <section className="mt-8">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Skills this paper needs</h2>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          The paper-level inventory Skill Match routed — {paper.skills.length} skill
          {paper.skills.length === 1 ? "" : "s"} across {paper.figureCount} figure
          {paper.figureCount === 1 ? "" : "s"}
          {tier.structured + tier.recovered > 0
            ? ` · ${tier.structured} routed cleanly, ${tier.recovered} via the recovery sweep`
            : ""}
          .
        </p>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {paper.skills.map((slug) => {
          const entry = bySlug.get(slug);
          const color = entry ? skillColor(entry) : "#64748b";
          const isInstalled = installed.has(slug);
          return (
            <span
              key={slug}
              className="inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium"
              style={{
                backgroundColor: `color-mix(in oklab, ${color} 12%, transparent)`,
                borderColor: `color-mix(in oklab, ${color} 38%, transparent)`,
                color: `color-mix(in oklab, ${color} 82%, white)`,
              }}
              title={isInstalled ? "Installed — runs in your account" : "Available in the Skill Store"}
            >
              <span
                aria-hidden
                className="size-1.5 rounded-full"
                style={{ backgroundColor: color, opacity: isInstalled ? 1 : 0.4 }}
              />
              {entry?.name ?? slug}
            </span>
          );
        })}
      </div>

      {paper.outOfScope.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-muted-foreground">Out of scope:</span>
          {paper.outOfScope.map((r) => (
            <span
              key={r}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              {oosLabel(r)}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
