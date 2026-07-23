"use client";

import * as React from "react";
import { ArrowUpRight, Asterisk, Eye, EyeOff, Trash2, Type } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Section } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import {
  addArrowOps,
  addSigBracketOps,
  addTextLabelOps,
  annotationTextOps,
  annotationVisibilityOps,
  removeAnnotationOps,
  selomAnnotations,
  STAR_TIERS,
  type SelomAnnotation,
} from "@/lib/figure/annotations";
import { cn } from "@/lib/ui/cn";

/**
 * Annotate — the export-killer panel (Pillar-2 slice 5). Add the annotations the owner round-trips to
 * Illustrator for: significance brackets + stars, arrows / callouts, free text labels. Each "Add" is one
 * undoable JSON-Patch that appends a NATIVE, `selom`-tagged `layout.shapes`/`layout.annotations` item —
 * so it renders instantly (render = f(spec)), drags on the artboard (Plotly's shape/annotation edits),
 * and exports with the figure. The list below manages the items added here (edit text/stars, show/hide,
 * remove); skill-emitted labels stay in the Marks panel.
 */
export function AnnotationsPanel({ store, spec }: { store: FigureStore; spec: FigureSpec }) {
  const items = selomAnnotations(spec);

  return (
    <div className="space-y-6">
      <Section title="Add annotation">
        <div className="space-y-1.5">
          <AddButton
            icon={Asterisk}
            label="Significance bracket"
            hint="Bracket + stars over two groups"
            onClick={() => store.commit(addSigBracketOps(spec))}
          />
          <AddButton
            icon={Type}
            label="Text label"
            hint="Panel letter, gene name, or note"
            onClick={() => store.commit(addTextLabelOps(spec))}
          />
          <AddButton
            icon={ArrowUpRight}
            label="Arrow / callout"
            hint="Pointer or leader line"
            onClick={() => store.commit(addArrowOps(spec))}
          />
        </div>
        <p className="text-[11px] leading-relaxed text-muted-foreground/80">
          Each annotation lives in the figure — drag it on the artboard to place it, and it exports with
          the figure. Undo (Cmd-Z) reverts any add.
        </p>
      </Section>

      {items.length > 0 && (
        <Section title={`On the figure · ${items.length}`}>
          <div className="space-y-1.5">
            {items.map((item) => (
              <AnnotationRow key={item.id} store={store} spec={spec} item={item} />
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function AddButton({
  icon: Icon,
  label,
  hint,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  hint: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-lg border border-border/70 bg-background/40 p-2 text-left transition-colors hover:border-input hover:bg-accent/40"
    >
      <span className="grid size-8 shrink-0 place-items-center rounded-md bg-muted text-foreground/80 [&_svg]:size-4">
        <Icon />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium text-foreground">{label}</span>
        <span className="block truncate text-[11px] text-muted-foreground">{hint}</span>
      </span>
    </button>
  );
}

function AnnotationRow({
  store,
  spec,
  item,
}: {
  store: FigureStore;
  spec: FigureSpec;
  item: SelomAnnotation;
}) {
  const isBracket = item.kind === "sigBracket";
  return (
    <div className="space-y-1.5 rounded-lg border border-border/70 bg-background/40 p-1.5">
      <div className="flex items-center gap-2">
        <span className="pl-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/80">
          {item.label}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <IconButton
            active={item.visible}
            label={item.visible ? `Hide ${item.label}` : `Show ${item.label}`}
            onClick={() => store.commit(annotationVisibilityOps(spec, item.id, !item.visible))}
          >
            {item.visible ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
          </IconButton>
          <IconButton
            label={`Remove ${item.label}`}
            onClick={() => store.commit(removeAnnotationOps(spec, item.id))}
            danger
          >
            <Trash2 className="size-4" />
          </IconButton>
        </div>
      </div>
      {isBracket ? (
        <StarPicker
          value={item.text}
          visible={item.visible}
          onPick={(v) => store.commit(annotationTextOps(spec, item.id, v))}
        />
      ) : (
        <TextEditor
          value={item.text}
          visible={item.visible}
          placeholder={item.kind === "arrow" ? "Optional caption" : "Label text"}
          ariaLabel={`${item.label} text`}
          onCommit={(v) => store.commit(annotationTextOps(spec, item.id, v))}
        />
      )}
    </div>
  );
}

/** Quick-pick the significance tier (hand-set stars; the p-value path derives them at add time). */
function StarPicker({
  value,
  visible,
  onPick,
}: {
  value: string;
  visible: boolean;
  onPick: (v: string) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Significance level"
      className={cn("flex flex-wrap gap-1", !visible && "opacity-50")}
    >
      {STAR_TIERS.map((tier) => (
        <button
          key={tier}
          type="button"
          aria-pressed={value === tier}
          onClick={() => onPick(tier)}
          className={cn(
            "tabular h-7 min-w-9 flex-1 rounded-md border px-1.5 text-xs font-semibold transition-colors",
            value === tier
              ? "border-primary bg-primary/10 text-foreground"
              : "border-border/70 text-muted-foreground hover:bg-accent/50",
          )}
        >
          {tier}
        </button>
      ))}
    </div>
  );
}

/** Inline text editor that commits on blur / Enter (so typing doesn't spam history). */
function TextEditor({
  value,
  visible,
  placeholder,
  ariaLabel,
  onCommit,
}: {
  value: string;
  visible: boolean;
  placeholder: string;
  ariaLabel: string;
  onCommit: (v: string) => void;
}) {
  const [draft, setDraft] = React.useState(value);
  React.useEffect(() => setDraft(value), [value]);
  const commit = () => {
    if (draft !== value) onCommit(draft);
  };
  return (
    <Input
      value={draft}
      placeholder={placeholder}
      aria-label={ariaLabel}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
      }}
      className={cn(
        "h-8 border-transparent bg-transparent px-2 shadow-none focus-visible:border-input focus-visible:bg-background/60",
        !visible && "text-muted-foreground/60 line-through",
      )}
    />
  );
}

function IconButton({
  children,
  label,
  onClick,
  active,
  danger,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  active?: boolean;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={cn(
        "grid size-7 shrink-0 cursor-pointer place-items-center rounded-md transition-colors",
        danger
          ? "text-muted-foreground/70 hover:bg-destructive/10 hover:text-destructive"
          : active
            ? "text-foreground/80 hover:bg-accent hover:text-accent-foreground"
            : "text-muted-foreground/60 hover:bg-accent hover:text-accent-foreground",
      )}
    >
      {children}
    </button>
  );
}
