"use client";

import { ColorField, Section, SelectField, SliderField } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure-spec";
import { COLORBAR_POSITIONS, COLORWAYS, findColorbarTrace } from "@/lib/figure-spec";
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

      <ColorbarControls store={store} spec={spec} />
    </div>
  );
}

/**
 * Colour-bar position presets + length — shown only for figures that actually have
 * a colour bar (heatmaps, colour-mapped scatters). Pairs with in-canvas dragging:
 * a preset snaps it back to a clean Right/Bottom/Left placement.
 */
function ColorbarControls({ store, spec }: { store: FigureStore; spec: FigureSpec }) {
  const cb = findColorbarTrace(spec);
  if (!cb) return null;
  const { base } = cb;

  const len = getAt<number>(spec, `${base}/len`, 1)!;
  const xa = getAt<string>(spec, `${base}/xanchor`, "");
  const ya = getAt<string>(spec, `${base}/yanchor`, "");
  const x = getAt<number>(spec, `${base}/x`, -99) ?? -99;
  const positionKey =
    Object.entries(COLORBAR_POSITIONS).find(
      ([, p]) => p.xanchor === xa && p.yanchor === ya && Math.abs(x - p.x) < 0.001,
    )?.[0] ?? "";

  return (
    <Section title="Colour bar">
      <SelectField
        label="Position"
        value={positionKey}
        placeholder="Custom"
        options={Object.entries(COLORBAR_POSITIONS).map(([k, p]) => ({ value: k, label: p.label }))}
        onChange={(k) => {
          const p = COLORBAR_POSITIONS[k];
          store.commit([
            set(`${base}/x`, p.x),
            set(`${base}/y`, p.y),
            set(`${base}/xanchor`, p.xanchor),
            set(`${base}/yanchor`, p.yanchor),
            set(`${base}/orientation`, p.orientation),
          ]);
        }}
      />
      <SliderField
        label="Length"
        value={Math.round(len * 100)}
        min={20}
        max={100}
        step={5}
        unit="%"
        store={store}
        build={(v) => [set(`${base}/len`, v / 100)]}
      />
    </Section>
  );
}
