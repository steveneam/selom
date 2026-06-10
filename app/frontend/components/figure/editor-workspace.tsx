"use client";

import { FigureCanvas } from "./figure-canvas";
import { PropertyPanel } from "./property-panel";
import type { FigureStore } from "@/hooks/use-figure-store";

export function EditorWorkspace({ store }: { store: FigureStore }) {
  const spec = store.spec;
  if (!spec) return null;
  const fixed = typeof spec.layout.width === "number";

  return (
    <div className="flex min-h-0 flex-1">
      {/* Workspace: the figure lives on a luminous white artboard floating on dark canvas. */}
      <div className="relative flex min-w-0 flex-1 items-center justify-center overflow-auto p-6 lg:p-10">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(48rem 28rem at 50% 12%, color-mix(in oklab, var(--primary) 9%, transparent), transparent 72%)",
          }}
        />
        <div
          className="relative flex rounded-xl border border-border bg-artboard p-3 shadow-2xl ring-1 ring-black/5"
          style={
            fixed ? undefined : { width: "100%", maxWidth: "64rem", height: "min(74vh, 720px)" }
          }
        >
          <div className="min-h-0 min-w-0 flex-1">
            <FigureCanvas spec={spec} />
          </div>
        </div>
      </div>

      <aside className="flex w-[330px] shrink-0 flex-col border-l border-border bg-card">
        <PropertyPanel store={store} />
      </aside>
    </div>
  );
}
