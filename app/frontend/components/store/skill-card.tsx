"use client";

import { createElement } from "react";
import { Check, Download, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { humanizeCategory, modalityColor, skillColor, skillIcon } from "@/lib/catalog/modality";
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
  const color = skillColor(skill);

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
        "group relative flex cursor-pointer flex-col gap-3 p-5 transition-colors hover:border-primary/40 hover:bg-card/80",
        "focus-visible:outline-none focus-visible:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring/40",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className="grid size-10 shrink-0 place-items-center rounded-xl border [&_svg]:size-5"
          style={{
            borderColor: `color-mix(in oklab, ${color} 45%, transparent)`,
            background: `color-mix(in oklab, ${color} 12%, var(--card))`,
            color,
          }}
        >
          {createElement(skillIcon(skill))}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="min-w-0 truncate text-sm font-semibold text-foreground">{skill.name}</h3>
              {/* App-Store-style category tag — what kind of analysis this is. */}
              <span
                className="mt-1 inline-block max-w-full truncate rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{
                  background: `color-mix(in oklab, ${color} 14%, transparent)`,
                  color: `color-mix(in oklab, ${color} 78%, var(--foreground))`,
                }}
              >
                {humanizeCategory(skill.category)}
              </span>
            </div>
            <Badge variant={verified ? "verified" : "community"}>{verified ? "Verified" : "Community"}</Badge>
          </div>
        </div>
      </div>

      <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">{skill.summary}</p>

      {/* Bottom chips = the DATA the skill runs on: source + omics modalities. */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
          <span aria-hidden className="size-1.5 rounded-full" style={{ backgroundColor: src.dot }} />
          {src.label}
        </span>
        {skill.omics.slice(0, 2).map((o) => {
          const oc = modalityColor(o);
          return (
            <span
              key={o}
              className="rounded-md border px-1.5 py-px text-[10px] font-medium"
              style={{
                borderColor: `color-mix(in oklab, ${oc} 35%, transparent)`,
                background: `color-mix(in oklab, ${oc} 8%, transparent)`,
                color: `color-mix(in oklab, ${oc} 72%, var(--foreground))`,
              }}
            >
              {o}
            </span>
          );
        })}
      </div>

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
