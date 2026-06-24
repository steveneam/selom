"use client";

import { ColorField, Section, SelectField, SliderField, SwitchField } from "./controls";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure-spec";
import { COLORBAR_POSITIONS, COLORWAYS, findColorbarTrace } from "@/lib/figure-spec";
import { type FigureModel, seriesColorOps } from "@/lib/figure-model";
import { readTones, toneOps, zExtent } from "@/lib/heatmap/colorscale";
import { getAt, set, type Operation } from "@/lib/patch";

/** One decimal place for the colour-scale sliders. */
const r1 = (n: number) => Math.round(n * 10) / 10;

/** Plotly named colour scales offered for heatmap-style figures. */
const NAMED_SCALES = [
  "Viridis",
  "Cividis",
  "Plasma",
  "Inferno",
  "Magma",
  "Turbo",
  "Greys",
  "Blues",
  "Reds",
  "RdBu",
];

/**
 * The adaptive Style panel: control groups render CONDITIONALLY from the derived
 * FigureModel's capabilities, so a line grid never shows point-size and a heatmap never
 * shows markers. Each group edits the channel that actually paints the figure.
 */
export function StylePanel({
  store,
  spec,
  model,
}: {
  store: FigureStore;
  spec: FigureSpec;
  model: FigureModel;
}) {
  const { capabilities: cap } = model;

  return (
    <div className="space-y-6">
      {cap.markers && <MarkerControls store={store} spec={spec} model={model} />}
      {cap.lines && <LineControls store={store} spec={spec} model={model} />}
      {cap.colorscale && model.heatmapTraceIndices.length > 0 && (
        <ColorscaleControls store={store} spec={spec} model={model} />
      )}

      <PaletteControls store={store} spec={spec} model={model} />

      <Section title="Background">
        <ColorField
          label="Plot area"
          value={getAt<string>(spec, "/layout/plot_bgcolor", "#ffffff")!}
          onCommit={(v) => store.commit([set("/layout/plot_bgcolor", v)])}
        />
        <ColorField
          label="Paper"
          value={getAt<string>(spec, "/layout/paper_bgcolor", "#ffffff")!}
          onCommit={(v) => store.commit([set("/layout/paper_bgcolor", v)])}
        />
      </Section>

      <ColorbarControls store={store} spec={spec} model={model} />
    </div>
  );
}

/** Point size + opacity — only for figures with marker traces (scatter/umap/pca/volcano). */
function MarkerControls({
  store,
  spec,
  model,
}: {
  store: FigureStore;
  spec: FigureSpec;
  model: FigureModel;
}) {
  const i0 = model.markerTraceIndices[0];
  const markerSize = getAt<number>(spec, `/data/${i0}/marker/size`, 7)!;
  const markerOpacity = getAt<number>(spec, `/data/${i0}/marker/opacity`, 0.9)!;
  const apply = (leaf: string, v: number) =>
    model.markerTraceIndices.map((i) => set(`/data/${i}/marker/${leaf}`, v));

  return (
    <Section title="Markers">
      <SliderField
        label="Point size"
        value={markerSize}
        min={2}
        max={24}
        store={store}
        build={(v) => apply("size", v)}
      />
      <SliderField
        label="Opacity"
        value={Math.round(markerOpacity * 100)}
        min={10}
        max={100}
        step={5}
        unit="%"
        store={store}
        build={(v) => apply("opacity", v / 100)}
      />
    </Section>
  );
}

/** Line width — only for figures with line traces (the ERG grid, trajectory, QC). */
function LineControls({
  store,
  spec,
  model,
}: {
  store: FigureStore;
  spec: FigureSpec;
  model: FigureModel;
}) {
  const i0 = model.lineTraceIndices[0];
  const lineWidth = getAt<number>(spec, `/data/${i0}/line/width`, 1.5)!;

  return (
    <Section title="Lines">
      <SliderField
        label="Line width"
        value={lineWidth}
        min={0.5}
        max={8}
        step={0.5}
        store={store}
        build={(v) => model.lineTraceIndices.map((i) => set(`/data/${i}/line/width`, v))}
      />
    </Section>
  );
}

/**
 * Named colour scale + reverse + diverging re-tone (midpoint / saturation) — for heatmaps
 * (heatmap-spec.md §D). The two sliders re-map the EXISTING z-matrix live (an instant, undoable
 * figure-store edit, no re-run) so faint or saturated cells read clearly; they share state with the
 * canvas colour-bar drag (drag the bar top/bottom/middle). Inference-driven, like the scale picker.
 */
