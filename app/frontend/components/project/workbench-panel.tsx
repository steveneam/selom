"use client";

import * as React from "react";
import Link from "next/link";
import { Boxes, GripVertical, MousePointerClick, Play, Search, Sparkles, X } from "lucide-react";
import { ProposalPlan } from "@/components/intake/proposal-plan";
import { ParamControl } from "./param-control";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/ui/cn";
import { skillColor, skillIcon } from "@/lib/catalog/modality";
import { isFieldDisabled, visibleParamFields } from "@/lib/catalog/params";
import { useSkillParams } from "@/lib/catalog/use-skill-params";
import { getSkill } from "@/lib/catalog/seed";
import { isDataAwareRecommendation, recommendedSkills } from "@/lib/catalog/quick-apply";
import type { DataRouting, SkillParams } from "@/lib/skills/api";
import type { DataFitSummary } from "@/lib/intake/inspect";
import type { Modality } from "@/lib/projects/types";
import type { IntakeProposal, ProposedStep } from "@/lib/intake/mock";

const DND_TYPE = "application/x-selom-skill";

/**
 * The Workbench: installed skills + (when present) the LLM's proposed pipeline.
 *
 * A skill can be applied to the data several ways, all converging on the same run:
 *   - the one-click chips (skills recommended for the loaded data; hidden when there are none),
 *   - press "Apply" on a skill card,
 *   - click a card to SELECT it, tweak its inline params, then Apply,
 *   - DRAG a card into the "Apply a skill" zone.
 * Only Verified skills run now; Community skills are queued for the sandbox.
 */
