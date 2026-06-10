"use client";

import { Section, SelectField, SwitchField, TextField } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure-spec";
import { getAt, set } from "@/lib/patch";

const SCALE_OPTIONS = [
  { value: "-", label: "Auto" },
  { value: "linear", label: "Linear" },
  { value: "log", label: "Log" },
];

export function AxesPanel({ store, spec }: { store: FigureStore; spec: FigureSpec }) {
  const xTitle = getAt<string>(spec, "/layout/xaxis/title/text", "")!;
  const yTitle = getAt<string>(spec, "/layout/yaxis/title/text", "")!;
  const showGrid = getAt<boolean>(spec, "/layout/xaxis/showgrid", true)!;
  const zeroLine = getAt<boolean>(spec, "/layout/xaxis/zeroline", false)!;
  const xType = getAt<string>(spec, "/layout/xaxis/type", "-")!;
  const yType = getAt<string>(spec, "/layout/yaxis/type", "-")!;

  return (
    <div className="space-y-6">
      <Section title="Titles">
        <TextField
          label="X-axis title"
          value={xTitle}
          placeholder="e.g. UMAP 1"
          onCommit={(v) => store.commit([set("/layout/xaxis/title/text", v)])}
        />
        <TextField
          label="Y-axis title"
          value={yTitle}
          placeholder="e.g. UMAP 2"
          onCommit={(v) => store.commit([set("/layout/yaxis/title/text", v)])}
        />
      </Section>

      <Section title="Gridlines">
        <SwitchField
          label="Show gridlines"
          checked={showGrid}
          onChange={(v) =>
            store.commit([set("/layout/xaxis/showgrid", v), set("/layout/yaxis/showgrid", v)])
          }
        />
        <SwitchField
          label="Zero lines"
          checked={zeroLine}
          onChange={(v) =>
            store.commit([set("/layout/xaxis/zeroline", v), set("/layout/yaxis/zeroline", v)])
          }
        />
      </Section>

      <Section title="Scale">
        <SelectField
          label="X scale"
          value={xType}
          options={SCALE_OPTIONS}
          onChange={(v) => store.commit([set("/layout/xaxis/type", v)])}
        />
        <SelectField
          label="Y scale"
          value={yType}
          options={SCALE_OPTIONS}
          onChange={(v) => store.commit([set("/layout/yaxis/type", v)])}
        />
      </Section>
    </div>
  );
}
