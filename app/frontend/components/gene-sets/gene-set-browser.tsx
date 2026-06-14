"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Bookmark, BookmarkCheck, FlaskConical, Layers, Search, Sparkles, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/cn";
import {
  getGeneSet,
  searchGeneSets,
  sourceColor,
  type GeneSetCard,
  type GeneSetSource,
} from "@/lib/gene-sets/api";
import { projectStore, select, useProjects } from "@/lib/projects/store";
import type { GeneSet } from "@/lib/projects/types";
import { dispatchIntent } from "@/lib/workspace/intent";

/**
 * The "Gene Sets" surface (gene-set builder Phase A · DECISIONS #11).
 *
 * A list-first, license-clean catalog over the corpus Selom owns or that is open
 * (GO · WikiPathways · curated). Search/browse → apply to data: a single set
 * highlights its panel in the volcano; a whole source becomes the enrichment library.
 * Picked sets save to a project as a provenance-stamped GeneSet for reuse.
 */
export function GeneSetBrowser() {
  const router = useRouter();
  const state = useProjects();
  const { projects } = state;

  const [query, setQuery] = React.useState("");
  const [sourceKey, setSourceKey] = React.useState("all");
  const [targetId, setTargetId] = React.useState<string | undefined>(undefined);
  const [sources, setSources] = React.useState<GeneSetSource[]>([]);
  const [results, setResults] = React.useState<GeneSetCard[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const [detail, setDetail] = React.useState<GeneSetCard | null>(null);

  const target = targetId ?? projects[0]?.id;
  const savedSets = target ? select.geneSets(state, target) : [];
  const savedFrom = new Set(savedSets.map((g) => g.createdFrom).filter(Boolean) as string[]);

  // Debounced search; aborts the in-flight request when the query/source changes.
  React.useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    const t = setTimeout(() => {
      searchGeneSets(query, sourceKey, 60, ctrl.signal)
        .then((r) => {
          setSources(r.sources);
          setResults(r.results);
          setError(null);
        })
        .catch((e) => {
          if (e?.name !== "AbortError") setError("Couldn't load gene sets. Is the analysis service running?");
        })
        .finally(() => setLoading(false));
    }, 180);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [query, sourceKey]);

  /** Ensure there is a project to apply/save into; create one on first use. */
  function ensureTarget(): string {
    if (target) return target;
    const p = projectStore.createProject("Untitled project");
    setTargetId(p.id);
    return p.id;
  }

  // Apply a single set's members as a volcano highlight panel → opens the project Workbench.
  async function highlightInVolcano(card: GeneSetCard) {
    setBusyId(card.id);
    try {
      const full = await getGeneSet(card.id);
      const projectId = ensureTarget();
      dispatchIntent({
        projectId,
        tab: "workbench",
        skillId: "selom.volcano",
        params: { highlight: full.genes.join(", ") },
      });
      router.push(`/p/${projectId}`);
    } catch {
      setError("Couldn't load that gene set's members. Please try again.");
    } finally {
      setBusyId(null);
    }
  }

  // Apply a whole source as the enrichment library → opens the project Workbench.
  function enrichAgainstSource() {
    const projectId = ensureTarget();
    dispatchIntent({
      projectId,
      tab: "workbench",
      skillId: "selom.enrichment",
      params: { gene_sets: sourceKey },
    });
    router.push(`/p/${projectId}`);
  }

  async function saveToProject(card: GeneSetCard) {
    setBusyId(card.id);
    try {
      const full = await getGeneSet(card.id);
      const projectId = ensureTarget();
      projectStore.saveGeneSet(projectId, {
        name: full.name,
        genes: full.genes,
        source: full.source,
        sourceLabel: full.source_label,
        license: full.license,
        createdFrom: full.id,
      });
    } catch {
      setError("Couldn't save that gene set. Please try again.");
    } finally {
      setBusyId(null);
    }
  }

  const filterOptions = [{ key: "all", label: "All" }, ...sources.map((s) => ({ key: s.key, label: s.label }))];
  const activeSource = sources.find((s) => s.key === sourceKey);
  const targetProject = projects.find((p) => p.id === target);

  return (
    <div className="space-y-5">
      {/* search + target project */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search gene sets"
            placeholder="Search gene sets…  e.g. cilium, phototransduction"
            className="h-9 w-full rounded-md border border-input bg-background/60 pl-8 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
          />
        </label>

        <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
          <span>Apply into</span>
          <div className="w-44">
            <Select value={target ?? ""} onValueChange={setTargetId}>
              <SelectTrigger aria-label="Target project">
                <SelectValue placeholder="No project — create one" />
              </SelectTrigger>
              <SelectContent>
                {projects.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* source filter + the collection-level apply (enrichment library) */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex items-center gap-0.5 rounded-lg bg-muted/60 p-1">
          {filterOptions.map((o) => (
            <button
              key={o.key}
              type="button"
              onClick={() => setSourceKey(o.key)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                sourceKey === o.key ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {o.key !== "all" && (
                <span aria-hidden className="size-2 rounded-full" style={{ background: sourceColor(o.key) }} />
              )}
              {o.label}
            </button>
          ))}
        </div>

        {activeSource && (
          <Button variant="outline" size="sm" onClick={enrichAgainstSource} className="gap-1.5">
            <FlaskConical className="size-4" />
            Enrich against {activeSource.label}
          </Button>
        )}

        <span className="tabular ml-auto text-xs text-muted-foreground">
          {loading ? "…" : `${results.length} shown`}
          {activeSource ? ` · ${activeSource.n_sets.toLocaleString()} in ${activeSource.label}` : ""}
        </span>
      </div>

      {error && (
        <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* saved in this project */}
      {savedSets.length > 0 && (
        <SavedStrip sets={savedSets} onApply={(g) => applySaved(g)} onRemove={(id) => projectStore.removeGeneSet(id)} />
      )}

      {/* results */}
      {loading ? (
        <SkeletonGrid />
      ) : results.length === 0 ? (
        <div className="grid place-items-center rounded-xl border border-dashed border-border p-12 text-center">
          <Layers className="size-6 text-muted-foreground" />
          <p className="mt-2 text-sm font-medium text-foreground">No gene sets match</p>
          <p className="mt-1 text-xs text-muted-foreground">Try a broader term, or switch the source filter.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {results.map((set) => (
            <SetCard
              key={set.id}
              set={set}
              busy={busyId === set.id}
              saved={savedFrom.has(set.id)}
              onOpen={() => setDetail(set)}
              onHighlight={() => highlightInVolcano(set)}
              onSave={() => saveToProject(set)}
            />
          ))}
        </div>
      )}

      <MembersDialog
        card={detail}
        busy={detail ? busyId === detail.id : false}
        saved={detail ? savedFrom.has(detail.id) : false}
        targetName={targetProject?.name}
        onClose={() => setDetail(null)}
        onHighlight={() => detail && highlightInVolcano(detail)}
        onSave={() => detail && saveToProject(detail)}
      />
    </div>
  );

  function applySaved(g: GeneSet) {
    const projectId = ensureTarget();
    dispatchIntent({
      projectId,
      tab: "workbench",
      skillId: "selom.volcano",
      params: { highlight: g.genes.join(", ") },
    });
    router.push(`/p/${projectId}`);
  }
}

function SetCard({
  set,
  busy,
  saved,
  onOpen,
  onHighlight,
  onSave,
}: {
  set: GeneSetCard;
  busy: boolean;
  saved: boolean;
  onOpen: () => void;
  onHighlight: () => void;
  onSave: () => void;
}) {
  const color = sourceColor(set.source);
  return (
    <Card className="flex flex-col gap-3 p-4 transition-colors hover:border-primary/30">
      <div className="flex items-start justify-between gap-2">
        <button onClick={onOpen} className="min-w-0 text-left">
          <h3 className="truncate text-sm font-semibold text-foreground hover:text-primary">{set.name}</h3>
          <span
            className="mt-1 inline-flex items-center gap-1.5 text-[11px] font-medium"
            style={{ color }}
          >
            <span aria-hidden className="size-2 rounded-full" style={{ background: color }} />
            {set.source_label}
          </span>
        </button>
        <span className="tabular shrink-0 rounded-md bg-muted/60 px-1.5 py-0.5 text-[11px] text-muted-foreground">
          {set.size.toLocaleString()} genes
        </span>
      </div>

      {/* sample member chips */}
      <div className="flex flex-wrap gap-1">
        {set.sample_genes.slice(0, 6).map((g) => (
          <span key={g} className="tabular rounded bg-secondary/60 px-1.5 py-0.5 text-[10px] font-medium text-secondary-foreground">
            {g}
          </span>
        ))}
        {set.size > 6 && <span className="px-1 py-0.5 text-[10px] text-muted-foreground">+{(set.size - 6).toLocaleString()}</span>}
      </div>

      <div className="mt-auto flex items-center gap-2 pt-1">
        <Button size="sm" className="h-8 flex-1 gap-1.5 px-2.5 text-xs" disabled={busy} onClick={onHighlight}>
          <Sparkles className="size-3.5" /> {busy ? "…" : "Highlight in volcano"}
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="size-8 shrink-0 text-muted-foreground"
          disabled={busy}
          aria-label={saved ? "Saved to project" : "Save to project"}
          title={saved ? "Saved to project" : "Save to project"}
          onClick={onSave}
        >
          {saved ? <BookmarkCheck className="size-4 text-primary" /> : <Bookmark className="size-4" />}
        </Button>
      </div>

      <span className="text-[10px] text-muted-foreground/80">License: {set.license}</span>
    </Card>
  );
}

function SavedStrip({
  sets,
  onApply,
  onRemove,
}: {
  sets: GeneSet[];
  onApply: (g: GeneSet) => void;
  onRemove: (id: string) => void;
}) {
  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
        <BookmarkCheck className="size-3 text-primary" /> Saved in this project
      </p>
      <div className="flex flex-wrap gap-2">
        {sets.map((g) => (
          <span
            key={g.id}
            className="group inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs text-foreground"
          >
            <span aria-hidden className="size-2 rounded-full" style={{ background: sourceColor(g.source) }} />
            <button onClick={() => onApply(g)} className="font-medium hover:text-primary" title="Highlight in volcano">
              {g.name}
            </button>
            <span className="tabular text-[10px] text-muted-foreground">{g.genes.length}</span>
            <button
              onClick={() => onRemove(g.id)}
              aria-label={`Remove ${g.name}`}
              className="grid size-4 place-items-center rounded text-muted-foreground/70 hover:text-destructive"
            >
              <X className="size-3" />
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, i) => (
        <Card key={i} className="h-40 animate-pulse p-4">
          <div className="h-4 w-2/3 rounded bg-muted" />
          <div className="mt-2 h-3 w-1/3 rounded bg-muted/70" />
          <div className="mt-4 flex gap-1">
            {Array.from({ length: 5 }).map((_, j) => (
              <div key={j} className="h-4 w-9 rounded bg-muted/60" />
            ))}
          </div>
          <div className="mt-6 h-8 w-full rounded bg-muted/70" />
        </Card>
      ))}
    </div>
  );
}

function MembersDialog({
  card,
  busy,
  saved,
  targetName,
  onClose,
  onHighlight,
  onSave,
}: {
  card: GeneSetCard | null;
  busy: boolean;
  saved: boolean;
  targetName?: string;
  onClose: () => void;
  onHighlight: () => void;
  onSave: () => void;
}) {
  const [genes, setGenes] = React.useState<string[] | null>(null);
  const closeRef = React.useRef<HTMLButtonElement>(null);

  React.useEffect(() => {
    if (!card) {
      setGenes(null);
      return;
    }
    const ctrl = new AbortController();
    getGeneSet(card.id, ctrl.signal)
      .then((d) => setGenes(d.genes))
      .catch(() => {});
    closeRef.current?.focus();
    return () => ctrl.abort();
  }, [card]);

  React.useEffect(() => {
    if (!card) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [card, onClose]);

  if (!card) return null;
  const color = sourceColor(card.source);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4"
      role="presentation"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${card.name} — members`}
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-border p-5">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-foreground">{card.name}</h2>
            <p className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5 font-medium" style={{ color }}>
                <span aria-hidden className="size-2 rounded-full" style={{ background: color }} />
                {card.source_label}
              </span>
              <span aria-hidden>·</span>
              <span className="tabular">{card.size.toLocaleString()} genes</span>
              <span aria-hidden>·</span>
              <Badge variant="community">{card.license}</Badge>
            </p>
          </div>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label="Close"
            className="grid size-8 shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {genes ? (
            <div className="flex flex-wrap gap-1.5">
              {genes.map((g) => (
                <span key={g} className="tabular rounded bg-secondary/60 px-1.5 py-0.5 text-[11px] font-medium text-secondary-foreground">
                  {g}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Loading members…</p>
          )}
        </div>

        <div className="flex items-center gap-2 border-t border-border p-4">
          <Button className="flex-1 gap-1.5" disabled={busy} onClick={onHighlight}>
            <Sparkles className="size-4" /> Highlight in volcano
          </Button>
          <Button variant="outline" className="gap-1.5" disabled={busy} onClick={onSave}>
            {saved ? <BookmarkCheck className="size-4 text-primary" /> : <Bookmark className="size-4" />}
            {saved ? "Saved" : "Save"}
          </Button>
        </div>
        {targetName && (
          <p className="border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
            Applies into <span className="text-foreground">{targetName}</span>.
          </p>
        )}
      </div>
    </div>
  );
}