export function WorkbenchPanel({
  installs,
  proposal,
  route,
  modality,
  running,
  onRun,
  preselect,
  routeComposer,
}: {
  /** The installed-skill rows (workspace-level now) — only the id + skillId are read. */
  installs: { id: string; skillId: string }[];
  proposal: IntakeProposal | null;
  /** The active dataset's persisted data-aware route (Slice 2) — the source of the data-fit
   *  "Recommended for your data" chips for an inspected dataset. */
  route?: { routing: DataRouting | null; dataFit: DataFitSummary | null } | null;
  /** The active dataset's modality — the mock-chip fallback for demo/sample data with no route. */
  modality?: Modality | null;
  running: string | null;
  onRun: (step: ProposedStep) => void;
  /** A skill the command palette / Gene Sets surface asked to select, with optional
   *  param prefills (nonce → re-selectable). */
  preselect?: { id: string; n: number; params?: SkillParams } | null;
  /** Optional AI route composer rendered at the top of the left column (Layer A, Phase 1). */
  routeComposer?: React.ReactNode;
}) {
  const [selected, setSelected] = React.useState<string | null>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const [params, setParams] = React.useState<SkillParams>({});
  // Filter the installed-skills list — installs are account-wide now (spec D1), so a library can
  // hold 100+ skills; a search keeps the column scannable (a dropdown would lose drag-to-apply).
  const [filter, setFilter] = React.useState("");
  // The last preselect nonce whose param prefills we consumed (one-shot per dispatch).
  const appliedPrefill = React.useRef<number>(-1);

  const isVerified = (id: string) => getSkill(id)?.tier === "verified";
  // One-click / quick apply sends no params — the backend fills every default server-side
  // (resolved_params). The selected-skill Apply sends only what the user changed.
  const apply = (skillId: string, p?: SkillParams) =>
    onRun({ skillId, rationale: "", params: p ?? {}, confidence: 0 });

  // Select a skill when the command palette / Gene Sets surface deep-links one in.
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- select a skill when one is deep-linked in
    if (preselect?.id) setSelected(preselect.id);
  }, [preselect]);

  // Initialise inline params when the selected skill changes; if a *fresh* preselect
  // carried prefills for this skill (e.g. a gene-set applied as a volcano highlight),
  // merge them once over the defaults.
  /* eslint-disable react-hooks/set-state-in-effect -- reset/merge inline params when the selected skill or its prefill changes */
  React.useEffect(() => {
    if (!selected) {
      setParams({});
      return;
    }
    // Params hold only what the user changes from the backend defaults (sent on Apply; the
    // controls display each field's default until touched). A fresh preselect (e.g. a gene
    // set applied as a volcano highlight) seeds those values once.
    if (preselect && preselect.id === selected && preselect.params && preselect.n !== appliedPrefill.current) {
      appliedPrefill.current = preselect.n;
      setParams({ ...preselect.params });
    } else {
      setParams({});
    }
  }, [selected, preselect]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const selectedSkill = selected ? getSkill(selected) : undefined;
  const { fields: schema, loading: paramsLoading } = useSkillParams(selected);

  // The "Recommended for your data" chips = the skills the engine RECOMMENDED for this dataset.
  // Data-fit-ranked from the inspected route when present (survives reload — read off the dataset),
  // else the modality mock for demo/sample data; empty → the row hides entirely (never a popularity
  // list under a recommendation's label). Resolved + deduped against the catalog.
  const quick = recommendedSkills(route ?? null, modality ?? null);
  // A3 fix: "Recommended for your data" implies a per-dataset verdict — only true when the real
  // inspect route drove the chips. The modality-mock fallback (demo/sample, or a real dataset whose
  // inspect failed) gets an honest, non-per-dataset heading instead.
  const dataAware = isDataAwareRecommendation(route ?? null);
  // Surface WHY each chip is recommended (Slice 2): the per-skill data-fit verdict for an inspected
  // dataset, looked up by the (normalized) skill id. Drives a tooltip so the data-fit ranking + the
  // fit reason aren't invisible. Undefined for the demo/sample mock path (no inspected fit).
  const fitFor = (catalogId: string) =>
    route?.dataFit?.fits.find((f) => `selom.${f.skill_id}` === catalogId || f.skill_id === catalogId);

  // The installed-skills list, filtered by the search box (name or category).
  const q = filter.trim().toLowerCase();
  const filteredInstalls = q
    ? installs.filter((i) => {
        const s = getSkill(i.skillId);
        return (s?.name ?? i.skillId).toLowerCase().includes(q) || (s?.category ?? "").toLowerCase().includes(q);
      })
    : installs;

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
      <div className="space-y-5">
        {/* Route composer (Layer A, Phase 1) — AI "which analysis?" pre-selector above the
            deterministic quick-apply row. Rendered only when the parent provides it. */}
        {routeComposer}

        {/* Recommended for your data — the engine's proposed skills, one click. Hidden when there's
            no proposal (no popularity fallback — the row only ever shows real recommendations). */}
        {quick.length > 0 && (
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
              <Sparkles className="size-3 text-primary" />{" "}
              {dataAware ? "Recommended for your data" : `Common for ${modality ?? "this data type"}`}
            </p>
            <div className="flex flex-wrap gap-2">
              {quick.map((s) => {
                const Icon = skillIcon(s);
                const color = skillColor(s);
                const busy = running === s.id;
                // Why this chip: the data-fit verdict + reason for an inspected dataset (e.g.
                // "Confident — … . bulk count matrix — fits deg"), else just the skill name.
                const fit = fitFor(s.id);
                const why = fit
                  ? [fit.confidence_label, fit.reason].filter(Boolean).join(" — ")
                  : s.name;
                return (
                  <button
                    key={s.id}
                    draggable
                    title={why}
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
                      ? paramsLoading
                        ? "Loading options…"
                        : schema.length > 0
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
                  {visibleParamFields(schema, params).map((f) => (
                    <ParamControl
                      key={f.key}
                      field={f}
                      value={params[f.key]}
                      disabled={isFieldDisabled(schema, f, params)}
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
            {installs.length > 0 && (
              <span className="tabular ml-1.5 text-muted-foreground/60">{installs.length}</span>
            )}
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
          <>
            {/* Account-wide libraries can be large — a filter keeps the list scannable. */}
            {installs.length > 6 && (
              <label className="relative block">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  aria-label="Filter installed skills"
                  placeholder="Filter skills…"
                  className="h-8 w-full rounded-md border border-input bg-background/60 pl-8 pr-3 text-xs text-foreground outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
                />
              </label>
            )}
            {/* Height-capped + scrollable so the column never runs off the page. */}
            <div className="max-h-[34rem] space-y-2.5 overflow-y-auto pr-0.5">
              {filteredInstalls.length === 0 ? (
                <p className="px-1 py-4 text-center text-xs text-muted-foreground">
                  No installed skills match “{filter}”.
                </p>
              ) : (
                filteredInstalls.map((inst) => {
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
                    <p className="truncate text-sm font-medium text-foreground" title={skill?.name ?? inst.skillId}>{skill?.name ?? inst.skillId}</p>
                    {verified ? <Badge variant="verified">Verified</Badge> : <Badge variant="community">Queued</Badge>}
                  </div>
                  {skill && (
                    <p className="truncate text-[11px] text-muted-foreground" title={skill.category}>{skill.category}</p>
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
          </>
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
      {React.createElement(skillIcon(skill))}
    </span>
  );
}

