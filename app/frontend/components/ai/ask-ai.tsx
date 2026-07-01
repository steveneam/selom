"use client";

import * as React from "react";
import { Sparkles, CornerDownLeft, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/ui/cn";
import { proposeActions } from "@/lib/ai/api";
import { proposalsFromTurn, selectedSkillFromTurn } from "@/lib/ai/proposals";
import type { AiProposal } from "@/lib/ai/types";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { SkillParams } from "@/lib/skills/api";

/** Stages in the engine spine that Layer A (AI Assist) owns. */
export type AiStage = "route" | "ingest" | "analyze" | "grade" | "output";

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
  onAutoTune,
  autoTuneLabel,
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
   * Optional one-click "Auto-tune" — the DETERMINISTIC best-practice default for this stage
   * (docs/auto-tune/spec.md). When provided, a neutral (non-✨) button renders ABOVE the AI chat
   * ("the one-click default flows into chat"); the handler applies/stages the engine's recommendation
   * and returns a note. Absent → no button (byte-identical to a chat-only composer). This is NOT the
   * AI path — it needs no gateway and carries no ✨ marker.
   */
  onAutoTune?: () => Promise<AutoTuneOutcome>;
  /** Auto-tune button label (e.g. "Auto-tune", "Draft methods"). Defaults to "Auto-tune". */
  autoTuneLabel?: string;
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
  // The Auto-tune outcome is kept SEPARATE from the AI chat note so a deterministic result never
  // renders inside the ✨ AI surface (it is not AI output) — it shows in the neutral block below.
  const [tuneNote, setTuneNote] = React.useState<string | null>(null);

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

    if (mode === "staged") {
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
    }
    // Other modes (live, advisory, draft) are later phases — fall through silently.
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
          {tuneNote ?? "Best-practice defaults — no AI. Review the changed inputs below, then re-run."}
        </p>
      </div>
      {aiChat}
    </div>
  );
}
