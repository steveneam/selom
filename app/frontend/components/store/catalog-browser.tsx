"use client";

import * as React from "react";
import { Search } from "lucide-react";
import { SkillCard } from "./skill-card";
import { SkillDetail } from "./skill-detail";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/ui/cn";
import { CATEGORY_GROUPS, humanizeCategory } from "@/lib/catalog/modality";
import { useCatalog } from "@/lib/catalog/registry";
import type { SkillCatalogEntry, SkillSource, SkillTier } from "@/lib/catalog/types";
import { useWorkspace, workspaceStore, wselect } from "@/lib/workspace/store";

type TierFilter = "all" | SkillTier;
type SourceFilter = "all" | SkillSource;

// Editorial App-Store shelves come from CATEGORY_GROUPS (single source of truth,
// shared with the per-card category colour in lib/catalog/modality).
const GROUPS = CATEGORY_GROUPS;

export function CatalogBrowser() {
  // Skill installs are workspace-level (account-wide, spec D1/D2) — the Store no longer asks
  // "which project"; installing makes a skill available in every project.
  const ws = useWorkspace();
  const { catalog } = useCatalog();

  // Filter facets follow the live catalog, not a fixed seed list.
  const categories = React.useMemo(
    () => Array.from(new Set(catalog.map((s) => s.category))).sort(),
    [catalog],
  );
  const omicsFacets = React.useMemo(
    () => Array.from(new Set(catalog.flatMap((s) => s.omics))).sort(),
    [catalog],
  );

  const [query, setQuery] = React.useState("");
  const [tier, setTier] = React.useState<TierFilter>("all");
  const [source, setSource] = React.useState<SourceFilter>("all");
  const [omics, setOmics] = React.useState<string>("all");
  const [category, setCategory] = React.useState<string>("all");
  const [open, setOpen] = React.useState<SkillCatalogEntry | null>(null);

  const installedIds = React.useMemo(() => wselect.installedSkillIds(ws), [ws]);

  const results = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return catalog.filter((s) => {
      if (tier !== "all" && s.tier !== tier) return false;
      if (source !== "all" && s.source !== source) return false;
      if (omics !== "all" && !s.omics.includes(omics)) return false;
      if (category !== "all" && s.category !== category) return false;
      if (q && !(`${s.name} ${s.summary} ${s.category}`.toLowerCase().includes(q))) return false;
      return true;
    }).sort((a, b) => b.popularity - a.popularity);
  }, [catalog, query, tier, source, omics, category]);

  // App-Store shelves only when browsing (no active search/filter); otherwise a
  // single flat results grid keeps "find" mode focused.
  const isFiltering =
    query.trim() !== "" || tier !== "all" || source !== "all" || omics !== "all" || category !== "all";

  const shelves = React.useMemo(() => {
    const claimed = new Set<string>();
    const out = GROUPS.map((g) => {
      const items = results.filter((s) => g.categories.includes(s.category));
      items.forEach((s) => claimed.add(s.id));
      return { ...g, items };
    }).filter((g) => g.items.length > 0);
    const rest = results.filter((s) => !claimed.has(s.id));
    if (rest.length > 0) {
      out.push({
        title: "More tools",
        subtitle: "Everything else in the catalog.",
        color: "#8b98a9",
        categories: [],
        items: rest,
      });
    }
    return out;
  }, [results]);

  function toggleInstall(skill: SkillCatalogEntry) {
    if (installedIds.has(skill.id)) workspaceStore.uninstallSkill(skill.id);
    else workspaceStore.installSkill(skill.id);
  }

  return (
    <div className="space-y-5">
      {/* search */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search skills"
            placeholder="Search skills…"
            className="h-9 w-full rounded-md border border-input bg-background/60 pl-8 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
          />
        </label>
        <span className="ml-auto text-xs text-muted-foreground">Installs are account-wide — available in every project.</span>
      </div>

      {/* facet rows */}
      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          value={tier}
          onChange={(v) => setTier(v as TierFilter)}
          options={[
            { value: "all", label: "All" },
            { value: "verified", label: "Verified" },
            { value: "community", label: "Community" },
          ]}
        />
        <Segmented
          value={source}
          onChange={(v) => setSource(v as SourceFilter)}
          options={[
            { value: "all", label: "All sources" },
            { value: "selom", label: "Selom" },
            { value: "clawbio", label: "ClawBio" },
            { value: "bioskills", label: "bioSkills" },
          ]}
        />
        <div className="w-40">
          <Select value={omics} onValueChange={setOmics}>
            <SelectTrigger aria-label="Filter by omics">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All omics</SelectItem>
              {omicsFacets.map((o) => (
                <SelectItem key={o} value={o}>
                  {o}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="w-48">
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger aria-label="Filter by category">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {categories.map((c) => (
                <SelectItem key={c} value={c}>
                  {humanizeCategory(c)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <span className="tabular ml-auto text-xs text-muted-foreground">
          {results.length} shown
        </span>
      </div>

      {/* grid */}
      {results.length === 0 ? (
        <div className="grid place-items-center rounded-xl border border-dashed border-border p-12 text-center">
          <p className="text-sm font-medium text-foreground">No skills match those filters</p>
          <p className="mt-1 text-xs text-muted-foreground">Clear a filter or try another search.</p>
        </div>
      ) : isFiltering ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {results.map((skill) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              installed={installedIds.has(skill.id)}
              onOpen={() => setOpen(skill)}
              onToggleInstall={() => toggleInstall(skill)}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-12">
          {shelves.map((shelf) => (
            <section key={shelf.title}>
              <div className="mb-5 flex items-end justify-between gap-3 border-b border-border pb-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2.5">
                    <span aria-hidden className="size-2.5 rounded-full" style={{ background: shelf.color }} />
                    <h2 className="text-xl font-semibold tracking-tight text-foreground">{shelf.title}</h2>
                  </div>
                  <p className="mt-1.5 text-sm text-muted-foreground">{shelf.subtitle}</p>
                </div>
                <span className="tabular shrink-0 text-xs text-muted-foreground">
                  {shelf.items.length} skill{shelf.items.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {shelf.items.map((skill) => (
                  <SkillCard
                    key={skill.id}
                    skill={skill}
                    installed={installedIds.has(skill.id)}
                    onOpen={() => setOpen(skill)}
                    onToggleInstall={() => toggleInstall(skill)}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      <SkillDetail
        skill={open}
        installed={open ? installedIds.has(open.id) : false}
        onClose={() => setOpen(null)}
        onToggleInstall={() => open && toggleInstall(open)}
      />
    </div>
  );
}

function Segmented({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="inline-flex items-center gap-0.5 rounded-lg bg-muted/60 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
            value === o.value
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
