"use client";

import { Section, SelectField, SwitchField } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure-spec";
import { LEGEND_POSITIONS } from "@/lib/figure-spec";
import { getAt, legendPosOps, set } from "@/lib/patch";

const ORIENTATION = [
  { value: "v", label: "Vertical" },
  { value: "h", label: "Horizontal" },
];

export function LegendPanel({ store, spec }: { store: FigureStore; spec: FigureSpec }) {
  const show = getAt<boolean>(spec, "/layout/showlegend", spec.data.length > 1)!;
  const orientation = getAt<string>(spec, "/layout/legend/orientation", "v")!;

  const xa = getAt<string>(spec, "/layout/legend/xanchor", "");
  const ya = getAt<string>(spec, "/layout/legend/yanchor", "");
  const positionKey =
    Object.entries(LEGEND_POSITIONS).find(
      ([, p]) =>
        p.xanchor === xa &&
        p.yanchor === ya &&
        Math.abs((getAt<number>(spec, "/layout/legend/x", -99) ?? -99) - p.x) < 0.001,
    )?.[0] ?? "";

  return (
    <div className="space-y-6">
      <Section title="Legend">
        <SwitchField
          label="Show legend"
          checked={show}
          onChange={(v) => store.commit([set("/layout/showlegend", v)])}
        />
        <SelectField
          label="Orientation"
          value={orientation}
          options={ORIENTATION}
          onChange={(v) => store.commit([set("/layout/legend/orientation", v)])}
        />
        <SelectField
          label="Position"
          value={positionKey}
          placeholder="Custom"
          options={Object.entries(LEGEND_POSITIONS).map(([k, p]) => ({ value: k, label: p.label }))}
          onChange={(k) => store.commit(legendPosOps(LEGEND_POSITIONS[k]))}
        />
      </Section>
    </div>
  );
}
