import type { ComponentType } from "react";
import { Asterisk, FileText, Layers, Palette, Ruler, Shapes, Tags } from "lucide-react";

import { annotationLayerEnabled } from "@/lib/config/env";
import { nonSelomAnnotationItems } from "@/lib/figure/annotations";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import { deriveFigureModel } from "@/lib/figure/figure-model";

/**
 * The inspector's tab set, derived once and consumed twice (`W-2`).
 *
 * The expanded `PropertyPanel` renders these as the tab strip; the COLLAPSED inspector dock renders
 * the same list as a spine of icons, where clicking one expands the dock straight to that tab. They
 * must not be able to disagree — a spine offering a tab the panel does not have, or hiding one it
 * does, is worse than no spine at all — so the list is computed here rather than in either of them.
 *
 * Not in `lib/`: these carry React icon components, and `lib/` is the UI-free layer.
 */
export type InspectorTab = {
  value: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
};

const BASE_TABS: InspectorTab[] = [
  { value: "style", label: "Style", icon: Palette },
  { value: "axes", label: "Axes", icon: Ruler },
  { value: "legend", label: "Legend", icon: Tags },
  { value: "data", label: "Data", icon: Layers },
];

/** The first tab a freshly-opened inspector shows. */
export const DEFAULT_INSPECTOR_TAB = "style";

/**
 * Marks lists the scale bar + skill-emitted labels only; the Selom annotation-layer items (brackets,
 * free text, arrows) live in the Annotate tab, so an item never appears in both places.
 */
function hasMarks(spec: FigureSpec): boolean {
  const model = deriveFigureModel(spec);
  return !!model.scalebar || nonSelomAnnotationItems(spec).length > 0;
}

export function inspectorTabs(spec: FigureSpec | null | undefined): InspectorTab[] {
  if (!spec) return [...BASE_TABS, { value: "page", label: "Page", icon: FileText }];
  return [
    ...BASE_TABS,
    // Behind `annotationLayerEnabled` (off by default) until the layer has a selection model and
    // survives a re-run. Dropping it also keeps the strip at 6 columns, which it is laid out for.
    ...(annotationLayerEnabled
      ? [{ value: "annotate", label: "Annotate", icon: Asterisk } as InspectorTab]
      : []),
    ...(hasMarks(spec) ? [{ value: "marks", label: "Marks", icon: Shapes } as InspectorTab] : []),
    { value: "page", label: "Page", icon: FileText },
  ];
}
