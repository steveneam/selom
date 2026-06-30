"use client";

import * as React from "react";
import { ChevronDown, FlaskConical, Play, Sparkles, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getSkill } from "@/lib/catalog/seed";
import { questionsFor, type IntakeAnswers } from "@/lib/intake/mock";
import {
  candidateFor,
  defaultDesignChoice,
  type DesignChoice,
  type DesignHints,
} from "@/lib/intake/design";
import type { DataRouting } from "@/lib/skills/api";
import type { Modality } from "@/lib/projects/types";

/**
 * The intake confirm-card (intake-questionnaire build-spec, Layer A ingest). The engine pre-fills
 * the data's modality, intended analysis, and experimental DESIGN deterministically (no AI); the
 * user CONFIRMS — it is a confirm-the-detection card, not a blank form (the SpatialGE negative
 * template). The free-text "context for the AI" is demoted to an optional fold. On confirm it hands
 * up the answers + the confirmed {@link DesignChoice}, which the parent injects into the `deg` run
 * params (build-spec §3b). Deterministic-path-primary: complete + correct with the gateway off.
 */
export function IntakeQuestionnaire({
  modality,
  design,
  routing,
  onSubmit,
  onSkip,
}: {
  modality: Modality;
  design?: DesignHints | null;
  routing?: DataRouting | null;
  onSubmit: (answers: IntakeAnswers, choice: DesignChoice | null) => void;
  onSkip: () => void;
}) {
  const needsDesign = !!design?.needs_design;
  const [answers, setAnswers] = React.useState<IntakeAnswers>({});

  // The confirmed design — seeded from the engine prefill (best group, control guess as reference).
  const initial = React.useMemo(() => defaultDesignChoice(design), [design]);
  const [groupKey, setGroupKey] = React.useState<string>(initial?.groupKey ?? "");
  const [reference, setReference] = React.useState<string>(initial?.reference ?? "");
  const [treatment, setTreatment] = React.useState<string>(initial?.treatment ?? "");

  // Re-seed the contrast when the dataset's design changes (new file / re-inspect / reload
  // re-attach). React-documented "adjust state when a prop changes" — a render-time reset keyed on
  // the prefill identity (memoized on `design`), not a setState-in-effect cascading render.
  const [seed, setSeed] = React.useState(initial);
  if (seed !== initial) {
    setSeed(initial);
    setGroupKey(initial?.groupKey ?? "");
    setReference(initial?.reference ?? "");
    setTreatment(initial?.treatment ?? "");
  }

  const candidate = candidateFor(design, groupKey);
  const levels = candidate?.levels ?? [];

  // Switch the group factor → re-default the contrast to that candidate's control guess + next level.
  function pickGroup(key: string) {
    setGroupKey(key);
    const cand = candidateFor(design, key);
    const names = cand?.levels.map((l) => l.name) ?? [];
    const ref = cand?.reference_guess ?? names[0] ?? "";
    setReference(ref);
    setTreatment(names.find((n) => n !== ref) ?? names[1] ?? "");
  }

  const analysisName = React.useMemo(() => {
    const sid = routing?.steps?.[0]?.skill_id;
    if (!sid) return null;
    return getSkill(`selom.${sid}`)?.name ?? getSkill(sid)?.name ?? sid;
  }, [routing]);

  const refReps = levels.find((l) => l.name === reference)?.n_replicates;
  const treatReps = levels.find((l) => l.name === treatment)?.n_replicates;
  const lowReps = needsDesign && ((refReps ?? 0) < 2 || (treatReps ?? 0) < 2);
  const designValid = !needsDesign || (!!reference && !!treatment && reference !== treatment);

  function submit() {
    const choice: DesignChoice | null =
      needsDesign && candidate && designValid
        ? {
            groupKey,
            source: design!.source,
            reference,
            treatment,
            levels: levels.map((l) => l.name),
            sampleCol: design!.sample_col ?? null,
          }
        : null;
    onSubmit(answers, choice);
  }

  function setAnswer(id: string, v: string) {
    setAnswers((a) => ({ ...a, [id]: v }));
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <FlaskConical className="size-4 text-primary" />
        <p className="text-sm font-medium text-foreground">Confirm your analysis</p>
        <span className="tabular rounded border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
          {modality}
        </span>
      </div>
      <p className="-mt-1 text-xs text-muted-foreground">
        Selom detected what your data is and how it&apos;s set up — confirm or correct it below, then run.
      </p>

      {/* "You want to make ___" — pre-selected from the data-aware route (read-only confirm). */}
      {analysisName && (
        <div className="flex items-baseline gap-2 text-sm">
          <span className="text-muted-foreground">You want to make:</span>
          <span className="font-medium text-foreground">{analysisName}</span>
          <span className="text-[11px] text-muted-foreground/70">· or pick another from the chips →</span>
        </div>
      )}

      {/* Design layer — only when the analysis consumes one (deg from counts / pseudobulk). */}
      {needsDesign && candidate && (
        <div className="space-y-3 rounded-xl border border-stage-data/40 bg-[color-mix(in_oklab,var(--stage-data)_6%,transparent)] p-4">
          <p className="text-xs font-medium text-foreground">Experimental design</p>

          {design!.group_candidates.length > 1 && (
            <div className="space-y-1.5">
              <Label htmlFor="design-group">Group / condition column</Label>
              <Select value={groupKey} onValueChange={pickGroup}>
                <SelectTrigger id="design-group" aria-label="Group / condition column">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {design!.group_candidates.map((c) => (
                    <SelectItem key={c.key} value={c.key}>
                      {c.label} ({c.n_levels})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Layer 2 — the detected conditions + replicate counts (confirm the detection). */}
          <div className="grid gap-2 sm:grid-cols-2">
            {levels.map((lv) => {
              const low = lv.n_replicates < 2;
              const role = lv.name === reference ? "reference" : lv.name === treatment ? "treatment" : null;
              return (
                <div
                  key={lv.name}
                  className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card/60 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground" title={lv.name}>
                      {lv.name}
                      {role && (
                        <span className="ml-1.5 rounded border border-primary/40 px-1 py-px text-[9px] uppercase tracking-wide text-primary">
                          {role}
                        </span>
                      )}
                    </p>
                    <p className={`tabular text-[11px] ${low ? "text-warn" : "text-muted-foreground"}`}>
                      {lv.n_replicates} {lv.replicate_unit}
                      {low && " — DE needs ≥2"}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* The contrast direction — logFC is treatment vs reference. */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="design-ref">Control / reference</Label>
              <Select value={reference} onValueChange={setReference}>
                <SelectTrigger id="design-ref" aria-label="Control / reference">
                  <SelectValue placeholder="Select…" />
                </SelectTrigger>
                <SelectContent>
                  {levels.map((l) => (
                    <SelectItem key={l.name} value={l.name} disabled={l.name === treatment}>
                      {l.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="design-treat">Treatment / comparison</Label>
              <Select value={treatment} onValueChange={setTreatment}>
                <SelectTrigger id="design-treat" aria-label="Treatment / comparison">
                  <SelectValue placeholder="Select…" />
                </SelectTrigger>
                <SelectContent>
                  {levels.map((l) => (
                    <SelectItem key={l.name} value={l.name} disabled={l.name === reference}>
                      {l.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      )}

      {/* The "ready to run" confirm card — the questionnaire's payoff (build-spec §3 / spec §7.6). */}
      <div className="rounded-xl border border-border bg-card/60 p-3.5">
        <p className="text-xs text-muted-foreground">
          {needsDesign && designValid ? (
            <>
              Detected: <span className="font-medium text-foreground">{modality}</span> ·{" "}
              <span className="font-medium text-foreground">{levels.length} conditions</span> (
              {treatment} vs {reference}
              {refReps != null && treatReps != null ? ` · n=${treatReps} vs ${refReps}` : ""}) — correct?
            </>
          ) : needsDesign ? (
            <>Pick a control and a treatment to define the contrast.</>
          ) : (
            <>
              Detected: <span className="font-medium text-foreground">{modality}</span> — ready to
              {analysisName ? ` make ${analysisName}.` : " analyze."}
            </>
          )}
        </p>
        {lowReps && designValid && (
          <p className="mt-1.5 inline-flex items-center gap-1.5 text-[11px] text-warn">
            <TriangleAlert className="size-3.5" />
            A condition has &lt;2 replicates — DE results will be unreliable.
          </p>
        )}
        <div className="mt-3 flex items-center gap-2">
          <Button type="button" size="sm" onClick={submit} disabled={!designValid}>
            <Play /> Confirm &amp; run
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onSkip}>
            Skip — I&apos;ll pick skills
          </Button>
        </div>
      </div>

      {/* Free-text context — demoted to an optional fold (it still feeds the AI proposal). */}
      <details className="group rounded-xl border border-border/70">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-3.5 py-2.5 text-xs font-medium text-muted-foreground hover:text-foreground">
          <Sparkles className="size-3.5 text-primary/70" />
          Add context for the AI (optional)
          <ChevronDown className="ml-auto size-3.5 transition-transform group-open:rotate-180" />
        </summary>
        <div className="grid gap-4 border-t border-border/60 p-3.5 sm:grid-cols-2">
          {questionsFor(modality).map((q) => (
            <div key={q.id} className={q.type === "textarea" ? "space-y-1.5 sm:col-span-2" : "space-y-1.5"}>
              <Label htmlFor={q.id}>{q.label}</Label>
              {q.type === "select" ? (
                <Select value={answers[q.id] ?? ""} onValueChange={(v) => setAnswer(q.id, v)}>
                  <SelectTrigger id={q.id} aria-label={q.label}>
                    <SelectValue placeholder="Select…" />
                  </SelectTrigger>
                  <SelectContent>
                    {(q.options ?? []).map((o) => (
                      <SelectItem key={o} value={o}>
                        {o}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : q.type === "textarea" ? (
                <textarea
                  id={q.id}
                  value={answers[q.id] ?? ""}
                  onChange={(e) => setAnswer(q.id, e.target.value)}
                  placeholder={q.placeholder}
                  rows={2}
                  className="w-full resize-y rounded-md border border-input bg-background/60 px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground/60 focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
                />
              ) : (
                <Input
                  id={q.id}
                  value={answers[q.id] ?? ""}
                  onChange={(e) => setAnswer(q.id, e.target.value)}
                  placeholder={q.placeholder}
                />
              )}
              {q.helper && <p className="text-[11px] text-muted-foreground">{q.helper}</p>}
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
