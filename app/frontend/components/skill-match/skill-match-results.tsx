"use client";

import * as React from "react";
import Link from "next/link";
import { motion, useReducedMotion, type Variants } from "motion/react";
import { ArrowUpRight, Bookmark, BookmarkCheck, Boxes, Check, Copy, Download, FlaskConical, Lock, Sparkles, TriangleAlert } from "lucide-react";

import { useCatalog } from "@/lib/catalog/registry";
import { skillColor, skillIcon } from "@/lib/catalog/modality";
import type { SkillCatalogEntry } from "@/lib/catalog/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { TintChip } from "@/components/ui/confidence-chip";
import { SkillDetail } from "@/components/store/skill-detail";
import {
  ATTRIBUTION_LABEL,
  confidenceColor,
  figureSkills,
  needsReview,
  oosLabel,
  oosReason,
  reviewCount,
  tierMeta,
  toSavedPaper,
} from "@/lib/skill-match/api";
import { useWorkspace, workspaceStore } from "@/lib/workspace/store";
import {
  exportFilename,
  toCSV,
  toTSV,
  type ExportFigureRow,
  type SkillMatchExport,
} from "@/lib/skill-match/export";
import type { FeasibilityMap, FigureRoute, PaperMetadata } from "@/lib/skill-match/types";
import { cn } from "@/lib/cn";

/** A translucent fill + readable border/text from one accent hex (the repo's Badge house style). */
function tint(hex: string): React.CSSProperties {
  return {
    backgroundColor: `color-mix(in oklab, ${hex} 14%, transparent)`,
    borderColor: `color-mix(in oklab, ${hex} 42%, transparent)`,
    color: `color-mix(in oklab, ${hex} 82%, white)`,
  };
}

const chip =
  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap";

// Shared column template for the per-figure list — the header and every row use it so the columns
// (figure · matched skill · tier · confidence) line up exactly.
const FIG_GRID = "grid grid-cols-[1.75rem_minmax(0,1fr)_auto_5.5rem] items-center gap-3";

/** Lookup table: bare skill slug (the router's id) → its catalog entry (id is `source.slug`). */
type SkillLookup = Map<string | undefined, SkillCatalogEntry>;

/**
 * A rich, Store-style skill pill (matches the Project's Quick-apply chips): the skill's modality
 * icon in its domain colour + its catalog display name + an installed/available marker. When `onOpen`
 * is supplied AND the skill resolves to a catalog entry, the chip is a button that opens the same
 * Store-style detail popout — a deliberate click, never a stray navigation. INSTALLED = a verified
 * catalog runner exists (runs now); otherwise the skill is available in the Store (never colour alone —
 * an icon + tooltip carry it too).
 */
function SkillChip({
  slug,
  entry,
  installed,
  onOpen,
}: {
  slug: string;
  entry?: SkillCatalogEntry;
  installed: boolean;
  onOpen?: (entry: SkillCatalogEntry) => void;
}) {
  const color = entry ? skillColor(entry) : "var(--primary)";
  const icon = entry ? skillIcon(entry) : Boxes;
  const clickable = !!(onOpen && entry);
  const status = installed
    ? `${entry?.name ?? slug} — installed (runs now)`
    : `${entry?.name ?? slug} — not installed (available in the Skill Store)`;
  const cls = cn(
    "inline-flex items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 text-xs font-medium text-foreground",
    installed ? "border-border" : "border-primary/40",
    clickable &&
      "cursor-pointer transition-colors hover:bg-accent hover:border-ring/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
  );
  const inner = (
    <>
      <span aria-hidden style={{ color }}>
        {React.createElement(icon, { className: "size-3.5" })}
      </span>
      {entry?.name ?? slug}
      {installed ? (
        <Check className="size-3 text-muted-foreground" aria-label="installed" />
      ) : (
        <Download className="size-3 text-primary" aria-label="available to install" />
      )}
    </>
  );
  return clickable ? (
    <button type="button" title={`${status} · click for details`} onClick={() => onOpen!(entry!)} className={cls}>
      {inner}
    </button>
  ) : (
    <span title={status} className={cls}>
      {inner}
    </span>
  );
}

