"use client";

import * as React from "react";
import Link from "next/link";
import { Boxes, GripVertical, MousePointerClick, Play, Sparkles, X } from "lucide-react";
import { ProposalPlan } from "@/components/intake/proposal-plan";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { skillColor, skillIcon } from "@/lib/catalog/modality";
import { defaultParams, skillParamSchema, type ParamField } from "@/lib/catalog/params";
import { getSkill } from "@/lib/catalog/seed";
import type { SkillParams } from "@/lib/skills-api";
import type { IntakeProposal, ProposedStep } from "@/lib/intake/mock";
import type { SkillInstall } from "@/lib/projects/types";

const DND_TYPE = "application/x-selom-skill";

/**
 * The Workbench: installed skills + (when present) the LLM's proposed pipeline.
 *
 * A skill can be applied to the data several ways, all converging on the same run:
 *   - the Quick apply row (most-used skills, one click),
 *   - press "Apply" on a skill card,
 *   - click a card to SELECT it, tweak its inline params, then Apply,
 *   - DRAG a card into the "Apply a skill" zone.
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
  const [params, setParams] = React.useState<SkillParams>({});

  const isVerified = (id: string) => getSkill(id)?.tier === "verified";
  const apply = (skillId: string, p?: SkillParams) =>
    onRun({ skillId, rationale: "", params: p ?? defaultParams(skillId), confidence: 0 });

  // Reset the inline params whenever the selected skill changes.
  React.useEffect(() => {
    setParams(selected ? defaultParams(selected) : {});
  }, [selected]);

  const selectedSkill = selected ? getSkill(selected) : undefined;
  const schema = selected ? skillParamSchema(selected) : [];

  // Quick apply = the most popular Verified installed skills (one-click favourites).
  const quick = installs
    .map((i) => getSkill(i.skillId))
    .filter((s): s is NonNullable<typeof s> => !!s && s.tier === "verified")
    .sort((a, b) => b.popularity - a.popularity)
    .slice(0, 4);

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
      <div className="space-y-5">
        {/* Quick apply — one-click favourites. */}
        {quick.length > 0 && (
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
              <Sparkles className="size-3 text-primary" /> Quick apply
            </p>
            <div className="flex flex-wrap gap-2">
              {quick.map((s) => {
                const Icon = skillIcon(s);
                const color = skillColor(s);
                const busy = running === s.id;
                return (
                  <button
                    key={s.id}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData(DND_TYPE, s.id);
                      e.dataTransfer.setData("text/plain", s.id);
                      e.dataTransfer.effectAllowed = "copy";
                    }}
                    onClick={() => apply(s.id)}
                    disabled={busy}
                    className="inline-flex cursor-grab items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:border-primary/40 hover:bg-card/80 active:cursor-grabbing disabled:opacity-60"
                  >
                    <span aria-hidden style={{ color }} className="[&_svg]:size-3.5">
                      <Icon />
                    </span>
                    {busy ? "Running…" : s.name}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Apply-a-skill hub — drop target + the selected skill, its params, and Apply. */}
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
            setSelected(id);
          }}
          className={cn(
            "rounded-xl border border-dashed p-6 transition-colors",
            dragOver ? "border-primary bg-accent/30" : "border-input bg-card/40",
          )}
        >
          {selectedSkill ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <SkillTile skillId={selectedSkill.id} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-foreground">{selectedSkill.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {isVerified(selectedSkill.id)
                      ? schema.length > 0
                        ? "Tune the options, then apply to your data."
                        : "Runs with smart defaults — ready to apply."
                      : "Community skill — runs in a future sandbox."}
                  </p>
                </div>
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

              {schema.length > 0 && (
                <div className="grid gap-3 rounded-lg border border-border bg-background/40 p-4 sm:grid-cols-2">
                  {schema.map((f) => (
                    <ParamControl
                      key={f.key}
                      field={f}
                      value={params[f.key]}
                      onChange={(v) => setParams((p) => ({ ...p, [f.key]: v }))}
                    />
                  ))}
                </div>
              )}

              <Button
                disabled={!isVerified(selectedSkill.id) || running === selectedSkill.id}
                onClick={() => apply(selectedSkill.id, params)}
              >
                <Play /> {running === selectedSkill.id ? "Running…" : "Apply skill"}
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

/** One inline parameter control (range / number / text / switch). */
function ParamControl({
  field,
  value,
  onChange,
}: {
  field: ParamField;
  value: SkillParams[string] | undefined;
  onChange: (v: SkillParams[string]) => void;
}) {
  const v = value ?? field.default;

  if (field.type === "switch") {
    const on = Boolean(v);
    return (
      <label className="flex items-center justify-between gap-3 sm:col-span-2">
        <span>
          <span className="block text-xs font-medium text-foreground">{field.label}</span>
          {field.help && <span className="block text-[11px] text-muted-foreground">{field.help}</span>}
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          onClick={() => onChange(!on)}
          className={cn(
            "relative h-5 w-9 shrink-0 rounded-full transition-colors",
            on ? "bg-primary" : "bg-input",
          )}
        >
          <span
            className={cn(
              "absolute top-0.5 size-4 rounded-full bg-white transition-transform",
              on ? "translate-x-4" : "translate-x-0.5",
            )}
          />
        </button>
      </label>
    );
  }

  if (field.type === "range") {
    return (
      <label className="block sm:col-span-2">
        <span className="flex items-center justify-between">
          <span className="text-xs font-medium text-foreground">{field.label}</span>
          <span className="tabular text-xs text-primary">{Number(v).toFixed(1)}</span>
        </span>
        <input
          type="range"
          min={field.min}
          max={field.max}
          step={field.step}
          value={Number(v)}
          onChange={(e) => onChange(Number(e.target.value))}
          className="mt-1.5 w-full accent-[var(--primary)]"
        />
        {field.help && <span className="mt-1 block text-[11px] text-muted-foreground">{field.help}</span>}
      </label>
    );
  }

  return (
    <label className="block">
      <span className="text-xs font-medium text-foreground">{field.label}</span>
      <input
        type={field.type === "number" ? "number" : "text"}
        value={String(v)}
        min={field.min}
        max={field.max}
        step={field.step}
        placeholder={field.placeholder}
        onChange={(e) => onChange(field.type === "number" ? Number(e.target.value) : e.target.value)}
        className="mt-1 h-9 w-full rounded-md border border-input bg-background/60 px-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground/60 focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
      />
      {field.help && <span className="mt-1 block text-[11px] text-muted-foreground">{field.help}</span>}
    </label>
  );
}
