"use client";

import { Sparkles } from "lucide-react";
import type { ExplainResponse } from "@/lib/ai/types";

/**
 * Honest source label for an `/ai/explain` result.
 *
 * The ✨ "AI" badge appears ONLY when the gateway actually produced the text
 * (`source === "ai"`). A deterministic summary (the default, gateway OFF) reads plainly
 * as "Grounded summary" — the ✨ glyph stays reserved for genuine AI so it never lies
 * (owner steer, 2026-06-30). Mirrors the `--stage-ai` accent used by {@link AiMarker}.
 */
export function ExplainSourceBadge({ source }: { source: ExplainResponse["source"] }) {
  if (source === "ai") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-stage-ai">
        <Sparkles aria-hidden className="size-3" /> AI
      </span>
    );
  }
  return (
    <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
      Grounded summary
    </span>
  );
}
