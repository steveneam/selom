"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowUpRight,
  Boxes,
  Check,
  Copy,
  Dna,
  Download,
  FileText,
  FlaskConical,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SkillDetail } from "@/components/store/skill-detail";
import { useCatalog } from "@/lib/catalog/registry";
import { skillColor, skillIcon } from "@/lib/catalog/modality";
import type { SkillCatalogEntry } from "@/lib/catalog/types";
import { projectStore, useProjects } from "@/lib/projects/store";
import type { GeneSet } from "@/lib/projects/types";
import { useWorkspace, workspaceStore } from "@/lib/workspace/store";
import type { SavedPaper } from "@/lib/workspace/types";
import { dispatchIntent } from "@/lib/workspace/intent";
import { pushUndo } from "@/lib/workspace/undo";
import { authorSummary, citationLine, oosLabel, tierMeta } from "@/lib/skill-match/api";
import { sourceColor } from "@/lib/gene-sets/api";
import {
  exportFilename,
  toCSV,
  toTSV,
  type ExportSkillRow,
  type SkillMatchExport,
} from "@/lib/skill-match/export";
import { cn } from "@/lib/cn";

type Tab = "papers" | "genesets" | "skills";

/** bare slug (router id) → catalog entry (entry id is `<source>.<slug>`). */
type SkillLookup = Map<string | undefined, SkillCatalogEntry>;

export function LibraryView() {
  const ws = useWorkspace();
  const { catalog } = useCatalog();
  const [tab, setTab] = React.useState<Tab>("papers");
  const [openSkill, setOpenSkill] = React.useState<SkillCatalogEntry | null>(null);

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
  // Workspace-installed skills resolve to catalog entries by full id (`selom.deg`).
  const byId = React.useMemo(() => new Map(catalog.map((e) => [e.id, e])), [catalog]);

  const counts = { papers: ws.papers.length, genesets: ws.geneSets.length, skills: ws.skills.length };

  return (
    <div className="space-y-6">
      <div role="tablist" aria-label="Library collections" className="inline-flex rounded-lg border border-border bg-card p-0.5 text-sm">
        <TabButton active={tab === "papers"} onClick={() => setTab("papers")} icon={<FileText className="size-4" />} label="Papers" count={counts.papers} />
        <TabButton active={tab === "genesets"} onClick={() => setTab("genesets")} icon={<Dna className="size-4" />} label="Gene sets" count={counts.genesets} />
        <TabButton active={tab === "skills"} onClick={() => setTab("skills")} icon={<Boxes className="size-4" />} label="Skills" count={counts.skills} />
      </div>

      {tab === "papers" && <PapersTab papers={ws.papers} bySlug={bySlug} installed={installed} onOpenSkill={setOpenSkill} />}
      {tab === "genesets" && <GeneSetsTab sets={ws.geneSets} />}
      {tab === "skills" && <SkillsTab skills={ws.skills} byId={byId} installed={installed} onOpenSkill={setOpenSkill} />}

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
  icon,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  count: number;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-colors",
        active ? "bg-muted text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {icon}
      {label}
      <span className="tabular ml-1 text-xs opacity-70">{count}</span>
    </button>
  );
}

function EmptyState({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="grid place-items-center rounded-xl border border-dashed border-border px-6 py-16 text-center">
      <span className="text-muted-foreground/50">{icon}</span>
      <p className="mt-3 text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 max-w-sm text-xs text-muted-foreground">{children}</p>
    </div>
  );
}

/** A compact skill pill (icon + catalog name + an installed/available marker). Opens the Store-style
 *  detail popout when it resolves to a catalog entry — a deliberate click, never a stray navigation. */
