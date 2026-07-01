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
import { AskAi } from "@/components/ai/ask-ai";
import { AiMarker } from "@/components/ai/ai-marker";
import { cn } from "@/lib/ui/cn";
import { questionsFor, type IntakeAnswers } from "@/lib/intake/mock";
import {
  candidateFor,
  defaultDesignChoice,
  type DesignChoice,
  type DesignHints,
  type LevelHint,
  type TimeRow,
} from "@/lib/intake/design";
import { designFromIngestActions, type IngestDesignProposal } from "@/lib/ai/proposals";
import type { DataRouting } from "@/lib/skills/api";
import type { AiActionDelta, HelperTurn } from "@/lib/ai/types";
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
  modalityGuessed,
  design,
  routing,
  dataColumns,
  onSubmit,
  onSkip,
}: {
  modality: Modality;
  /** A4 fix: true when `modality` is only the filename heuristic (no successful inspect yet) — the
   *  confirm card says "Guessed from filename" instead of "Detected" so a failed/pending inspect
   *  never reads as a real classification. Defaults to false (detected) for existing callers. */
  modalityGuessed?: boolean;
  design?: DesignHints | null;
  routing?: DataRouting | null;
  /** The dataset's column names — forwarded to the ingest AI refiner so it can map messy sample
   *  names → conditions. Absent → the refiner still runs, with less context. */
  dataColumns?: string[] | null;
  /** On confirm: the answers, the confirmed design, and — when the design came from the AI refiner and
   *  was CONFIRMED UNCHANGED — the `set_design` action delta that attributes the run through the
   *  chokepoint (✨). Absent/empty aiActions → a plain human-attributed run. */
  onSubmit: (answers: IntakeAnswers, choice: DesignChoice | null, aiActions?: AiActionDelta[]) => void;
  onSkip: () => void;
}) {
  const modalityVerb = modalityGuessed ? "Guessed from filename" : "Detected";
  const needsDesign = !!design?.needs_design;
  const [answers, setAnswers] = React.useState<IntakeAnswers>({});

  // The confirmed design — seeded from the engine prefill (best group, control guess as reference).
  const initial = React.useMemo(() => defaultDesignChoice(design), [design]);
  const [groupKey, setGroupKey] = React.useState<string>(initial?.groupKey ?? "");
  const [reference, setReference] = React.useState<string>(initial?.reference ?? "");
  const [treatment, setTreatment] = React.useState<string>(initial?.treatment ?? "");
  // scRNA: the biological-replicate column (followups #6). Seeded from detection; the user can pick the
  // right one when it wasn't detected (else pseudobulk counts cells as replicates, inflating n).
  const [sampleCol, setSampleCol] = React.useState<string>(initial?.sampleCol ?? "");
  // The ingest AI refiner's last proposal (2b): its patch pre-filled the design; kept so a CONFIRMED-
  // UNCHANGED design attributes the run through the chokepoint (✨). Cleared on any dataset change.
  const [aiProposal, setAiProposal] = React.useState<IngestDesignProposal | null>(null);
  // Override a WRONG time-course detection back to a 2-group contrast (fe-review HIGH): the engine may
  // read ordered-looking labels as a time-course when the user actually wants to compare groups.
  const [treatAsCategorical, setTreatAsCategorical] = React.useState(false);
  // Per-timepoint numeric-time corrections (fe-review HIGH): the value the user typed to fix a misparse
  // (e.g. a label the engine mis-scaled). Keyed by level name; drives the order + the synthesized sheet.
  const [timeEdits, setTimeEdits] = React.useState<Record<string, string>>({});

  // Re-seed the contrast when the dataset's design changes (new file / re-inspect / reload
  // re-attach). React-documented "adjust state when a prop changes" — a render-time reset keyed on
  // the prefill identity (memoized on `design`), not a setState-in-effect cascading render.
  const [seed, setSeed] = React.useState(initial);
  if (seed !== initial) {
    setSeed(initial);
    setGroupKey(initial?.groupKey ?? "");
    setReference(initial?.reference ?? "");
    setTreatment(initial?.treatment ?? "");
    setSampleCol(initial?.sampleCol ?? "");
    setAiProposal(null); // a new dataset's design isn't the prior AI proposal
    setTreatAsCategorical(false);
    setTimeEdits({});
  }

  // The ingest AI refiner (2b): map the proposal turn → a design patch (honesty-checked against the
  // detected levels), PRE-FILL the editable contrast, and return a short note. Never applies silently;
  // the user confirms/edits below. Returns null → ask-ai shows its honest "nothing usable" fallback.
  function applyIngestProposal(turn: HelperTurn): string | null {
    const proposed = designFromIngestActions(turn, design ?? null);
    if (!proposed) {
      setAiProposal(null);
      return null;
    }
    const { patch } = proposed;
    if (patch.groupKey && patch.groupKey !== groupKey) pickGroup(patch.groupKey);
    if (patch.reference) setReference(patch.reference);
    if (patch.treatment) setTreatment(patch.treatment);
    setAiProposal(proposed);
    const bits = [
      patch.reference && `control ${patch.reference}`,
      patch.treatment && `treatment ${patch.treatment}`,
    ].filter(Boolean);
    return `✨ Proposed ${bits.join(" · ") || "a design"} — review below, then Confirm & run.`;
  }

  const candidate = candidateFor(design, groupKey);
  // Memoized so it's a stable dependency for the timepoint-ordering useMemo below (candidate is a stable
  // element reference off the `design` prop, so this only changes when the chosen group changes).
  const levels = React.useMemo(() => candidate?.levels ?? [], [candidate]);
  // A time-course design (ordered timepoints) renders a timeline + runs the deg time-course mode — no
  // control/treatment contrast, so the contrast selects, the ≥2-replicate warning, and the messy-name
  // AI refiner (which maps names → a contrast) don't apply. The user can OVERRIDE the detection back to
  // a 2-group contrast (fe-review HIGH) — then it's treated categorically like any other design.
  const detectedTimeCourse = candidate?.kind === "time_course";
  const isTimeCourse = detectedTimeCourse && !treatAsCategorical;

  // The effective numeric time of a timepoint level = the user's correction if valid, else the engine's
  // detected value (fe-review HIGH: a misparsed timepoint can be fixed, and the order follows the number).
  const effTime = React.useCallback(
    (lv: LevelHint): number => {
      const raw = timeEdits[lv.name];
      const n = raw !== undefined && raw.trim() !== "" ? Number(raw) : NaN;
      return Number.isFinite(n) ? n : lv.time ?? 0;
    },
    [timeEdits],
  );
  // Timepoints re-sorted by their effective time — so a corrected value reorders the timeline + baseline.
  const orderedTimeLevels = React.useMemo(
    () => (isTimeCourse ? [...levels].sort((a, b) => effTime(a) - effTime(b)) : levels),
    [isTimeCourse, levels, effTime],
  );
  // Valid only when no two timepoints collapsed onto the same value (the runner needs distinct times).
  const timeCourseValid =
    !isTimeCourse ||
    (() => {
      const ts = levels.map(effTime);
      return ts.every(Number.isFinite) && new Set(ts).size === ts.length;
    })();

  // Switch the group factor → re-default the contrast to that candidate's control guess + next level.
  function pickGroup(key: string) {
    setGroupKey(key);
    const cand = candidateFor(design, key);
    const names = cand?.levels.map((l) => l.name) ?? [];
    const ref = cand?.reference_guess ?? names[0] ?? "";
    setReference(ref);
    setTreatment(names.find((n) => n !== ref) ?? names[1] ?? "");
  }

  // "Reset to detected" (followups #7): restore the engine's prefill after any contrast/sample/design
  // edit — incl. a time-course override or a corrected timepoint.
  const designEdited =
    !!initial &&
    (groupKey !== initial.groupKey ||
      reference !== initial.reference ||
      treatment !== initial.treatment ||
      (sampleCol || "") !== (initial.sampleCol || "") ||
      treatAsCategorical ||
      Object.keys(timeEdits).length > 0);
  function resetToDetected() {
    setGroupKey(initial?.groupKey ?? "");
    setReference(initial?.reference ?? "");
    setTreatment(initial?.treatment ?? "");
    setSampleCol(initial?.sampleCol ?? "");
    setTreatAsCategorical(false);
    setTimeEdits({});
  }

  const analysisName = React.useMemo(() => {
    const sid = routing?.steps?.[0]?.skill_id;
    if (!sid) return null;
    return getSkill(`selom.${sid}`)?.name ?? getSkill(sid)?.name ?? sid;
  }, [routing]);

  // Per-field AI attribution (fe-review MED): the ✨ shows on a contrast field that STILL holds the
  // value the ingest refiner proposed (editing it away drops the marker) — mirrors submit()'s honesty
  // check, so what's marked ✨ is exactly what routes through the chokepoint as AI-attributed.
  const refFromAi = aiProposal?.patch.reference !== undefined && aiProposal?.patch.reference === reference;
  const treatFromAi = aiProposal?.patch.treatment !== undefined && aiProposal?.patch.treatment === treatment;

  const refReps = levels.find((l) => l.name === reference)?.n_replicates;
  const treatReps = levels.find((l) => l.name === treatment)?.n_replicates;
  const lowReps = needsDesign && !isTimeCourse && ((refReps ?? 0) < 2 || (treatReps ?? 0) < 2);
  const designValid =
    !needsDesign ||
    (isTimeCourse
      ? timeCourseValid
      : !!reference && !!treatment && reference !== treatment);

  function submit() {
    // A time-course run carries the (possibly corrected) per-sample times: remap each level's detected
    // time → its effective time, then rewrite the sheet rows by that map so a fixed misparse reproduces.
    let timeRows: TimeRow[] = candidate?.time_rows ?? [];
    if (isTimeCourse && candidate) {
      const remap = new Map<number, number>();
      for (const lv of levels) if (lv.time != null) remap.set(lv.time, effTime(lv));
      timeRows = (candidate.time_rows ?? []).map((r) => ({ ...r, time: remap.get(r.time) ?? r.time }));
    }
    const choice: DesignChoice | null =
      needsDesign && candidate && designValid
        ? {
            groupKey,
            source: design!.source,
            kind: isTimeCourse ? "time_course" : "categorical",
            reference,
            treatment,
            levels: levels.map((l) => l.name),
            sampleCol: sampleCol || null,
            ...(isTimeCourse ? { timeRows } : {}),
          }
        : null;
    // AI attribution (2b): carry the refiner's set_design action ONLY when its proposal was CONFIRMED
    // UNCHANGED — every AI-proposed field still equals the confirmed value. If the user edited any of
    // it, the run is human-attributed (no ✨). Mirrors approvedActions' "staged still equals proposed"
    // honesty check; the server stamps the trusted actor via the chokepoint.
    const p = aiProposal?.patch;
    const aiUnchanged =
      !!p &&
      (p.groupKey === undefined || p.groupKey === groupKey) &&
      (p.reference === undefined || p.reference === reference) &&
      (p.treatment === undefined || p.treatment === treatment);
    const aiActions = aiUnchanged && choice ? [aiProposal!.action] : [];
    onSubmit(answers, choice, aiActions);
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
          <span className="text-[11px] text-muted-foreground/70">· or choose another below</span>
        </div>
      )}

      {/* Design layer — only when the analysis consumes one (deg from counts / pseudobulk). */}
      {needsDesign && candidate && (
        <div className="space-y-3 rounded-xl border border-stage-data/40 bg-[color-mix(in_oklab,var(--stage-data)_6%,transparent)] p-4">
          <div className="flex items-start justify-between gap-2">
            <p className="text-xs font-medium text-foreground">Experimental design</p>
            {designEdited && (
              <button
                type="button"
                onClick={resetToDetected}
                className="text-[11px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
              >
                Reset to detected
              </button>
            )}
          </div>

          {/* Why the engine prefilled this design — the plain-English note + that "control" is a GUESS
              (followups #3). The user confirms against it, not a blank form. */}
          {design!.note && (
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              {design!.note}
              {!isTimeCourse && candidate.reference_guess &&
                ` · “${candidate.reference_guess}” guessed as the control — confirm below`}
            </p>
          )}

          {design!.group_candidates.length > 1 ? (
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
          ) : (
            // Single candidate: show WHICH column the conditions came from, read-only (followups #4).
            <p className="text-[11px] text-muted-foreground">
              Conditions from <span className="font-medium text-foreground">{candidate.label}</span>
            </p>
          )}

          {/* Override a wrong time-course detection (fe-review HIGH). Shown whenever the engine read a
              time-course, so the user can flip it to a 2-group contrast — or back. */}
          {detectedTimeCourse && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-muted-foreground">These conditions are:</span>
              <div
                className="inline-flex rounded-lg border border-border p-0.5"
                role="group"
                aria-label="Design type"
              >
                <button
                  type="button"
                  aria-pressed={isTimeCourse}
                  onClick={() => setTreatAsCategorical(false)}
                  className={cn(
                    "rounded-md px-2 py-1 text-[11px] transition-colors",
                    isTimeCourse
                      ? "bg-primary/15 font-medium text-primary"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  Ordered timepoints
                </button>
                <button
                  type="button"
                  aria-pressed={treatAsCategorical}
                  onClick={() => setTreatAsCategorical(true)}
                  className={cn(
                    "rounded-md px-2 py-1 text-[11px] transition-colors",
                    treatAsCategorical
                      ? "bg-primary/15 font-medium text-primary"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  Groups to compare
                </button>
              </div>
              <span className="text-[11px] text-muted-foreground/70">
                {isTimeCourse ? "— tests a trend across time" : "— runs a 2-group contrast instead"}
              </span>
            </div>
          )}

          {isTimeCourse ? (
            /* Time-course (2c): an ordered timeline, not a 2-group contrast — the run tests a trend
               across time (deg time-course mode), with the earliest timepoint as the baseline. Each
               timepoint's numeric value is EDITABLE (fe-review HIGH): correct a misparse and the order
               + baseline follow the number. */
            <div className="space-y-2">
              <p className="text-[11px] text-muted-foreground">
                Ordered timepoints — genes are tested for a trend across time (baseline = earliest). Edit a
                value to fix a misparse; the order updates.
              </p>
              <ol className="flex flex-wrap items-center gap-1.5" aria-label="Timepoints in order">
                {orderedTimeLevels.map((lv, i) => (
                  <React.Fragment key={lv.name}>
                    {i > 0 && (
                      <span aria-hidden className="text-muted-foreground/50">
                        →
                      </span>
                    )}
                    <li>
                      <TimepointChip
                        name={lv.name}
                        time={effTime(lv)}
                        reps={lv.n_replicates}
                        unit={lv.replicate_unit}
                        isBaseline={i === 0}
                        onCommit={(n) => setTimeEdits((m) => ({ ...m, [lv.name]: String(n) }))}
                      />
                    </li>
                  </React.Fragment>
                ))}
              </ol>
              {!timeCourseValid && (
                <p className="inline-flex items-center gap-1.5 text-[11px] text-warn">
                  <TriangleAlert className="size-3.5" />
                  Two timepoints share the same value — give each a distinct time.
                </p>
              )}
            </div>
          ) : (
            <>
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
                      {role ? (
                        <span className="ml-1.5 rounded border border-primary/40 px-1 py-px text-[9px] uppercase tracking-wide text-primary">
                          {role}
                        </span>
                      ) : (
                        // A level that is neither reference nor treatment is EXCLUDED from this pairwise
                        // contrast (deg compares two groups) — surface it, don't hide it (followups #2).
                        levels.length > 2 && (
                          <span className="ml-1.5 rounded border border-muted-foreground/30 px-1 py-px text-[9px] uppercase tracking-wide text-muted-foreground">
                            not compared
                          </span>
                        )
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
              <div className="flex items-center gap-1.5">
                <Label htmlFor="design-ref">Control / reference</Label>
                {refFromAi && <AiMarker state="staged" size="xs" />}
              </div>
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
              <div className="flex items-center gap-1.5">
                <Label htmlFor="design-treat">Treatment / comparison</Label>
                {treatFromAi && <AiMarker state="staged" size="xs" />}
              </div>
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

          {/* scRNA replicate column (followups #6): pseudobulk aggregates by biological replicate, not
              cells — let the user name it when detection missed it, else n is inflated. */}
          {design!.source === "obs" && (design!.sample_col_candidates?.length ?? 0) > 0 && (
            <div className="space-y-1.5">
              <Label htmlFor="design-sample">Replicate / sample column</Label>
              <Select value={sampleCol} onValueChange={setSampleCol}>
                <SelectTrigger id="design-sample" aria-label="Replicate / sample column">
                  <SelectValue placeholder="Select…" />
                </SelectTrigger>
                <SelectContent>
                  {design!.sample_col_candidates!.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {!sampleCol && (
                <p className="inline-flex items-center gap-1.5 text-[11px] text-warn">
                  <TriangleAlert className="size-3.5" />
                  No sample column detected — pick the one identifying biological replicates, else cells
                  count as replicates (inflated n).
                </p>
              )}
            </div>
          )}

          {/* Layer A 2b — the AI refiner: reads messy free-text sample names → a control/treatment
              contrast, PRE-FILLING the selects above (never silently). The deterministic detection
              already ran; this is the L4 assist for the cases it couldn't parse. */}
          <AskAi
            stage="ingest"
            mode="staged"
            label="Ask AI to read your sample names"
            placeholder="e.g. these are WT vs knockout — set the contrast"
            context={{ dataColumns: dataColumns ?? null }}
            onIngest={applyIngestProposal}
          />
            </>
          )}
        </div>
      )}

      {/* The "ready to run" confirm card — the questionnaire's payoff (build-spec §3 / spec §7.6). */}
      <div className="rounded-xl border border-border bg-card/60 p-3.5">
        <p className="text-xs text-muted-foreground">
          {needsDesign && isTimeCourse ? (
            <>
              {modalityVerb}: <span className="font-medium text-foreground">{modality}</span> ·{" "}
              <span className="font-medium text-foreground">
                time-course across {levels.length} timepoints
              </span>{" "}
              ({levels[0]?.name} → {levels[levels.length - 1]?.name}) — correct?
            </>
          ) : needsDesign && designValid ? (
            <>
              {modalityVerb}: <span className="font-medium text-foreground">{modality}</span> ·{" "}
              <span className="font-medium text-foreground">{levels.length} conditions</span> (
              {treatment} vs {reference}
              {refReps != null && treatReps != null ? ` · n=${treatReps} vs ${refReps}` : ""}) — correct?
            </>
          ) : needsDesign ? (
            <>Pick a control and a treatment to define the contrast.</>
          ) : analysisName ? (
            <>
              {modalityVerb}: <span className="font-medium text-foreground">{modality}</span> — ready to make{" "}
              {analysisName}.
            </>
          ) : (
            // routing didn't resolve a skill (followups #8): don't imply a silent run — point at Skip.
            <>
              {modalityVerb}: <span className="font-medium text-foreground">{modality}</span> — no analysis
              auto-detected. <span className="font-medium text-foreground">Skip</span> below to pick a skill.
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
          <Sparkles className="size-3.5 text-stage-ai/70" />
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

/** One editable timepoint chip in the ordered timeline. The number is the axis value the deg time-course
 *  runner consumes — editing it corrects a misparse (fe-review HIGH). A free-typed draft commits on
 *  blur/Enter (so the timeline doesn't re-sort mid-keystroke) and re-syncs when the effective value
 *  changes externally (a reorder / reset) — the adjust-state-during-render pattern, no effect needed. */
function TimepointChip({
  name,
  time,
  reps,
  unit,
  isBaseline,
  onCommit,
}: {
  name: string;
  time: number;
  reps: number;
  unit: string;
  isBaseline: boolean;
  onCommit: (n: number) => void;
}) {
  const [draft, setDraft] = React.useState(String(time));
  const [seed, setSeed] = React.useState(time);
  if (seed !== time) {
    setSeed(time);
    setDraft(String(time));
  }
  const commit = () => {
    const n = Number(draft);
    if (Number.isFinite(n) && n !== time) onCommit(n);
    else setDraft(String(time));
  };
  return (
    <span className="flex items-center gap-1.5 rounded-lg border border-border bg-card/60 px-2.5 py-1.5">
      <span className="text-sm font-medium text-foreground">{name}</span>
      {isBaseline && (
        <span className="rounded border border-primary/40 px-1 py-px text-[9px] uppercase tracking-wide text-primary">
          baseline
        </span>
      )}
      <input
        value={draft}
        inputMode="decimal"
        aria-label={`${name} timepoint value`}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
        className="tabular h-6 w-14 rounded border border-input bg-background/60 px-1.5 text-center text-xs text-foreground outline-none focus-visible:border-ring/60 focus-visible:ring-1 focus-visible:ring-ring/30"
      />
      <span className="tabular text-[11px] text-muted-foreground">
        {reps} {unit}
      </span>
    </span>
  );
}
