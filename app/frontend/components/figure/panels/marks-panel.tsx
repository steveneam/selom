"use client";

import * as React from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Section, SwitchField, TextField } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure-spec";
import {
  annotationItems,
  annotationTextOp,
  annotationVisibilityOp,
  scalebarResizeOps,
  scalebarVisibilityOps,
  type FigureModel,
} from "@/lib/figure-model";
import { cn } from "@/lib/cn";

/**
 * Marks — generic, owner-controlled layout primitives (P3 §3.5). The scale bar is found
 * deterministically via the skill's `meta.selom.primitives` hint (not guessed among shapes), so
 * it can be shown/hidden and resized (change the denoted length — the bar stays accurate because
 * it is one paper-referenced pair sized to the shared data→paper mapping). Annotations (unit
 * labels, condition labels, threshold callouts) get a list with show/hide + inline edit.
 */
export function MarksPanel({
  store,
  spec,
  model,
}: {
  store: FigureStore;
  spec: FigureSpec;
  model: FigureModel;
}) {
  const sb = model.scalebar;
  const annos = annotationItems(spec);

  return (
    <div className="space-y-6">
      {sb && (
        <Section title="Scale bar">
          <SwitchField
            label="Show scale bar"
            checked={sb.visible}
            onChange={(v) => store.commit(scalebarVisibilityOps(sb, v))}
          />
          {sb.visible && (
            <>
              {sb.yLen > 0 && (
                <TextField
                  label={`Amplitude (${sb.yUnit})`}
                  value={String(sb.yLen)}
                  mono
                  onCommit={(v) => {
                    const n = parseFloat(v);
                    if (n > 0) store.commit(scalebarResizeOps(spec, sb, "y", n));
                  }}
                />
              )}
              {sb.xLen > 0 && (
                <TextField
                  label={`Time (${sb.xUnit})`}
                  value={String(sb.xLen)}
                  mono
                  onCommit={(v) => {
                    const n = parseFloat(v);
                    if (n > 0) store.commit(scalebarResizeOps(spec, sb, "x", n));
                  }}
                />
              )}
              <p className="text-[11px] leading-relaxed text-muted-foreground/80">
                The bar denotes a fixed data length — changing a value rescales the bar and relabels
                it. Drag it on the figure to reposition.
              </p>
            </>
          )}
        </Section>
      )}

      {annos.length > 0 && (
        <Section title={`Annotations · ${annos.length}`}>
          <div className="space-y-1.5">
            {annos.map((a) => (
              <AnnotationRow key={a.index} store={store} index={a.index} text={a.text} visible={a.visible} />
            ))}
          </div>
          <p className="text-[11px] leading-relaxed text-muted-foreground/80">
            Edit a label, or hide it. Double-click any annotation on the figure to edit it in place.
          </p>
        </Section>
      )}
    </div>
  );
}

function AnnotationRow({
  store,
  index,
  text,
  visible,
}: {
  store: FigureStore;
  index: number;
  text: string;
  visible: boolean;
}) {
  const [draft, setDraft] = React.useState(text);
  React.useEffect(() => setDraft(text), [text]);
  const commit = () => {
    if (draft !== text) store.commit([annotationTextOp(index, draft)]);
  };

  return (
    <div className="flex items-center gap-2 rounded-lg border border-border/70 bg-background/40 p-1.5">
      <Input
        value={draft}
        aria-label={`Annotation ${index + 1} text`}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
        className={cn(
          "h-7 flex-1 border-transparent bg-transparent px-1.5 shadow-none focus-visible:border-input focus-visible:bg-background/60",
          !visible && "text-muted-foreground/60 line-through",
        )}
      />
      <button
        type="button"
        aria-label={visible ? `Hide annotation ${index + 1}` : `Show annotation ${index + 1}`}
        title={visible ? "Hide" : "Show"}
        onClick={() => store.commit([annotationVisibilityOp(index, !visible)])}
        className={cn(
          "grid size-7 shrink-0 cursor-pointer place-items-center rounded-md transition-colors hover:bg-accent hover:text-accent-foreground",
          visible ? "text-foreground/80" : "text-muted-foreground/60",
        )}
      >
        {visible ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
      </button>
    </div>
  );
}