export function SkillMatchResults({
  map,
  meta,
  filename,
}: {
  map: FeasibilityMap;
  meta?: PaperMetadata | null;
  filename?: string;
}) {
  const reduce = useReducedMotion();
  const { catalog } = useCatalog();
  // Installed = a verified catalog runner; match on the bare slug (catalog ids are `source.slug`).
  const installed = React.useMemo(
    () => new Set(catalog.filter((e) => e.tier === "verified").map((e) => e.id.split(".").pop())),
    [catalog],
  );
  const bySlug: SkillLookup = React.useMemo(() => {
    const m: SkillLookup = new Map();
    for (const e of catalog) m.set(e.id.split(".").pop(), e);
    return m;
  }, [catalog]);

  // The export payload — catalog display names resolved the same way the chips show them, so a Copy /
  // CSV reads identically to the screen. Pure + offline (lib/skill-match/export).
  const exportData: SkillMatchExport = React.useMemo(() => {
    const name = (slug: string) => bySlug.get(slug)?.name ?? slug;
    const figures: ExportFigureRow[] = map.figures.map((fr) => {
      const v = figureView(fr);
      return {
        figure: fr.figure,
        skills: v.inScope ? [v.primary, ...v.also].map(name) : [],
        tier: tierMeta(fr.tier).label,
        confidencePct: Math.round(fr.confidence * 100),
        attribution: ATTRIBUTION_LABEL[fr.attribution] ?? fr.attribution,
        outOfScope: v.oos.map(oosLabel),
      };
    });
    return {
      paper: {
        title: meta?.title ?? null,
        authors: meta?.authors ?? null,
        venue: meta?.venue ?? null,
        year: meta?.year ?? null,
        volume: meta?.volume ?? null,
        issue: meta?.issue ?? null,
        pages: meta?.pages ?? null,
        doi: meta?.doi ?? null,
        pmid: meta?.pmid ?? null,
        filename: filename ?? "paper",
      },
      skills: map.skills.map((s) => ({ name: name(s), slug: s, installed: installed.has(s) })),
      outOfScope: map.out_of_scope.map(oosLabel),
      figures,
      unmatchedTerms: map.unmatched_terms,
    };
  }, [map, meta, filename, bySlug, installed]);

  // Staggered reveal — the skills "appear as it runs". Reduced-motion → empty states = instant.
  const container: Variants = {
    hidden: {},
    show: reduce ? {} : { transition: { staggerChildren: 0.05, delayChildren: 0.03 } },
  };
  const rise: Variants = reduce
    ? { hidden: {}, show: {} }
    : { hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0, transition: { duration: 0.22, ease: "easeOut" } } };

  const installedN = map.skills.filter((s) => installed.has(s)).length;
  const hasFigs = map.figures.length > 0;
  // Two views in the right column so the per-figure breakdown reads beside the paper instead of below
  // the fold: "Overview" (summary + the paper-level skill inventory) and "Per-figure" (scrollable).
  const [tab, setTab] = React.useState<"overview" | "figures">("overview");
  // Click any skill chip -> the same Store-style detail popout (read-only here; no project context).
  const [openSkill, setOpenSkill] = React.useState<SkillCatalogEntry | null>(null);

  return (
    <div className="space-y-4">
      <div className={cn("flex items-center gap-3", hasFigs ? "justify-between" : "justify-end")}>
        {hasFigs && (
          <div role="tablist" aria-label="Skill-match results" className="inline-flex rounded-lg border border-border bg-card p-0.5 text-xs">
            <TabButton active={tab === "overview"} onClick={() => setTab("overview")}>
              Overview
            </TabButton>
            <TabButton active={tab === "figures"} onClick={() => setTab("figures")}>
              Per-figure
              <span className="ml-1.5 tabular opacity-70">{map.figures.length}</span>
            </TabButton>
          </div>
        )}
        <div className="flex shrink-0 items-center gap-1.5">
          <SaveToLibrary map={map} meta={meta} filename={filename ?? "paper"} />
          <ExportControls data={exportData} />
        </div>
      </div>

      {!hasFigs || tab === "overview" ? (
        <motion.div key="overview" className="space-y-6" variants={container} initial="hidden" animate="show">
          <motion.div variants={rise}>
            <SummaryUpsell map={map} installedN={installedN} />
          </motion.div>

          <motion.section variants={rise}>
            <SectionHeading title="Skills this paper needs">
              The paper-level inventory — every Selom skill the paper&apos;s methods and figures call for.
            </SectionHeading>
            <motion.div className="mt-3 flex flex-wrap gap-1.5" variants={container}>
              {map.skills.length === 0 && (
                <span className="text-xs text-muted-foreground">No in-scope skills detected.</span>
              )}
              {map.skills.map((s) => (
                <motion.span key={s} variants={rise}>
                  <SkillChip slug={s} entry={bySlug.get(s)} installed={installed.has(s)} onOpen={setOpenSkill} />
                </motion.span>
              ))}
            </motion.div>
            {map.skills.length > 0 && (
              <p className="mt-2 text-[11px] text-muted-foreground">
                <span className="tabular text-foreground/80">
                  {installedN}/{map.skills.length}
                </span>{" "}
                installed{" "}
                {installedN < map.skills.length
                  ? "· the rest are available in the Skill Store"
                  : "— every skill this paper needs runs in your account now"}
              </p>
            )}
            {map.skills.length > 0 && (
              <Link
                href="/store"
                className="mt-2 inline-flex items-center gap-1 text-xs text-primary/90 hover:text-primary hover:underline"
              >
                Open the Skill Store
                <ArrowUpRight className="size-3" />
              </Link>
            )}
            {map.out_of_scope.length > 0 && (
              <>
                <p className="mt-4 text-xs font-medium text-muted-foreground">Out of scope (no Selom skill)</p>
                <motion.div className="mt-2 flex flex-wrap gap-1.5" variants={container}>
                  {map.out_of_scope.map((r) => (
                    <motion.span
                      key={r}
                      variants={rise}
                      className={cn(chip, "border-border bg-muted text-muted-foreground")}
                    >
                      <FlaskConical className="size-3" />
                      {oosLabel(r)}
                    </motion.span>
                  ))}
                </motion.div>
              </>
            )}
          </motion.section>

          {map.unmatched_terms.length > 0 && (
            <motion.div variants={rise}>
              <SkillGaps terms={map.unmatched_terms} />
            </motion.div>
          )}
        </motion.div>
      ) : (
        <motion.div key="figures" variants={container} initial="hidden" animate="show">
          <SectionHeading title="Per-figure routing">
            Every skill each figure routed to, plus that figure&apos;s routing tier and confidence —
            both figure-level (confidence = the top-two evidence margin for the figure, scaled by
            where the evidence came from).
          </SectionHeading>
          <div className={cn(FIG_GRID, "mt-3 px-3 text-[10px] font-medium uppercase tracking-wider text-muted-foreground")}>
            <span>Fig</span>
            <span>Matched skills</span>
            <span>Tier</span>
            <span className="text-right">Confidence</span>
          </div>
          {/* The whole right column scrolls (its parent owns the height), so the list just flows. */}
          <motion.ul className="mt-1.5 space-y-1.5" variants={container}>
            {map.figures.map((fr) => (
              <motion.li key={fr.figure} variants={rise}>
                <FigureRow fr={fr} installed={installed} bySlug={bySlug} onOpen={setOpenSkill} />
              </motion.li>
            ))}
          </motion.ul>
        </motion.div>
      )}

      <SkillDetail
        skill={openSkill}
        installed={!!openSkill && installed.has(openSkill.id.split(".").pop())}
        onClose={() => setOpenSkill(null)}
      />
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center rounded-md px-3 py-1.5 font-medium transition-colors",
        active ? "bg-muted text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

/**
 * Copy (TSV → clipboard, pastes into Excel/Sheets) + Download CSV of the whole routing result —
 * paper metadata + skill inventory + per-figure routing. Pure, client-side, offline (the data is
 * already here); a true multi-sheet .xlsx can come later from a small backend openpyxl endpoint.
 */
function ExportControls({ data }: { data: SkillMatchExport }) {
  const [copied, setCopied] = React.useState(false);

  async function copy() {
    const tsv = toTSV(data);
    try {
      await navigator.clipboard.writeText(tsv);
    } catch {
      // Non-secure-context fallback.
      const ta = document.createElement("textarea");
      ta.value = tsv;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } catch {
        /* clipboard unavailable — nothing we can do */
      }
      ta.remove();
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  function download() {
    const blob = new Blob([toCSV(data)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = exportFilename(data);
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex shrink-0 items-center gap-1.5">
      <Button
        variant="outline"
        size="sm"
        onClick={copy}
        title="Copy as TSV — paste straight into Excel or Google Sheets"
      >
        {copied ? <Check className="text-emerald-500" /> : <Copy />}
        {copied ? "Copied" : "Copy"}
      </Button>
      <Button variant="outline" size="sm" onClick={download} title="Download the result as a CSV file">
        <Download />
        CSV
      </Button>
    </div>
  );
}

/**
 * "Save to Library" — persists this Skill-Match result as a compact `SavedPaper` in the project- and
 * data-agnostic Workspace Library so it's revisitable without re-dropping the PDF (spec §5). The
 * summary (skill inventory + per-figure tier rollup) is built from the data already on the client;
 * saving is idempotent on `doi || filename`, so the button reads "Saved" once the paper is in the
 * Library (and a click then refreshes it).
 */
function SaveToLibrary({
  map,
  meta,
  filename,
}: {
  map: FeasibilityMap;
  meta?: PaperMetadata | null;
  filename: string;
}) {
  const ws = useWorkspace();
  const key = (meta?.doi && meta.doi.trim()) || filename;
  const inLibrary = ws.papers.some((p) => ((p.doi && p.doi.trim()) || p.filename) === key);

  function save() {
    workspaceStore.savePaper(toSavedPaper(map, meta, filename));
  }

  return (
    <Button
      variant={inLibrary ? "outline" : "default"}
      size="sm"
      onClick={save}
      title={inLibrary ? "Saved to your Library — click to refresh it" : "Save this match to your Workspace Library"}
    >
      {inLibrary ? <BookmarkCheck className="text-primary" /> : <Bookmark />}
      {inLibrary ? "Saved" : "Save to Library"}
    </Button>
  );
}

// "Open in Reproduction" (the stage-1 → stage-2 handoff) now lives in the PaperPipeline header above
// the metadata (components/paper/pipeline.tsx, wired in skill-match.tsx) so the workflow reads as one
// pipeline — see [[selom-workspace-library]] §10.

function SectionHeading({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <>
      <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      <p className="mt-0.5 text-xs text-muted-foreground">{children}</p>
    </>
  );
}

/**
 * The key product moment: the FREE deterministic result (skills needed + how many you have
 * installed, plus the per-figure breakdown when the PDF exposes figure captions) and the open-core
 * Pro-AI upsell. When a PDF has no machine-readable captions, per-figure routing is honestly marked
 * unavailable (the skill inventory is the reliable deliverable) and that becomes the Pro-AI offer.
 */
function SummaryUpsell({ map, installedN }: { map: FeasibilityMap; installedN: number }) {
  const figs = map.figures.length;
  const review = reviewCount(map);
  const clean = figs - review;
  const structured = map.tier_summary?.structured ?? 0;
  const recovered = map.tier_summary?.recovered ?? 0;
  const denom = Math.max(structured + recovered, 1);
  const skillsN = map.skills.length;
  return (
    <Card className="overflow-hidden">
      <div className="grid gap-px bg-border md:grid-cols-[1.6fr_1fr]">
        <div className="bg-card p-5">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Deterministic routing · free &amp; offline
          </p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-foreground tabular">
            {skillsN} skill{skillsN === 1 ? "" : "s"} needed
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              {installedN}/{skillsN} installed
            </span>
          </p>
          {figs > 0 ? (
            <>
              <p className="mt-3 text-sm text-muted-foreground tabular">
                {figs} figure{figs === 1 ? "" : "s"} · {clean} route cleanly · {review} need review
              </p>
              <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-muted">
                <div
                  style={{ width: `${(structured / denom) * 100}%`, backgroundColor: tierMeta("structured").color }}
                  title={`${structured} structured`}
                />
                <div
                  style={{ width: `${(recovered / denom) * 100}%`, backgroundColor: tierMeta("recovered").color }}
                  title={`${recovered} recovered`}
                />
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <Legend color={tierMeta("structured").color} label="Structured" n={structured} />
                <Legend color={tierMeta("recovered").color} label="Recovered" n={recovered} />
              </div>
            </>
          ) : (
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              No machine-readable figure captions in this PDF — per-figure routing isn&apos;t
              available. The skill inventory below is the reliable result.
            </p>
          )}
        </div>

        <div className="flex flex-col justify-between gap-3 bg-card p-5">
          {figs === 0 ? (
            <ProUpsell body="This PDF has no machine-readable figure captions. Pro AI maps each figure to its skill on tricky journal layouts — the skill inventory is always free." />
          ) : review > 0 ? (
            <ProUpsell
              body={
                <>
                  <span className="text-foreground">{review}</span> figure{review === 1 ? "" : "s"} routed
                  with low confidence or via the recovery sweep. Pro AI verifies these on tricky
                  journal layouts — the deterministic map above is always free.
                </>
              }
            />
          ) : (
            <div className="flex h-full flex-col justify-center">
              <p className="flex items-center gap-1.5 text-sm font-semibold" style={{ color: tierMeta("structured").color }}>
                <Sparkles className="size-4" />
                All figures routed cleanly
              </p>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                Every figure routed from a clean caption — no Pro AI verification needed.
              </p>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function ProUpsell({ body }: { body: React.ReactNode }) {
  return (
    <>
      <div>
        <p className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
          <Sparkles className="size-4" style={{ color: tierMeta("recovered").color }} />
          Pro AI verification
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{body}</p>
      </div>
      <button
        type="button"
        disabled
        title="Pro AI verification — coming soon"
        className="inline-flex items-center justify-center gap-1.5 rounded-md border px-3 py-2 text-xs font-semibold"
        style={tint(tierMeta("recovered").color)}
      >
        <Lock className="size-3.5" />
        Verify with Pro AI · coming soon
      </button>
    </>
  );
}

function Legend({ color, label, n }: { color: string; label: string; n: number }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden className="size-2 rounded-[3px]" style={{ backgroundColor: color }} />
      {label} <span className="tabular text-foreground/70">{n}</span>
    </span>
  );
}

/**
 * One figure's effective routing, derived the same way the engine's auto-ledger does: a figure with
 * ANY in-scope skill candidate is in-scope (its primary = the top-ranked in-scope skill), even when
 * an out-of-scope readout out-scored it overall. `fr.top`/`fr.in_scope` (the raw overall winner) are
 * intentionally NOT trusted here.
 */
function figureView(fr: FigureRoute) {
  const skills = figureSkills(fr);
  const oos = Array.from(
    new Set(fr.candidates.filter((c) => c.target.startsWith("oos:")).map((c) => oosReason(c.target))),
  );
  return {
    inScope: skills.length > 0,
    primary: skills[0] ?? oosLabel(oosReason(fr.top) || fr.reason),
    also: skills.slice(1),
    oos,
  };
}

function FigureRow({
  fr,
  installed,
  bySlug,
  onOpen,
}: {
  fr: FigureRoute;
  installed: Set<string | undefined>;
  bySlug: SkillLookup;
  onOpen: (entry: SkillCatalogEntry) => void;
}) {
  const v = figureView(fr);
  const tm = tierMeta(fr.tier);
  const flagged = needsReview(fr);
  const pct = Math.round(fr.confidence * 100);
  const heat = confidenceColor(fr.confidence);
  // Every in-scope skill the figure routed to, top-ranked first — all shown as chips (below), so the
  // engine's full match for a figure reads at a glance rather than hiding in a sentence.
  const skills = v.inScope ? [v.primary, ...v.also] : [];
  // The sub-line carries only the non-skill context: a co-present out-of-scope readout + the evidence
  // source (the skills themselves are now chips, not prose).
  const sub = [
    v.inScope && v.oos.length ? `+ ${v.oos.map(oosLabel).join(", ")} readout` : "",
    ATTRIBUTION_LABEL[fr.attribution] ?? fr.attribution,
  ].filter(Boolean).join(" · ");
  return (
    <div
      className={cn(FIG_GRID, "items-start rounded-lg border border-border bg-card px-3 py-2.5")}
      style={flagged ? { borderLeft: `2px solid ${tierMeta("recovered").color}` } : undefined}
    >
      <span className="mt-0.5 grid size-6 place-items-center rounded-md bg-muted text-xs font-semibold text-foreground tabular">
        {fr.figure}
      </span>
      <div className="min-w-0">
        {v.inScope ? (
          <div className="flex flex-wrap gap-1.5">
            {skills.map((slug) => (
              <SkillChip
                key={slug}
                slug={slug}
                entry={bySlug.get(slug)}
                installed={installed.has(slug)}
                onOpen={onOpen}
              />
            ))}
          </div>
        ) : (
          <span className={cn(chip, "border-border bg-muted text-muted-foreground")}>
            <FlaskConical className="size-3" />
            {v.primary}
          </span>
        )}
        {sub && (
          <p className="mt-1.5 truncate text-[11px] text-muted-foreground" title={sub}>
            {sub}
          </p>
        )}
      </div>
      <TintChip color={tm.color} label={tm.label} size="sm" title={tm.hint} className="justify-self-start" />
      <div className="flex items-center justify-end gap-2" title={`routing confidence ${pct}%`}>
        <div className="h-1.5 w-12 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: heat }} />
        </div>
        <span className="w-8 text-right text-xs font-medium tabular" style={{ color: heat }}>
          {pct}%
        </span>
      </div>
    </div>
  );
}

function SkillGaps({ terms }: { terms: string[] }) {
  return (
    <section>
      <h2 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
        <TriangleAlert className="size-4 text-muted-foreground" />
        Method terms with no Selom skill
      </h2>
      <p className="mt-0.5 text-xs text-muted-foreground">
        Routed to nothing in the registry — the Skill Foundry backlog signal.
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {terms.map((t) => (
          <span key={t} className={cn(chip, "border-dashed border-border bg-transparent text-muted-foreground")}>
            {t}
          </span>
        ))}
      </div>
    </section>
  );
}
