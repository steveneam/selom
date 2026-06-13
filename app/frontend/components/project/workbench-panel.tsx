"use client";

import * as React from "react";
import Link from "next/link";
import { Boxes, GripVertical, MousePointerClick, Play, X } from "lucide-react";
import { ProposalPlan } from "@/components/intake/proposal-plan";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { skillColor, skillIcon } from "@/lib/catalog/modality";
import { getSkill } from "@/lib/catalog/seed";
import type { IntakeProposal, ProposedStep } from "@/lib/intake/mock";
import type { SkillInstall } from "@/lib/projects/types";

const DND_TYPE = "application/x-selom-skill";

/**
 * The Workbench: installed skills + (when present) the LLM's proposed pipeline.
 *
 * A skill can be applied to the data three ways, all converging on the same run:
 *   1. press "Apply" on the skill card,
 *   2. click a card to SELECT it, then press Apply in the drop zone,
 *   3. DRAG a card into the "Apply a skill" zone.
 * Only Verified skills run now; Community skills are queued for the sandbox.
 */
export function WorkbenchPanel({
  installs,
  proposal,
  running,
  onRun,
}: {
  installs: SkillInstall[];
  proposal: IntakeProposal | null;
  running: string | null;
  onRun: (step: ProposedStep) => void;
}) {
  const [selected, setSelected] = React.useState<string | null>(null);
  const [dragOver, setDragOver] = React.useState(false);

  const isVerified = (id: string) => getSkill(id)?.tier === "verified";
  const apply = (skillId: string) => onRun({ skillId, rationale: "", params: {}, confidence: 0 });
  const selectedSkill = selected ? getSkill(selected) : undefined;

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
      <div className="space-y-5">
        {/* Apply-a-skill hub — drop target + the selected skill + Apply. */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const id = e.dataTransfer.getData(DND_TYPE) || e.dataTransfer.getData("text/plain");
            if (!id) return;
            if (isVerified(id)) apply(id);
            else setSelected(id);
          }}
          className={cn(
            "rounded-xl border border-dashed p-6 transition-colors",
            dragOver ? "border-primary bg-accent/30" : "border-input bg-card/40",
          )}
        >
          {selectedSkill ? (
            <div className="flex flex-wrap items-center gap-3">
              <SkillTile skillId={selectedSkill.id} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-foreground">{selectedSkill.name}</p>
                <p className="text-xs text-muted-foreground">
                  {isVerified(selectedSkill.id)
                    ? "Ready to apply to your data."
                    : "Community skill — runs in a future sandbox."}
                </p>
              </div>
              <Button
                size="sm"
                disabled={!isVerified(selectedSkill.id) || running === selectedSkill.id}
                onClick={() => apply(selectedSkill.id)}
              >
                <Play /> {running === selectedSkill.id ? "Running…" : "Apply skill"}
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="size-8 text-muted-foreground"
                aria-label="Clear selection"
                onClick={() => setSelected(null)}
              >
                <X />
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2 py-3 text-center">
              <span className="grid size-11 place-items-center rounded-xl border border-border bg-background/60 text-primary [&_svg]:size-5">
                <MousePointerClick />
              </span>
              <p className="text-sm font-semibold text-foreground">Apply a skill to your data</p>
              <p className="max-w-sm text-xs text-muted-foreground">
                Drag a skill here, click one to select it, or press{" "}
                <span className="text-foreground">Apply</span> on any installed skill.
              </p>
            </div>
          )}
        </div>

        {/* proposal (or guidance to get one) */}
        <Card className="p-5">
          {proposal ? (
            <ProposalPlan proposal={proposal} running={running} onRun={onRun} />
          ) : (
            <div className="grid place-items-center py-10 text-center">
              <div className="max-w-sm space-y-1.5">
                <p className="text-sm font-medium text-foreground">No proposed pipeline yet</p>
                <p className="text-xs text-muted-foreground">
                  Drop a dataset in the <span className="text-foreground">Data</span> tab and answer a few
                  questions, or apply one of your installed skills directly.
                </p>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* installed skills */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Installed skills
          </p>
          <Link href="/store" className="text-[11px] font-medium text-primary hover:underline">
            + Store
          </Link>
        </div>
        {installs.length === 0 ? (
          <Card className="grid place-items-center gap-2 p-6 text-center">
            <Boxes className="size-5 text-muted-foreground" />
            <p className="text-xs text-muted-foreground">No skills installed. Add some from the Skill Store.</p>
            <Button asChild variant="outline" size="sm" className="mt-1">
              <Link href="/store">Browse Store</Link>
            </Button>
          </Card>
        ) : (
          installs.map((inst) => {
            const skill = getSkill(inst.skillId);
            const busy = running === inst.skillId;
            const verified = skill?.tier === "verified";
            const isSel = selected === inst.skillId;
            return (
              <Card
                key={inst.id}
                draggable={verified}
                onDragStart={(e) => {
                  e.dataTransfer.setData(DND_TYPE, inst.skillId);
                  e.dataTransfer.setData("text/plain", inst.skillId);
                  e.dataTransfer.effectAllowed = "copy";
                }}
                onClick={() => setSelected(isSel ? null : inst.skillId)}
                className={cn(
                  "flex items-center gap-2 p-3 transition-colors",
                  verified ? "cursor-grab active:cursor-grabbing hover:border-primary/40 hover:bg-card/80" : "opacity-90",
                  isSel && "border-primary/60 bg-accent/30 ring-1 ring-ring/40",
                )}
              >
                {verified && <GripVertical className="size-4 shrink-0 text-muted-foreground/60" aria-hidden />}
                <SkillTile skillId={inst.skillId} small />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <p className="truncate text-sm font-medium text-foreground">{skill?.name ?? inst.skillId}</p>
                    {verified ? <Badge variant="verified">Verified</Badge> : <Badge variant="community">Queued</Badge>}
                  </div>
                  {skill && (
                    <p className="truncate text-[11px] text-muted-foreground">{skill.category}</p>
                  )}
                </div>
                <Button
                  size="sm"
                  variant={verified ? "default" : "secondary"}
                  className="h-7 shrink-0 px-2.5 text-xs"
                  disabled={busy || !verified}
                  title={verified ? "Apply skill to your data" : "Community skill — runs in a future sandbox"}
                  onClick={(e) => {
                    e.stopPropagation();
                    apply(inst.skillId);
                  }}
                >
                  <Play /> {busy ? "Running…" : "Apply"}
                </Button>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
}

/** Modality-coloured icon tile for a skill (matches the Skill Store identity). */
function SkillTile({ skillId, small }: { skillId: string; small?: boolean }) {
  const skill = getSkill(skillId);
  if (!skill) return null;
  const color = skillColor(skill);
  const Icon = skillIcon(skill);
  return (
    <span
      aria-hidden
      className={cn(
        "grid shrink-0 place-items-center rounded-lg border",
        small ? "size-8 [&_svg]:size-4" : "size-10 [&_svg]:size-5",
      )}
      style={{
        borderColor: `color-mix(in oklab, ${color} 45%, transparent)`,
        background: `color-mix(in oklab, ${color} 12%, var(--card))`,
        color,
      }}
    >
      <Icon />
    </span>
  );
}