function ColorscaleControls({
  store,
  spec,
  model,
}: {
  store: FigureStore;
  spec: FigureSpec;
  model: FigureModel;
}) {
  const idx = model.heatmapTraceIndices;
  const i0 = idx[0];
  if (i0 === undefined) return null;
  const rawScale = getAt<unknown>(spec, `/data/${i0}/colorscale`);
  const scaleVal = typeof rawScale === "string" ? rawScale : "";
  const reversed = getAt<boolean>(spec, `/data/${i0}/reversescale`, false)!;
  const apply = (leaf: string, v: unknown) => idx.map((i) => set(`/data/${i}/${leaf}`, v));

  // Live re-tone (midpoint + symmetric saturation): bounds come from the z data extent.
  const tones = readTones(spec);
  const ext = zExtent(spec);
  const sat = tones ? (tones.zmax - tones.zmin) / 2 : 0;
  const maxAbs = tones && ext ? Math.max(ext.max - tones.zmid, tones.zmid - ext.min, 0.5) : 1;

  return (
    <Section title="Colour scale">
      <SelectField
        label="Scale"
        value={scaleVal}
        placeholder="Custom"
        options={NAMED_SCALES.map((s) => ({ value: s, label: s }))}
        onChange={(v) => store.commit(apply("colorscale", v))}
      />
      <SwitchField
        label="Reverse"
        checked={reversed}
        onChange={(v) => store.commit(apply("reversescale", v))}
      />
      {tones && ext && (
        <>
          <SliderField
            label="Midpoint"
            value={r1(tones.zmid)}
            min={r1(ext.min)}
            max={r1(ext.max)}
            step={0.1}
            store={store}
            build={(v) => toneOps(idx, { zmid: v })}
          />
          <SliderField
            label="Saturation ±"
            value={r1(sat)}
            min={0.2}
            max={r1(maxAbs)}
            step={0.1}
            store={store}
            build={(v) => toneOps(idx, { zmin: r1(tones.zmid - v), zmax: r1(tones.zmid + v) })}
          />
        </>
      )}
    </Section>
  );
}

/**
 * Palette: swaps `layout.colorway` AND rewrites the real colour channel of every series
 * that already carries an EXPLICIT colour (ERG's 6 line conditions, coloured scatters).
 * Series that rely on the colourway (no explicit colour) are left for colorway to drive.
 */
function PaletteControls({
  store,
  spec,
  model,
}: {
  store: FigureStore;
  spec: FigureSpec;
  model: FigureModel;
}) {
  const currentColorway = JSON.stringify(getAt<string[]>(spec, "/layout/colorway", []));
  const colorwayKey =
    Object.entries(COLORWAYS).find(([, v]) => JSON.stringify(v.colors) === currentColorway)?.[0] ??
    "okabeito";

  const explicitSeries = model.series.filter(
    (s) => s.colorChannels.length > 0 && !s.perPoint && s.color != null,
  );

  const applyPalette = (key: string) => {
    const colors = COLORWAYS[key].colors;
    const ops: Operation[] = [set("/layout/colorway", colors)];
    explicitSeries.forEach((s, idx) => ops.push(...seriesColorOps(s, colors[idx % colors.length])));
    store.commit(ops);
  };

  return (
    <Section title="Palette">
      <SelectField
        label="Colour palette"
        value={colorwayKey}
        options={Object.entries(COLORWAYS).map(([k, v]) => ({ value: k, label: v.label }))}
        onChange={applyPalette}
      />
      <div className="flex gap-1">
        {COLORWAYS[colorwayKey].colors.map((c) => (
          <span key={c} className="h-4 flex-1 rounded-sm" style={{ backgroundColor: c }} title={c} />
        ))}
      </div>
      {explicitSeries.length > 0 && (
        <p className="text-[11px] leading-relaxed text-muted-foreground/80">
          Applies to the {explicitSeries.length} coloured series. Recolour one at a time in the
          Data tab.
        </p>
      )}
    </Section>
  );
}

/**
 * Colour-bar position presets + length — shown only for figures that actually have
 * a colour bar (heatmaps, colour-mapped scatters). Pairs with in-canvas dragging:
 * a preset snaps it back to a clean Right/Bottom/Left placement.
 */
function ColorbarControls({
  store,
  spec,
  model,
}: {
  store: FigureStore;
  spec: FigureSpec;
  model: FigureModel;
}) {
  if (!model.capabilities.colorbar) return null;
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
