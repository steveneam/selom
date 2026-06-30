"use client";

import * as React from "react";
import { Sparkles, CornerDownLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/ui/cn";
import { proposeActions } from "@/lib/ai/api";
import { proposalsFromTurn } from "@/lib/ai/proposals";
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

/** Context bundle forwarded to the gateway (mirrors backend ProposeRequest fields). */
export interface AiContext {
  skillId?: string | null;
  params?: SkillParams;
  figureSpec?: FigureSpec | null;
  capabilitySurface?: Record<string, unknown> | null;
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
  onStaged,
}: {
  stage: AiStage;
  label: string;
  placeholder: string;
  mode: AiMode;
  context: AiContext;
  disabled?: boolean;
  /** Callback for mode="staged" — receives the proposed param changes to queue. */
  onStaged?: (proposals: AiProposal[]) => void;
  // later phase — onLive, onAdvice, onSelect, onDraft (one per mode)
}) {
  const [goal, setGoal] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [note, setNote] = React.useState<string | null>(null);

  async function send() {
    // Only `staged` is wired in Phase 0; other modes are later phases.
    if (mode !== "staged") return;
    const g = goal.trim();
    if (!g || busy) return;
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
  }

  return (
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
          aria-label="Describe what you want the AI to adjust"
          className="h-8 flex-1 text-xs"
        />
        <Button size="sm" disabled={disabled || busy || !goal.trim()} onClick={() => void send()}>
          {busy ? "Asking…" : <><CornerDownLeft /> Ask</>}
        </Button>
      </div>
      {note && <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{note}</p>}
    </div>
  );
}