function SkillPill({
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
  const cls = cn(
    "inline-flex items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 text-xs font-medium text-foreground",
    installed ? "border-border" : "border-primary/40",
    clickable && "cursor-pointer transition-colors hover:bg-accent hover:border-ring/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
  );
  const status = installed ? `${entry?.name ?? slug} — installed (runs now)` : `${entry?.name ?? slug} — available in the Skill Store`;
  const inner = (
    <>
      <span aria-hidden style={{ color }}>
        {React.createElement(icon, { className: "size-3.5" })}
      </span>
      {entry?.name ?? slug}
      {installed ? <Check className="size-3 text-muted-foreground" aria-label="installed" /> : <Download className="size-3 text-primary" aria-label="available" />}
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

// ── Papers ──────────────────────────────────────────────────────────────────

function PapersTab({
  papers,
  bySlug,
  installed,
  onOpenSkill,
}: {
  papers: SavedPaper[];
  bySlug: SkillLookup;
  installed: Set<string | undefined>;
  onOpenSkill: (entry: SkillCatalogEntry) => void;
}) {
  if (papers.length === 0) {
    return (
      <EmptyState icon={<FileText className="size-8" />} title="No saved papers yet">
        Drop a PDF in <Link href="/skill-match" className="text-primary hover:underline">Skill Match</Link> and hit{" "}
        <span className="text-foreground">Save to Library</span> to keep its matched skills here.
      </EmptyState>
    );
  }
  return (
    <div className="space-y-3">
      {papers.map((p) => (
        <PaperRow key={p.id} paper={p} bySlug={bySlug} installed={installed} onOpenSkill={onOpenSkill} />
      ))}
    </div>
  );
}

function PaperRow({
  paper,
  bySlug,
  installed,
  onOpenSkill,
}: {
  paper: SavedPaper;
  bySlug: SkillLookup;
  installed: Set<string | undefined>;
  onOpenSkill: (entry: SkillCatalogEntry) => void;
}) {
  const name = (slug: string) => bySlug.get(slug)?.name ?? slug;
  const cite = citationLine(paper);
  const authors = authorSummary(paper.authors);
  const installedN = paper.skills.filter((s) => installed.has(s)).length;

  function remove() {
    const removed = workspaceStore.removePaper(paper.id);
    if (removed) pushUndo(`Removed “${removed.title || removed.filename}” from the Library`, () => workspaceStore.restorePaper(removed));
  }

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-foreground" title={paper.title || paper.filename}>
            {paper.title || paper.filename}
          </h3>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {[authors, cite].filter(Boolean).join(" · ") || paper.filename}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            {paper.doi && (
              <a href={`https://doi.org/${paper.doi}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-primary/90 hover:text-primary hover:underline">
                DOI <ArrowUpRight className="size-3" />
              </a>
            )}
            {paper.pmid && (
              <a href={`https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-primary/90 hover:text-primary hover:underline">
                PMID {paper.pmid} <ArrowUpRight className="size-3" />
              </a>
            )}
            {paper.isPreprint && (
              <span className="rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 font-medium text-amber-600 dark:text-amber-400">preprint</span>
            )}
            <span className="tabular truncate" title={paper.filename}>{paper.filename}</span>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <PaperExport paper={paper} nameOf={name} installed={installed} />
          <Button variant="ghost" size="icon" className="size-8 text-muted-foreground hover:text-destructive" onClick={remove} aria-label="Remove from Library" title="Remove from Library">
            <Trash2 className="size-4" />
          </Button>
        </div>
      </div>

      {/* the stored routing summary (inventory + per-figure tier rollup; spec D3) */}
      <div className="mt-3.5 border-t border-border pt-3.5">
        <p className="text-xs text-muted-foreground tabular">
          <span className="font-medium text-foreground/80">{paper.skills.length}</span> skill{paper.skills.length === 1 ? "" : "s"}
          {" · "}
          <span className="font-medium text-foreground/80">{installedN}/{paper.skills.length}</span> installed
          {" · "}
          <span className="font-medium text-foreground/80">{paper.figureCount}</span> figure{paper.figureCount === 1 ? "" : "s"}
          {(paper.tierSummary.structured + paper.tierSummary.recovered) > 0 && (
            <>
              {" · "}
              <TierDot color={tierMeta("structured").color} /> {paper.tierSummary.structured} structured
              {" · "}
              <TierDot color={tierMeta("recovered").color} /> {paper.tierSummary.recovered} recovered
            </>
          )}
        </p>
        {paper.skills.length > 0 ? (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {paper.skills.map((s) => (
              <SkillPill key={s} slug={s} entry={bySlug.get(s)} installed={installed.has(s)} onOpen={onOpenSkill} />
            ))}
          </div>
        ) : (
          <p className="mt-2 text-xs text-muted-foreground">No in-scope skills were detected for this paper.</p>
        )}
        {paper.outOfScope.length > 0 && (
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-muted-foreground">Out of scope:</span>
            {paper.outOfScope.map((r) => (
              <span key={r} className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                <FlaskConical className="size-3" />
                {oosLabel(r)}
              </span>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function TierDot({ color }: { color: string }) {
  return <span aria-hidden className="mr-0.5 inline-block size-2 rounded-[3px] align-middle" style={{ backgroundColor: color }} />;
}

/** Copy (TSV) / CSV of a saved paper's summary — paper block + skill inventory (no per-figure rows;
 *  those aren't stored, spec D3). Reuses the pure Skill-Match export serializers. */
function PaperExport({
  paper,
  nameOf,
  installed,
}: {
  paper: SavedPaper;
  nameOf: (slug: string) => string;
  installed: Set<string | undefined>;
}) {
  const [copied, setCopied] = React.useState(false);
  const data: SkillMatchExport = React.useMemo(() => {
    const skills: ExportSkillRow[] = paper.skills.map((s) => ({ name: nameOf(s), slug: s, installed: installed.has(s) }));
    return {
      paper: {
        title: paper.title ?? null,
        authors: paper.authors ?? null,
        venue: paper.venue ?? null,
        year: paper.year ?? null,
        volume: paper.volume ?? null,
        issue: paper.issue ?? null,
        pages: paper.pages ?? null,
        doi: paper.doi ?? null,
        pmid: paper.pmid ?? null,
        filename: paper.filename,
      },
      skills,
      outOfScope: paper.outOfScope.map(oosLabel),
      figures: [],
      unmatchedTerms: [],
    };
  }, [paper, nameOf, installed]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(toTSV(data));
    } catch {
      /* clipboard unavailable */
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
    <>
      <Button variant="outline" size="sm" onClick={copy} title="Copy as TSV — paste into Excel / Sheets">
        {copied ? <Check className="text-emerald-500" /> : <Copy />}
        {copied ? "Copied" : "Copy"}
      </Button>
      <Button variant="outline" size="sm" onClick={download} title="Download the summary as CSV">
        <Download />
        CSV
      </Button>
    </>
  );
}

// ── Gene sets ─────────────────────────────────────────────────────────────────

function GeneSetsTab({ sets }: { sets: GeneSet[] }) {
  const router = useRouter();
  const { projects } = useProjects();

  /** Applying runs the panel in a project — ensure one exists, then deep-link the Workbench. */
  function apply(g: GeneSet) {
    const projectId = projects[0]?.id ?? projectStore.createProject("Untitled project").id;
    dispatchIntent({ projectId, tab: "workbench", skillId: "selom.volcano", params: { highlight: g.genes.join(", ") } });
    router.push(`/p/${projectId}`);
  }
  function remove(g: GeneSet) {
    workspaceStore.removeGeneSet(g.id);
  }

  if (sets.length === 0) {
    return (
      <EmptyState icon={<Dna className="size-8" />} title="No gene sets saved yet">
        Curate panels in <Link href="/gene-sets" className="text-primary hover:underline">Gene Sets</Link> and save them
        — they&apos;ll live here, reusable across every project.
      </EmptyState>
    );
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {sets.map((g) => (
        <Card key={g.id} className="flex flex-col gap-3 p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold text-foreground" title={g.name}>{g.name}</h3>
              <span className="mt-1 inline-flex items-center gap-1.5 text-[11px] font-medium" style={{ color: sourceColor(g.source) }}>
                <span aria-hidden className="size-2 rounded-full" style={{ background: sourceColor(g.source) }} />
                {g.sourceLabel}
              </span>
            </div>
            <span className="tabular shrink-0 rounded-md bg-muted/60 px-1.5 py-0.5 text-[11px] text-muted-foreground">{g.genes.length} genes</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {g.genes.slice(0, 6).map((gene) => (
              <span key={gene} className="tabular rounded bg-secondary/60 px-1.5 py-0.5 text-[10px] font-medium text-secondary-foreground">{gene}</span>
            ))}
            {g.genes.length > 6 && <span className="px-1 py-0.5 text-[10px] text-muted-foreground">+{g.genes.length - 6}</span>}
          </div>
          <div className="mt-auto flex items-center gap-2 pt-1">
            <Button size="sm" className="h-8 flex-1 gap-1.5 px-2.5 text-xs" onClick={() => apply(g)}>
              <Sparkles className="size-3.5" /> Highlight in volcano
            </Button>
            <Button size="icon" variant="ghost" className="size-8 shrink-0 text-muted-foreground hover:text-destructive" aria-label={`Remove ${g.name}`} title="Remove from Library" onClick={() => remove(g)}>
              <X className="size-4" />
            </Button>
          </div>
          <span className="text-[10px] text-muted-foreground/80">License: {g.license}</span>
        </Card>
      ))}
    </div>
  );
}

// ── Skills ────────────────────────────────────────────────────────────────────

function SkillsTab({
  skills,
  byId,
  installed,
  onOpenSkill,
}: {
  skills: { skillId: string }[];
  byId: Map<string, SkillCatalogEntry>;
  installed: Set<string | undefined>;
  onOpenSkill: (entry: SkillCatalogEntry) => void;
}) {
  if (skills.length === 0) {
    return (
      <EmptyState icon={<Boxes className="size-8" />} title="No skills in your library yet">
        Add skills from the <Link href="/store" className="text-primary hover:underline">Skill Store</Link> — they&apos;ll
        be available across every project.
      </EmptyState>
    );
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5">
        {skills.map((s) => {
          const slug = s.skillId.split(".").pop()!;
          return <SkillPill key={s.skillId} slug={slug} entry={byId.get(s.skillId)} installed={installed.has(slug)} onOpen={onOpenSkill} />;
        })}
      </div>
      <Link href="/store" className="inline-flex items-center gap-1 text-xs text-primary/90 hover:text-primary hover:underline">
        Open the Skill Store
        <ArrowUpRight className="size-3" />
      </Link>
    </div>
  );
}
