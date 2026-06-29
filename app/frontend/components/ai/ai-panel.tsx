"use client";

import * as React from "react";
import { Sparkles, X } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/ui/cn";
import { AiActivityFeed, type ActivityTurn } from "./ai-activity-feed";
import { CapabilityGapView } from "./capability-gap-view";
import type { AiProposal } from "@/lib/ai/types";

/**
 * The AI panel (S5) — a right-side dock with two tabs: Activity (the audit feed over
 * `provenance.actions[]`) and Gaps (the `GET /ai/gaps` capability backlog). It reuses the
 * focused-dock pattern (a fixed-width side column, the FigureDataPanel idiom) — deliberately
 * NOT the full conversational Ask-Selom chat dock, which stays a future Pillar-3 feature.
 *
 * Rendered as a fixed right dock so it overlays consistently across every workspace view without
 * restructuring the layout; the user keeps working underneath (it's a dock, not a modal — no
 * backdrop, no focus trap). The fuchsia `--stage-ai` accent marks it as the AI surface throughout.
 */
export function AiPanel({
  open,
  onClose,
  turns,
  proposals,
  aiCount,
}: {
  open: boolean;
  onClose: () => void;
  /** Committed AI-assisted runs (one per AI-touched figure) for the Activity feed's History. */
  turns: ActivityTurn[];
  /** The open figure's live proposal queue — the Activity feed's Pending section. */
  proposals: AiProposal[];
  /** The pending ✨AI count, mirrored from the banner onto the Activity tab badge. */
  aiCount: number;
}) {
  if (!open) return null;
  return (
    <aside
      aria-label="AI activity"
      // Dock BELOW the global app header (h-14 / 3.5rem) rather than top-0, so the fixed panel sits
      // within the content region instead of painting over the header's right edge.
      className={cn(
        "fixed right-0 top-14 z-40 flex h-[calc(100dvh-3.5rem)] w-[360px] flex-col border-l border-border bg-card shadow-2xl",
        "ring-1 ring-[color-mix(in_oklab,var(--stage-ai)_22%,transparent)]",
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-border px-3.5 py-2.5">
        <span className="flex items-center gap-2 text-sm font-semibold tracking-tight text-foreground">
          <Sparkles className="size-4 text-stage-ai" aria-hidden />
          AI activity
        </span>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close AI panel" className="-mr-1.5">
          <X />
        </Button>
      </header>

      <Tabs defaultValue="activity" className="flex min-h-0 flex-1 flex-col">
        <div className="px-3 pt-2.5">
          <TabsList className="w-full">
            <TabsTrigger value="activity">
              Activity
              {aiCount > 0 && (
                <span
                  className="ml-1 inline-flex min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-semibold tabular-nums text-stage-ai"
                  style={{ backgroundColor: "color-mix(in oklab, var(--stage-ai) 16%, transparent)" }}
                  aria-label={`${aiCount} pending AI changes`}
                >
                  {aiCount}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="gaps">Gaps</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="activity" className="min-h-0 flex-1">
          <ScrollArea className="h-full px-3.5 py-3">
            <AiActivityFeed turns={turns} proposals={proposals} />
          </ScrollArea>
        </TabsContent>
        <TabsContent value="gaps" className="min-h-0 flex-1">
          <ScrollArea className="h-full px-3.5 py-3">
            <CapabilityGapView />
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </aside>
  );
}
