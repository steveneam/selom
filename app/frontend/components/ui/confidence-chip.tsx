import * as React from "react";
import { ShieldCheck, ShieldQuestion, ShieldX, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/ui/cn";
import { TONE_COLOR, type ConfidenceTone } from "@/lib/ui/confidence";

export type ChipSize = "xs" | "sm" | "md";

// Per-size shape — the three call sites this primitive replaces collapse to one scale:
//   xs → the data-type detector's tiny inline tag
//   sm → skill-match's tier chip
//   md → the reproduction data-fit band chip (prominent, card-leading)
// Icon sizing rides the chip via [&_svg] so a chip with or without an icon keeps its height.
const SIZE_CLASS: Record<ChipSize, string> = {
  xs: "gap-1 rounded-md px-1.5 py-px text-[10px] font-medium [&_svg]:size-3",
  sm: "gap-1 rounded-md px-2 py-0.5 text-xs font-medium [&_svg]:size-3.5",
  md: "gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold [&_svg]:size-3.5",
};

/**
 * The shared tinted-pill shape. One home for the `color-mix` tint (12% surface · 40% border · 80%
 * text mixed over the theme `--foreground`, so it holds in light AND dark) plus the size scale.
 * Takes a raw `color` so non-semantic chips — e.g. skill-match's per-tier colours — can reuse the
 * exact shape; for a confidence verdict prefer {@link ConfidenceChip}, which maps a tone → colour
 * and a matching icon.
 */
export function TintChip({
  color,
  label,
  size = "sm",
  icon: Icon,
  className,
  title,
}: {
  color: string;
  label: React.ReactNode;
  size?: ChipSize;
  icon?: LucideIcon;
  className?: string;
  title?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap border",
        SIZE_CLASS[size],
        className,
      )}
      style={{
        backgroundColor: `color-mix(in oklab, ${color} 12%, transparent)`,
        borderColor: `color-mix(in oklab, ${color} 40%, transparent)`,
        color: `color-mix(in oklab, ${color} 80%, var(--foreground))`,
      }}
      title={title}
    >
      {Icon ? <Icon aria-hidden /> : null}
      {label}
    </span>
  );
}

// One Shield icon vocabulary across every confidence surface (filled-vs-outline discipline — all
// lucide outline). Colour is never the only signal: the icon + the caller's word carry the meaning
// too, so the chip stays colour-blind safe.
const TONE_ICON: Record<ConfidenceTone, LucideIcon> = {
  positive: ShieldCheck,
  caution: ShieldCheck,
  neutral: ShieldQuestion,
  negative: ShieldX,
  muted: ShieldQuestion,
};

/**
 * A confidence verdict as a chip: the shared tone colour + its matching Shield icon + the caller's
 * label. Each surface maps its own vocabulary onto a tone and passes its own label, so "Likely",
 * "Uncertain", and "Usable" can all wear the one quiet-slate `neutral` tone yet keep their words.
 * Pass `hideIcon` when the surrounding layout already carries the meaning and an icon would crowd it.
 */
export function ConfidenceChip({
  tone,
  label,
  size = "sm",
  hideIcon,
  className,
  title,
}: {
  tone: ConfidenceTone;
  label: React.ReactNode;
  size?: ChipSize;
  hideIcon?: boolean;
  className?: string;
  title?: string;
}) {
  return (
    <TintChip
      color={TONE_COLOR[tone]}
      label={label}
      size={size}
      icon={hideIcon ? undefined : TONE_ICON[tone]}
      className={className}
      title={title}
    />
  );
}
