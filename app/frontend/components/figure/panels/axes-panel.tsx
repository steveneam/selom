"use client";

import { Section, SelectField, SwitchField, TextField } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import { getAt, set } from "@/lib/figure/patch";

const SCALE_OPTIONS = [
  { value: "-", label: "Auto" },
  { value: "linear", label: "Linear" },
  { value: "log", label: "Log" },
];

const X_SIDE = [
  { value: "bottom", label: "Bottom" },
  { value: "top", label: "Top" },
];
const Y_SIDE = [
  { value: "left", label: "Left" },
  { value: "right", label: "Right" },
];

export function AxesPanel({ store, spec }: { store: FigureStore; spec: FigureSpec }) {
  const xTitle = getAt<string>(spec, "/layout/xaxis/title/text", "")!;
  const yTitle = getAt<string>(spec, "/layout/yaxis/title/text", "")!;
  const zeroLine = getAt<boolean>(spec, "/layout/xaxis/zeroline", false)!;
  const xType = getAt<string>(spec, "/layout/xaxis/type", "-")!;
  const yType = getAt<string>(spec, "/layout/yaxis/type", "-")!;
  const xSide = getAt<string>(spec, "/layout/xaxis/side", "bottom")!;
  const ySide = getAt<string>(spec, "/layout/yaxis/side", "left")!;

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

      {/* Gridline styling lives in the Style tab's "Axis gridlines" group; the zero reference line
          stays here with the axis structure. */}
      <Section title="Zero line">
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

      <Section title="Tick labels">
        <SelectField
          label="X-axis side"
          value={xSide}
          options={X_SIDE}
          onChange={(v) => store.commit([set("/layout/xaxis/side", v)])}
        />
        <SelectField
          label="Y-axis side"
          value={ySide}
          options={Y_SIDE}
          onChange={(v) => store.commit([set("/layout/yaxis/side", v)])}
        />
      </Section>
    </div>
  );
}
