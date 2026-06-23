"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, Layers, Palette, Ruler, Shapes, Tags } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { FigureStore } from "@/hooks/use-figure-store";
import { annotationItems, deriveFigureModel, seriesForTrace } from "@/lib/figure-model";
import { StylePanel } from "./panels/style-panel";
import { AxesPanel } from "./panels/axes-panel";
import { LegendPanel } from "./panels/legend-panel";
import { DataPanel } from "./panels/data-panel";
import { MarksPanel } from "./panels/marks-panel";
import { PagePanel } from "./panels/page-panel";

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
  const hasMarks = !!model?.scalebar || (spec ? annotationItems(spec).length > 0 : false);

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

  if (!spec || !model) return null;

  const tabs = hasMarks
    ? [...BASE_TABS, { value: "marks", label: "Marks", icon: Shapes }, { value: "page", label: "Page", icon: FileText }]
    : [...BASE_TABS, { value: "page", label: "Page", icon: FileText }];

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
        <div className="p-4">
          <TabsContent value="style">
            <StylePanel store={store} spec={spec} model={model} />
          </TabsContent>
          <TabsContent value="axes">
            <AxesPanel store={store} spec={spec} />
          </TabsContent>
          <TabsContent value="legend">
            <LegendPanel store={store} spec={spec} />
          </TabsContent>
          <TabsContent value="data">
            <DataPanel store={store} spec={spec} model={model} focusedSeriesKey={focusedSeriesKey} />
          </TabsContent>
          {hasMarks && (
            <TabsContent value="marks">
              <MarksPanel store={store} spec={spec} model={model} />
            </TabsContent>
          )}
          <TabsContent value="page">
            <PagePanel store={store} spec={spec} />
          </TabsContent>
        </div>
      </ScrollArea>
    </Tabs>
  );
}
