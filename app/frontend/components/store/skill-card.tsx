"use client";

import { Check, Download, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import type { SkillCatalogEntry, SkillSource } from "@/lib/catalog/types";

const SOURCE_META: Record<SkillSource, { label: string; dot: string }> = {
  selom: { label: "Selom", dot: "#22d3ee" },
  clawbio: { label: "ClawBio", dot: "#a78bfa" },
  bioskills: { label: "bioSkills", dot: "#fb923c" },
};

export function SkillCard({
  skill,
  installed,
  onOpen,
  onToggleInstall,
}: {
  skill: SkillCatalogEntry;
  installed: boolean;
  onOpen: () => void;
  onToggleInstall: () => void;
}) {
  const src = SOURCE_META[skill.source];
  const verified = skill.tier === "verified";

  return (
    <Card
      role="button"
      tabIndex={0}
      aria-label={`${skill.name} — view details`}
      onClick={onOpen}
      onKeyDown={(e) => {
        // Only the card itself opens details — let the inner Install button
        // handle its own keys without also firing this.
        if (e.target !== e.currentTarget) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      className={cn(
        "group relative flex cursor-pointer flex-col gap-3 p-4 transition-colors hover:border-primary/40 hover:bg-card/80",
        "focus-visible:outline-none focus-visible:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring/40",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 truncate text-sm font-semibold text-foreground">{skill.name}</h3>
        <Badge variant={verified ? "verified" : "community"}>{verified ? "Verified" : "Community"}</Badge>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
          <span aria-hidden className="size-1.5 rounded-full" style={{ backgroundColor: src.dot }} />
          {src.label}
        </span>
        {skill.omics.slice(0, 2).map((o) => (
          <span
            key={o}
            className="rounded border border-border px-1.5 py-px text-[10px] text-muted-foreground"
          >
            {o}
          </span>
        ))}
      </div>

      <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">{skill.summary}</p>

      <div className="mt-auto flex items-center justify-between gap-2 pt-1">
        <span className="tabular truncate text-[10px] text-muted-foreground">
          {skill.inputFormats.join(" · ")}
        </span>
        <Button
          size="sm"
          variant={installed ? "secondary" : verified ? "default" : "outline"}
          onClick={(e) => {
            e.stopPropagation();
            onToggleInstall();
          }}
          className="h-7 px-2.5 text-xs"
        >
          {installed ? (
            <>
              <Check /> Installed
            </>
          ) : verified ? (
            <>
              <Download /> Install
            </>
          ) : (
            <>
              <Plus /> Queue
            </>
          )}
        </Button>
      </div>
    </Card>
  );
}
