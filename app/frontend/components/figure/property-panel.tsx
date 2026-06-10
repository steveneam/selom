"use client";

import { FileText, Layers, Palette, Ruler, Tags } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { FigureStore } from "@/hooks/use-figure-store";
import { StylePanel } from "./panels/style-panel";
import { AxesPanel } from "./panels/axes-panel";
import { LegendPanel } from "./panels/legend-panel";
import { DataPanel } from "./panels/data-panel";
import { PagePanel } from "./panels/page-panel";

const TABS = [
  { value: "style", label: "Style", icon: Palette },
  { value: "axes", label: "Axes", icon: Ruler },
  { value: "legend", label: "Legend", icon: Tags },
  { value: "data", label: "Data", icon: Layers },
  { value: "page", label: "Page", icon: FileText },
] as const;

export function PropertyPanel({ store }: { store: FigureStore }) {
  const spec = store.spec;
  if (!spec) return null;

  return (
    <Tabs defaultValue="style" className="flex h-full min-h-0 flex-col">
      <div className="border-b border-border px-3 py-2.5">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Inspector
          </span>
        </div>
        <TabsList className="grid h-auto w-full grid-cols-5 bg-muted/50 p-1">
          {TABS.map(({ value, label, icon: Icon }) => (
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
            <StylePanel store={store} spec={spec} />
          </TabsContent>
          <TabsContent value="axes">
            <AxesPanel store={store} spec={spec} />
          </TabsContent>
          <TabsContent value="legend">
            <LegendPanel store={store} spec={spec} />
          </TabsContent>
          <TabsContent value="data">
            <DataPanel store={store} spec={spec} />
          </TabsContent>
          <TabsContent value="page">
            <PagePanel store={store} spec={spec} />
          </TabsContent>
        </div>
      </ScrollArea>
    </Tabs>
  );
}
