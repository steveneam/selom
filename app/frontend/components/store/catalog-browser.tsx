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
import { cn } from "@/lib/cn";
import { CATALOG, CATEGORIES, OMICS } from "@/lib/catalog/seed";
import type { SkillCatalogEntry, SkillSource, SkillTier } from "@/lib/catalog/types";
import { projectStore, select, useProjects } from "@/lib/projects/store";

type TierFilter = "all" | SkillTier;
type SourceFilter = "all" | SkillSource;

export function CatalogBrowser() {
  const state = useProjects();
  const { projects } = state;

  const [query, setQuery] = React.useState("");
  const [tier, setTier] = React.useState<TierFilter>("all");
  const [source, setSource] = React.useState<SourceFilter>("all");
  const [omics, setOmics] = React.useState<string>("all");
  const [category, setCategory] = React.useState<string>("all");
  const [open, setOpen] = React.useState<SkillCatalogEntry | null>(null);
  const [targetId, setTargetId] = React.useState<string | undefined>(undefined);

  const target = targetId ?? projects[0]?.id;
  const targetProject = projects.find((p) => p.id === target);
  const installedIds = React.useMemo(
    () => new Set(target ? select.installedIds(state, target) : []),
    [state, target],
  );

  const results = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return CATALOG.filter((s) => {
      if (tier !== "all" && s.tier !== tier) return false;
      if (source !== "all" && s.source !== source) return false;
      if (omics !== "all" && !s.omics.includes(omics)) return false;
      if (category !== "all" && s.category !== category) return false;
      if (q && !(`${s.name} ${s.summary} ${s.category}`.toLowerCase().includes(q))) return false;
      return true;
    }).sort((a, b) => b.popularity - a.popularity);
  }, [query, tier, source, omics, category]);

  function toggleInstall(skill: SkillCatalogEntry) {
    let projectId = target;
    if (!projectId) {
      const p = projectStore.createProject("Untitled project");
      projectId = p.id;
      setTargetId(p.id);
    }
    if (installedIds.has(skill.id)) projectStore.uninstallSkill(projectId, skill.id);
    else projectStore.installSkill(projectId, skill.id);
  }

  return (
    <div className="space-y-4">
      {/* target project + search */}
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

        <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
          <span>Installing into</span>
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
              {OMICS.map((o) => (
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
              {CATEGORIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
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
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
      )}

      <SkillDetail
        skill={open}
        installed={open ? installedIds.has(open.id) : false}
        targetProjectName={targetProject?.name}
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
