"use client";

import { Lock } from "lucide-react";
import { FigureCanvas } from "./figure-canvas";
import { PropertyPanel } from "./property-panel";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { FigureStore } from "@/hooks/use-figure-store";

export function EditorWorkspace({
  store,
  elevated = false,
  readOnly = false,
  onEditCopy,
}: {
  store: FigureStore;
  elevated?: boolean;
  /** Frozen "paper" version (Pillar 1, S3): render the figure but bind no edit
   *  gestures, and replace the inspector with an "Edit a copy" notice (Decision D6). */
  readOnly?: boolean;
  onEditCopy?: () => void;
}) {
  const spec = store.spec;
  if (!spec) return null;
  const fixed = typeof spec.layout.width === "number";

  return (
    <div className="flex min-h-0 flex-1">
      {/* Workspace: the figure lives on a luminous white artboard floating on dark canvas.
          Top-align (not center): a tall figure overflows the scroll region, and centering
          would push its top out of view AND make it unreachable by scrolling. */}
      <div className="relative flex min-w-0 flex-1 items-start justify-center overflow-auto p-6 lg:p-10">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(48rem 28rem at 50% 12%, color-mix(in oklab, var(--primary) 9%, transparent), transparent 72%)",
          }}
        />
        <div
          className={cn(
            "relative flex rounded-xl border border-border bg-artboard p-3 shadow-2xl ring-1 ring-black/5",
            // During export, the figure is the subject — lift it above the scrim (z-40)
            // but below the popover (z-50) so the rest of the page blurs around it.
            elevated && "z-[45]",
          )}
          style={
            fixed ? undefined : { width: "100%", maxWidth: "64rem", height: "min(74vh, 720px)" }
          }
        >
          <div className="min-h-0 min-w-0 flex-1">
            {/* Read-only: no `store` → no edit gestures, no `edits` config, pure view. */}
            <FigureCanvas spec={spec} store={readOnly ? undefined : store} />
          </div>
        </div>
      </div>

      <aside className="flex w-[330px] shrink-0 flex-col border-l border-border bg-card">
        {readOnly ? <FrozenNotice onEditCopy={onEditCopy} /> : <PropertyPanel store={store} />}
      </aside>
    </div>
  );
}

/** The inspector slot for a frozen "paper" version — editing is off; fork to change it. */
function FrozenNotice({ onEditCopy }: { onEditCopy?: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <span className="grid size-10 place-items-center rounded-xl border border-stage-figure/40 bg-stage-figure/10 text-stage-figure [&_svg]:size-5">
        <Lock />
      </span>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">Frozen — the paper version</p>
        <p className="mx-auto max-w-[18rem] text-xs text-muted-foreground">
          This version is locked so it stays exactly as published. Edit a copy to make
          changes — the original is kept, untouched.
        </p>
      </div>
      {onEditCopy && (
        <Button size="sm" variant="outline" onClick={onEditCopy}>
          Edit a copy
        </Button>
      )}
    </div>
  );
}
