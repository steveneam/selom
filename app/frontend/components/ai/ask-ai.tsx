"use client";

import * as React from "react";
import { Sparkles, CornerDownLeft, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/ui/cn";
import { proposeActions } from "@/lib/ai/api";
import { proposalsFromTurn, selectedSkillFromTurn } from "@/lib/ai/proposals";
import { ExplainSourceBadge } from "@/components/ai/explain-source-badge";
import type { AiProposal, ExplainResponse, HelperTurn } from "@/lib/ai/types";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { SkillParams } from "@/lib/skills/api";

/** Stages in the engine spine that Layer A (AI Assist) owns. `methods` is the publish-stage
 *  methods-draft entry point (pillar-2 may later split a formal Methods & Legend stage; the
 *  `draft` composer moves there unchanged). It is a label only — `draft` mode delegates the wire
 *  call to the caller's `onExplain`, so no stage string crosses the `/ai/propose` boundary. */
export type AiStage = "route" | "ingest" | "analyze" | "grade" | "output" | "methods";

/**
 * Apply-discipline per stage (the spine of every AI entry point).
 *   staged   — pending queue, one explicit re-run (analyze, ingest) — ✅ wired in Phase 0
 *   live     — immediate JSON-Patch, undoable; cosmetic (output) — later phase
 *   advisory — propose-only, never auto-applied (grade) — later phase
 *   select   — pre-selects in picker; user confirms + runs (route) — later phase
 *   draft    — AI-marked, fully editable prose (methods) — later phase
 */
export type AiMode = "staged" | "live" | "advisory" | "select" | "draft";

/** The result of a one-click Auto-tune (deterministic best-practice defaults; no AI). */
export interface AutoTuneOutcome {
  ok: boolean;
  /** A short summary to show below the composer — the reviewable diff / honest note. */
  note: string;
}

/** Context bundle forwarded to the gateway (mirrors backend ProposeRequest fields). */
export interface AiContext {
  skillId?: string | null;
  params?: SkillParams;
  figureSpec?: FigureSpec | null;
  capabilitySurface?: Record<string, unknown> | null;
  // Slice 2 — data-aware routing (mode="select"). The data DESCRIPTION (columns + engine kind +
  // numeric-col count); the server derives the fit verdict itself. Null when no dataset is inspected.
  dataColumns?: string[] | null;
  dataKind?: string | null;
  dataNumericCols?: number | null;
}

/**
 * The reusable stage-parameterized "Ask AI" composer (Phase 0 — Layer A, FE Experience Spine).
 *
 * One entry point per engine-spine stage, governed by the apply-discipline contract
 * (`docs/ai-cross-stage-entry-points/spec.md`). Phase 0 wires only the `staged` mode
 * (the existing analyze composer, unchanged in behaviour); every other mode is declared
 * in the type union but NOT implemented yet — each ships with its own phase.
 *
 * Degrades clean: with the gateway off (the default) `/ai/propose` returns an empty plan,
 * so this shows a quiet "gateway off" note and changes nothing — the deterministic editor
 * is entirely unaffected. Live proposal text awaits `SELOM_AI_GATEWAY=live` + `ANTHROPIC_API_KEY`.
 */
export function AskAi({
  stage,
  label,
  placeholder,
  mode,
  context,
  disabled,
  hint,
  onStaged,
  onSelect,
  onIngest,
  onExplain,
  onDraftResult,
  onAutoTune,
  autoTuneLabel,
  autoTuneHint,
  pendingActive,
  scopeKey,
}: {
  stage: AiStage;
  label: string;
  placeholder: string;
  mode: AiMode;
  context: AiContext;
  disabled?: boolean;
  /**
   * One-line helper shown below the input for mode="select" only — describes what the
   * composer does so the user knows it pre-selects (not runs) the skill.
   * e.g. "Pre-selects a skill below to confirm and run."
   */
  hint?: string;
  /** Callback for mode="staged" — receives the proposed param changes to queue. */
  onStaged?: (proposals: AiProposal[]) => void;
  /**
   * Callback for mode="select" — receives the bare registry slug and must normalize,
   * resolve, and install it. Returns the resolved skill display name on success, or
   * `null` when the slug cannot be found in the catalog (unresolved → honest note shown).
   */
  onSelect?: (skillId: string) => string | null;
  /**
   * Callback for stage="ingest" — receives the raw proposal turn. The caller (the intake
   * questionnaire, which holds the detected design hints) maps it via `designFromIngestActions`,
   * applies the patch to the editable design, and returns a short note to show (e.g. "Proposed WT
   * vs KO — review below"), or `null` when nothing usable was proposed (an honest fallback note is
   * then shown). The mapping lives with the caller because it needs the detected levels for the
   * never-invent-a-level honesty check.
   */
  onIngest?: (turn: HelperTurn) => string | null;
  /**
   * Callback for the INFORMATIONAL modes (mode="advisory" grade · mode="draft" methods) — the caller
   * wires it to `explain({ request, ... })` grounded in its stage artifact (the figure's stats method
   * for grade; the deterministic methods text for methods). AskAi calls it on Ask and renders the
   * returned text with an AI/deterministic source badge (✨ only when `source==="ai"`). Returns null →
   * the honest "nothing to explain" note. Gateway-off still returns a grounded card (source="deterministic").
   */
  onExplain?: (goal: string) => Promise<ExplainResponse | null>;
  /**
   * Callback for mode="draft" ONLY — lifts the explain result out of the composer into the caller's
   * own EDITABLE field (the Methods textarea, `docs/methods-draft/spec.md` option A). When provided,
   * `draft` mode calls this with the returned text + source INSTEAD of rendering AskAi's read-only
   * result block (the caller owns display + edit + the ✨ source badge). Absent → `draft` falls back
   * to the same read-only render as `advisory`, so an un-lifted draft still shows something.
   */
  onDraftResult?: (text: string, source: ExplainResponse["source"]) => void;
  /**
   * Optional one-click "Auto-tune" — the DETERMINISTIC best-practice default for this stage
   * (docs/auto-tune/spec.md). When provided, a neutral (non-✨) button renders ABOVE the AI chat
   * ("the one-click default flows into chat"); the handler applies/stages the engine's recommendation
   * and returns a note. Absent → no button (byte-identical to a chat-only composer). This is NOT the
   * AI path — it needs no gateway and carries no ✨ marker.
   */
  onAutoTune?: () => Promise<AutoTuneOutcome>;
  /** Auto-tune button label (e.g. "Auto-tune", "Draft methods"). Defaults to "Auto-tune". */
  autoTuneLabel?: string;
  /** The neutral hint under the Auto-tune button BEFORE a click (overrides the analyze-flavoured
   *  "Best-practice defaults … then re-run" default — e.g. methods drafting has no re-run). Once the
   *  handler runs, its outcome note replaces this. Only meaningful with `onAutoTune`. */
  autoTuneHint?: string;
  /** Whether staged changes are currently pending (the caller's dirty flag). When it goes true→false
   *  (a Reset or a committed Re-run) the Auto-tune outcome note is cleared so it can't keep asserting
   *  pending changes exist. Only meaningful with `onAutoTune`. */
  pendingActive?: boolean;
  /** A scope key (e.g. dataset:skill:figure) — when it changes, the Auto-tune outcome note is cleared
   *  (the prior result no longer applies to the new figure). Only meaningful with `onAutoTune`. */
  scopeKey?: string;
  // later phase — onLive, onAdvice, onDraft (one per mode)
}) {
  const [goal, setGoal] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [tuning, setTuning] = React.useState(false);
  const [note, setNote] = React.useState<string | null>(null);
  // The informational (advisory/draft) explain result — rendered with an AI/deterministic source badge.
  const [result, setResult] = React.useState<ExplainResponse | null>(null);
  // The Auto-tune outcome is kept SEPARATE from the AI chat note so a deterministic result never
  // renders inside the ✨ AI surface (it is not AI output) — it shows in the neutral block below.
  const [tuneNote, setTuneNote] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);

  async function copyResult() {
    if (!result) return;
    // Same honesty invariant as the methods/legend draft: prefix [AI-generated] ONLY when the gateway
    // actually produced the text (source==="ai") — a grounded deterministic card copies clean.
    const marker = result.source === "ai" ? "[AI-generated]\n" : "";
    try {
      await navigator.clipboard.writeText(marker + result.text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked (e.g. insecure context) — no-op */
    }
  }

  async function autoTune() {
    if (!onAutoTune || tuning || busy) return;
    setTuning(true);
    setTuneNote(null);
    try {
      const r = await onAutoTune();
      setTuneNote(r.note);
    } catch (e) {
      setTuneNote(e instanceof Error ? e.message : "Couldn't auto-tune.");
    } finally {
      setTuning(false);
    }
  }

  // Keep the Auto-tune outcome note honest by adjusting state DURING render on the relevant prop
  // changes (React's "store info from previous renders" pattern, same as project-workspace's fdScope
  // reset) — not an effect. Clear the note when its staged changes are reversed (Reset) or committed
  // (Re-run) — pending goes true→false — or when the figure scope changes; never on the click's own
  // false→true edge. setTuneNote(null) when already null is a no-op, so this can't loop.
  const [prevScope, setPrevScope] = React.useState(scopeKey);
  if (scopeKey !== prevScope) {
    setPrevScope(scopeKey);
    setTuneNote(null);
  }
  const [prevPending, setPrevPending] = React.useState(!!pendingActive);
  if (!!pendingActive !== prevPending) {
    setPrevPending(!!pendingActive);
    if (!pendingActive) setTuneNote(null);
  }

  async function send() {
    const g = goal.trim();
    if (!g || busy) return;

    if (stage === "ingest") {
      // Ingest is STAGED, but maps to a design PATCH (not figure-data params): fetch the proposal and
      // let the caller (the questionnaire, which holds the detected design) map + apply it + describe it.
      setBusy(true);
      setNote(null);
      try {
        const turn = await proposeActions({
          stage,
          skill_id: context.skillId,
          params: context.params,
          goal: g,
          // The detected column names help the gateway map messy sample names → conditions.
          data_columns: context.dataColumns ?? undefined,
        });
        const applied = onIngest?.(turn) ?? null;
        if (applied) {
          setNote(applied);
          setGoal("");
        } else {
          setNote(
            turn.plan.notes ||
              "No design suggestion — the AI gateway is off or couldn't map your names to the detected conditions. Your form is unaffected.",
          );
        }
      } catch (e) {
        setNote(e instanceof Error ? e.message : "Couldn't reach the AI helper.");
      } finally {
        setBusy(false);
      }
    } else if (mode === "staged") {
      setBusy(true);
      setNote(null);
      try {
        const turn = await proposeActions({
          stage,
          skill_id: context.skillId,
          params: context.params,
          goal: g,
          figure_spec: (context.figureSpec as Record<string, unknown> | null | undefined) ?? null,
          capability_surface: context.capabilitySurface ?? null,
        });
        const proposals = proposalsFromTurn(turn);
        if (proposals.length > 0) {
          onStaged?.(proposals);
          setGoal("");
        } else if (turn.plan.actions.length > 0) {
          // The gateway DID propose, but only cosmetic actions (restyle/relabel) — they don't enter the
          // recompute queue, and applying them live from turn.figure_spec isn't wired yet (deferred,
          // gateway-off). Say that honestly rather than "nothing to propose" (which would be a lie).
          setNote(
            `The AI suggested ${turn.plan.actions.length} cosmetic change${turn.plan.actions.length === 1 ? "" : "s"} (restyle/relabel); applying those live isn't wired into this flow yet, so there are no input changes to stage.`,
          );
        } else {
          setNote(
            turn.plan.notes ||
              "No suggestions — the AI gateway is off or had nothing to propose. Your editor is unaffected.",
          );
        }
      } catch (e) {
        setNote(e instanceof Error ? e.message : "Couldn't reach the AI helper.");
      } finally {
        setBusy(false);
      }
    } else if (mode === "select") {
      setBusy(true);
      setNote(null);
      try {
        const turn = await proposeActions({
          stage,
          skill_id: context.skillId,
          params: context.params,
          goal: g,
          // Data-aware routing: lets the gateway score its suggested skill against the real data
          // (the select_skill compat gate). Omitted fields → the server skips the check (fail-soft).
          data_columns: context.dataColumns ?? undefined,
          data_kind: context.dataKind ?? undefined,
          data_n_numeric_cols: context.dataNumericCols ?? undefined,
        });
        const sel = selectedSkillFromTurn(turn);
        if (sel.skillId) {
          const name = onSelect?.(sel.skillId);
          if (name) {
            setNote(
              `Selected ${name} below — ${sel.rationale || "review the inputs and Apply."}`,
            );
            setGoal("");
          } else {
            setNote(
              `The AI suggested "${sel.skillId}", which isn't available in this workspace.`,
            );
          }
        } else if (sel.gap?.unmet === "no_fitting_skill") {
          setNote(`No fitting skill for that — recorded as a gap.`);
        } else {
          setNote(
            turn.plan.notes ||
              "No suggestion — the AI gateway is off or had nothing to propose. Your picker is unaffected.",
          );
        }
      } catch (e) {
        setNote(e instanceof Error ? e.message : "Couldn't reach the AI helper.");
      } finally {
        setBusy(false);
      }
    } else if (mode === "advisory" || mode === "draft") {
      // Informational path: call the caller's explain resolver. Deterministic-primary — gateway off
      // still returns a grounded card (source="deterministic"). For mode="draft" with `onDraftResult`,
      // LIFT the text into the caller's editable field (the Methods textarea); otherwise render it in
      // the read-only result block (advisory, and un-lifted draft).
      setBusy(true);
      setNote(null);
      try {
        const r = (await onExplain?.(g)) ?? null;
        if (r) {
          if (mode === "draft" && onDraftResult) {
            onDraftResult(r.text, r.source);
          } else {
            setResult(r);
          }
          setGoal("");
        } else {
          setNote(
            mode === "draft"
              ? "Nothing to draft — this figure has no generated methods text yet."
              : "Nothing to explain here yet — run a skill that produces a statistic first.",
          );
        }
      } catch (e) {
        setNote(e instanceof Error ? e.message : "Couldn't reach the AI helper.");
      } finally {
        setBusy(false);
      }
    }
    // mode="live" (cosmetic JSON-Patch) is a later phase — falls through silently.
  }

  // The ✨ AI chat surface (the typed-goal path) — rendered byte-identically whether or not the
  // Auto-tune button is present, so opting a stage into Auto-tune never regresses the chat.
  const aiChat = (
    <div
      className={cn(
        "rounded-xl border p-3",
        "border-stage-ai/30 bg-[color-mix(in_oklab,var(--stage-ai)_7%,var(--card))]",
      )}
    >
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-foreground">
        <Sparkles className="size-3.5 text-stage-ai" aria-hidden />
        {label}
      </p>
      <div className="flex items-center gap-2">
        <Input
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void send();
            }
          }}
          placeholder={placeholder}
          disabled={disabled || busy}
          aria-label={label}
          className="h-8 flex-1 text-xs"
        />
        <Button
          size="sm"
          // When Auto-tune is present it is the primary CTA (the deterministic path is primary and
          // always works); the AI chat — gateway-off by default — steps back to the outline variant.
          // Standalone (no Auto-tune, e.g. the route composer) "Ask" stays the primary action.
          variant={onAutoTune ? "outline" : "default"}
          disabled={disabled || busy || !goal.trim()}
          onClick={() => void send()}
        >
          {busy ? "Asking…" : <><CornerDownLeft /> Ask</>}
        </Button>
      </div>
      {mode === "select" && hint && !note && (
        <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{hint}</p>
      )}
      {note && (
        <p role="status" aria-live="polite" className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
          {note}
        </p>
      )}
      {result && (
        <div className="mt-2 rounded-lg border border-border bg-background/50 px-3 py-2.5">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              {mode === "draft" ? "Draft" : "Advisory"}
            </span>
            <div className="flex items-center gap-2">
              {/* ✨ AI only when the gateway actually produced it; a grounded deterministic card is labelled so. */}
              <ExplainSourceBadge source={result.source} />
              {/* Copy the advisory text (fe-review MED) — carries the [AI-generated] marker only when source=ai. */}
              <button
                type="button"
                onClick={() => void copyResult()}
                className="rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
          <p className="whitespace-pre-wrap text-xs leading-relaxed text-foreground/85">{result.text}</p>
        </div>
      )}
    </div>
  );

  if (!onAutoTune) return aiChat;

  // One surface, two paths: the DETERMINISTIC one-click Auto-tune (neutral — no ✨, no gateway) sits
  // above and "flows into" the AI chat. Its outcome shows in this neutral block, never in the ✨ box.
  return (
    <div className="space-y-2.5">
      <div className="rounded-xl border border-border bg-card p-3">
        <Button
          type="button"
          // The deterministic one-click default is the PRIMARY CTA (spine invariant: deterministic
          // path primary). Neutral --primary weight, never the --stage-ai/✨ AI accent (spec R8).
          variant="default"
          size="sm"
          className="w-full"
          disabled={disabled || tuning || busy}
          aria-busy={tuning}
          onClick={() => void autoTune()}
        >
          <SlidersHorizontal />
          {tuning ? "Tuning…" : (autoTuneLabel ?? "Auto-tune")}
        </Button>
        <p
          role="status"
          aria-live="polite"
          className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground"
        >
          {tuneNote ?? autoTuneHint ?? "Best-practice defaults — no AI. Review the changed inputs below, then re-run."}
        </p>
      </div>
      {aiChat}
    </div>
  );
}
