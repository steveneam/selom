"use client";

import { ColorField, Section, SelectField, SliderField } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure-spec";
import { COLORWAYS } from "@/lib/figure-spec";
import { getAt, set } from "@/lib/patch";

export function StylePanel({ store, spec }: { store: FigureStore; spec: FigureSpec }) {
  const traceCount = spec.data.length;
  const markerSize = getAt<number>(spec, "/data/0/marker/size", 7)!;
  const markerOpacity = getAt<number>(spec, "/data/0/marker/opacity", 0.9)!;
  const plotBg = getAt<string>(spec, "/layout/plot_bgcolor", "#ffffff")!;
  const paperBg = getAt<string>(spec, "/layout/paper_bgcolor", "#ffffff")!;

  const currentColorway = JSON.stringify(getAt<string[]>(spec, "/layout/colorway", []));
  const colorwayKey =
    Object.entries(COLORWAYS).find(([, v]) => JSON.stringify(v.colors) === currentColorway)?.[0] ??
    "okabeito";

  const allTraces = (build: (i: number) => ReturnType<typeof set>) =>
    Array.from({ length: traceCount }, (_, i) => build(i));

  return (
    <div className="space-y-6">
      <Section title="Markers">
        <SliderField
          label="Point size"
          value={markerSize}
          min={2}
          max={24}
          store={store}
          build={(v) => allTraces((i) => set(`/data/${i}/marker/size`, v))}
        />
        <SliderField
          label="Opacity"
          value={Math.round(markerOpacity * 100)}
          min={10}
          max={100}
          step={5}
          unit="%"
          store={store}
          build={(v) => allTraces((i) => set(`/data/${i}/marker/opacity`, v / 100))}
        />
      </Section>

      <Section title="Palette">
        <SelectField
          label="Colour palette"
          value={colorwayKey}
          options={Object.entries(COLORWAYS).map(([k, v]) => ({ value: k, label: v.label }))}
          onChange={(k) => store.commit([set("/layout/colorway", COLORWAYS[k].colors)])}
        />
        <div className="flex gap-1">
          {COLORWAYS[colorwayKey].colors.map((c) => (
            <span
              key={c}
              className="h-4 flex-1 rounded-sm"
              style={{ backgroundColor: c }}
              title={c}
            />
          ))}
        </div>
      </Section>

      <Section title="Background">
        <ColorField
          label="Plot area"
          value={plotBg}
          onCommit={(v) => store.commit([set("/layout/plot_bgcolor", v)])}
        />
        <ColorField
          label="Paper"
          value={paperBg}
          onCommit={(v) => store.commit([set("/layout/paper_bgcolor", v)])}
        />
      </Section>
    </div>
  );
}
