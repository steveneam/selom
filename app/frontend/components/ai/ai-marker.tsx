"use client";

import * as React from "react";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/ui/cn";
import { formatApprovedAt } from "@/lib/ai/format";
import type { AiAction } from "@/lib/ai/types";

/**
 * The ✨ AI-attribution marker (S5, build piece a).
 *
 * A small Sparkles glyph that tags an AI-touched control/row, in the fuchsia `--stage-ai`
 * accent. THREE states, distinguished by FILL — never by colour alone (the glyph shape + the
 * tooltip text carry the meaning, so it's colourblind- and screen-reader-safe):
 *   proposed  — HOLLOW (stroke only). An un-acted AI suggestion; pulses gently to ask for
 *               attention (a meaningful animation, auto-disabled under prefers-reduced-motion).
 *   staged    — FILLED. The AI's value is accepted + staged on this control but NOT yet re-run
 *               (pre-commit); the tooltip carries the model and clicking reverts to base.
 *   applied   — FILLED + muted. A COMMITTED AI change (backed by a provenance `action`); the
 *               tooltip carries the full provenance tag (actor · model · approved-at).
 *
 * "staged" vs "applied" matters: a not-yet-re-run value must not claim it was applied. When `onRevert`
 * is given the marker is an actual button (focusable); otherwise it's an inert span (read-only feed).
 */
export function AiMarker({
  state,
  model,
  action,
  onRevert,
  className,
  size = "sm",
}: {
  state: "proposed" | "staged" | "applied";
  /** Model id for the proposed/staged tooltip (the applied tooltip prefers `action.model`). */
  model?: string;
  /** The provenance action behind an APPLIED (committed) marker — supplies the tooltip's actor·model·date. */
  action?: AiAction;
  /** Click handler. Staged/applied → revert to base; proposed → dismiss the suggestion. */
  onRevert?: () => void;
  className?: string;
  size?: "xs" | "sm";
}) {
  const px = size === "xs" ? "size-3" : "size-3.5";
  const verb = onRevert ? (state === "proposed" ? " — click to dismiss" : " — click to revert") : "";
  const tip =
    state === "applied"
      ? `${tagLabel(action)}${verb}`
      : state === "staged"
        ? `Staged by AI${model ? ` · ${model}` : ""}${verb}`
        : `Proposed by AI${model ? ` · ${model}` : ""}${verb}`;
  // The full tag rides the accessible name too — not just the mouse-only `title` — so keyboard + SR
  // users get the same attribution, prefixed with the state so it's self-describing out of context.
  const stateWord =
    state === "applied" ? "AI-applied change" : state === "staged" ? "AI-staged change" : "AI-proposed change";
  const label = `${stateWord} — ${tip}`;

  const glyph = (
    <Sparkles
      aria-hidden
      className={cn(
        px,
        "text-stage-ai",
        state === "applied"
          ? "fill-[color-mix(in_oklab,var(--stage-ai)_25%,transparent)] opacity-80"
          : state === "staged"
            ? "fill-[color-mix(in_oklab,var(--stage-ai)_30%,transparent)]"
            : "animate-pulse opacity-90",
      )}
    />
  );

  if (!onRevert) {
    return (
      <span className={cn("inline-flex shrink-0 items-center", className)} title={tip} aria-label={label} role="img">
        {glyph}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={onRevert}
      title={tip}
      aria-label={label}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-md p-1 transition-colors cursor-pointer",
        "hover:bg-[color-mix(in_oklab,var(--stage-ai)_14%,transparent)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stage-ai/50",
        className,
      )}
    >
      {glyph}
    </button>
  );
}

/** "AI · gpt · Jun 29, 14:32" — the provenance tag for an applied marker's tooltip. */
function tagLabel(action?: AiAction): string {
  if (!action) return "Applied by AI";
  const parts = [action.actor || "ai"];
  if (action.model) parts.push(action.model);
  const when = formatApprovedAt(action.approved_at);
  if (when) parts.push(when);
  return parts.join(" · ");
}
