"use client";

import { useEffect, useMemo, useState } from "react";
import { Asterisk, FileText, Layers, Palette, Ruler, Shapes, Tags } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { FigureStore } from "@/hooks/use-figure-store";
import { deriveFigureModel, seriesForTrace } from "@/lib/figure/figure-model";
import { nonSelomAnnotationItems } from "@/lib/figure/annotations";
import { annotationLayerEnabled } from "@/lib/config/env";
import { StylePanel } from "./panels/style-panel";
import { AxesPanel } from "./panels/axes-panel";
import { LegendPanel } from "./panels/legend-panel";
import { DataPanel } from "./panels/data-panel";
import { MarksPanel } from "./panels/marks-panel";
import { AnnotationsPanel } from "./panels/annotations-panel";
import { PagePanel } from "./panels/page-panel";
import { PaneBoundary } from "@/components/ui/error-boundary";
import { PaneShell } from "@/components/ui/pane-shell";

const BASE_TABS = [
  { value: "style", label: "Style", icon: Palette },
  { value: "axes", label: "Axes", icon: Ruler },
  { value: "legend", label: "Legend", icon: Tags },
  { value: "data", label: "Data", icon: Layers },
] as const;

export function PropertyPanel({
  store,
  selection,
}: {
  store: FigureStore;
  /** Click-to-select from the canvas (P3 §3.4): focus the clicked trace's series in Data. The
   *  nonce makes re-clicking the same trace re-fire the focus. */
  selection?: { trace: number; nonce: number } | null;
}) {
  const spec = store.spec;
  // The adaptive inspector is driven by the derived model (inference-first); memoised so
  // it recomputes only when the spec changes. Style + Data + Marks render from it.
  const model = useMemo(() => (spec ? deriveFigureModel(spec) : null), [spec]);
  // Marks lists the scale bar + skill-emitted labels only — the Selom annotation-layer items (brackets,
  // free text, arrows) live in the always-present Annotate tab, so an item never shows in both places.
  const hasMarks = !!model?.scalebar || (spec ? nonSelomAnnotationItems(spec).length > 0 : false);

  const [tab, setTab] = useState("style");
  const [focusedSeriesKey, setFocusedSeriesKey] = useState<string | null>(null);

  // A canvas click → focus that trace's series in the Data tab.
  useEffect(() => {
    if (!selection || !model) return;
    const series = seriesForTrace(model, selection.trace);
    if (!series) return;
    setFocusedSeriesKey(series.key);
    setTab("data");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection?.nonce]);

  // Stable slot when there's no figure to inspect (Task B3): render the inspector's outer shape with
  // an empty state instead of vanishing to `null`, so the panel never collapses out of the layout.
  if (!spec || !model) {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <div className="border-b border-border px-3 py-2.5">
          <span className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Inspector
          </span>
        </div>
        <PaneShell state={{ status: "empty", message: "No figure open — open a figure to inspect it." }} className="m-3" />
      </div>
    );
  }

  // The hand-annotation tab is behind `annotationLayerEnabled` (off by default) until the layer has a
  // selection model and survives a re-run — see lib/config/env.ts. Dropping it also returns the tab
  // strip to 6 columns, which is what it was laid out for.
  const annotateTab = { value: "annotate", label: "Annotate", icon: Asterisk } as const;
  const pageTab = { value: "page", label: "Page", icon: FileText } as const;
  const marksTab = { value: "marks", label: "Marks", icon: Shapes } as const;
  const tabs = [
    ...BASE_TABS,
    ...(annotationLayerEnabled ? [annotateTab] : []),
    ...(hasMarks ? [marksTab] : []),
    pageTab,
  ];

  return (
    <Tabs value={tab} onValueChange={setTab} className="flex h-full min-h-0 flex-col">
      <div className="border-b border-border px-3 py-2.5">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Inspector
          </span>
        </div>
        <TabsList
          className="grid h-auto w-full bg-muted/50 p-1"
          style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }}
        >
          {tabs.map(({ value, label, icon: Icon }) => (
            <TabsTrigger key={value} value={value} className="h-auto flex-col gap-1 py-1.5">
              <Icon />
              <span className="text-[10px] leading-none">{label}</span>
            </TabsTrigger>
          ))}
        </TabsList>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        {/* Each tab panel is isolated (Task B1): a panel that throws while reading a
            capability-specific shape (e.g. colour-scale on a heatmap-less spec) shows a local
            fallback instead of unmounting the whole inspector. `spec` is the reset key — a figure
            switch (new spec) auto-clears a stuck panel. */}
        <div className="p-4">
          <TabsContent value="style">
            <PaneBoundary label="style" resetKeys={[spec]}>
              <StylePanel store={store} spec={spec} model={model} />
            </PaneBoundary>
          </TabsContent>
          <TabsContent value="axes">
            <PaneBoundary label="axes" resetKeys={[spec]}>
              <AxesPanel store={store} spec={spec} />
            </PaneBoundary>
          </TabsContent>
          <TabsContent value="legend">
            <PaneBoundary label="legend" resetKeys={[spec]}>
              <LegendPanel store={store} spec={spec} />
            </PaneBoundary>
          </TabsContent>
          <TabsContent value="data">
            <PaneBoundary label="data" resetKeys={[spec]}>
              <DataPanel store={store} spec={spec} model={model} focusedSeriesKey={focusedSeriesKey} />
            </PaneBoundary>
          </TabsContent>
          {annotationLayerEnabled && (
            <TabsContent value="annotate">
              <PaneBoundary label="annotate" resetKeys={[spec]}>
                <AnnotationsPanel store={store} spec={spec} />
              </PaneBoundary>
            </TabsContent>
          )}
          {hasMarks && (
            <TabsContent value="marks">
              <PaneBoundary label="marks" resetKeys={[spec]}>
                <MarksPanel store={store} spec={spec} model={model} />
              </PaneBoundary>
            </TabsContent>
          )}
          <TabsContent value="page">
            <PaneBoundary label="page" resetKeys={[spec]}>
              <PagePanel store={store} spec={spec} />
            </PaneBoundary>
          </TabsContent>
        </div>
      </ScrollArea>
    </Tabs>
  );
}
