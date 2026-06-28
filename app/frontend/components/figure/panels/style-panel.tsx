"use client";

import * as React from "react";
import { ColorField, Section, SelectField, SliderField, SwitchField } from "./controls";
import { Input } from "@/components/ui/input";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import { COLORBAR_POSITIONS, COLORWAYS, findColorbarTrace } from "@/lib/figure/figure-spec";
import { type FigureModel, seriesColorOps } from "@/lib/figure/figure-model";
import { heatmapColorscaleState } from "@/lib/figure/contract";
import { readTones, toneOps, zExtent } from "@/lib/heatmap/colorscale";
import {
  type LabelRow,
  annotationTrackNames,
  colorLabelsByGroupOps,
  hasRowDendrogram,
  labelColorBy,
  labelRows,
  labelSideOps,
  mainHeatmapIndex,
  renameLabelOps,
  setHighlightOps,
} from "@/lib/heatmap/labels";
import {
  colTreeFraction,
  hasColTree,
  hasDendrogram,
  hasRowTree,
  maxDistance,
  rowTreeFraction,
  setColTreeOps,
  setRowTreeOps,
  tipGap,
  tipLengthOps,
  type TipAxis,
} from "@/lib/heatmap/dendrogram";
import { getAt, set, type Operation } from "@/lib/figure/patch";
import { cn } from "@/lib/ui/cn";

/** One decimal place for the colour-scale sliders. */
const r1 = (n: number) => Math.round(n * 10) / 10;

/** Sentinel for the "off" choice of the group-colouring select — Radix Select rejects an empty-string
 *  item value, and it can't collide with a real annotation-column name. */
const COLOR_BY_NONE = "__none__";

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
  // The heatmap colour-scale section's fail-safe state (Task B2): a heatmap trace → the controls; a
  // declared-heatmap-but-traceless spec → an explicit "no heatmap trace" note (never a crash); a
  // non-heatmap colorscale (trajectory/markers continuous colour) → hidden, exactly as before.
  const colorscaleState = heatmapColorscaleState({
    heatmapTones: cap.heatmapTones,
    heatmapLabels: cap.heatmapLabels,
    heatmapTraceCount: model.heatmapTraceIndices.length,
  });

  return (
    <div className="space-y-6">
      {cap.markers && <MarkerControls store={store} spec={spec} model={model} />}
      {cap.lines && <LineControls store={store} spec={spec} model={model} />}
      {colorscaleState === "ready" && <ColorscaleControls store={store} spec={spec} model={model} />}
      {colorscaleState === "empty" && (
        <Section title="Colour scale">
          <p className="text-[11px] leading-relaxed text-muted-foreground/70">
            No heatmap trace in this figure.
          </p>
        </Section>
      )}
      {model.heatmapTraceIndices.length > 0 && hasDendrogram(spec) && (
        <DendrogramControls store={store} spec={spec} />
      )}
      {cap.heatmapLabels && model.heatmapTraceIndices.length > 0 && (
        <LabelsControls store={store} spec={spec} />
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
 * Dendrogram: how much room the row / column clustering trees get (owner request 2026-06-25). An
 * instant, undoable layout edit — it re-proportions the gutter vs heatmap domains (no re-run), so a
 * bigger tree draws the same branches more spread out and the connections read clearly. Shown only
 * for the trees actually present.
 */
function DendrogramControls({ store, spec }: { store: FigureStore; spec: FigureSpec }) {
  const showRow = hasRowTree(spec);
  const showCol = hasColTree(spec);
  return (
    <Section title="Dendrogram">
      <p className="text-[11px] leading-relaxed text-muted-foreground/80">
        Give a tree more room to spread its branches — the clustering and data are unchanged.
      </p>
      {showRow && (
        <SliderField
          label="Row tree width"
          value={Math.round(rowTreeFraction(spec) * 100)}
          min={8}
          max={45}
          step={1}
          unit="%"
          store={store}
          build={(v) => setRowTreeOps(spec, v / 100)}
        />
      )}
      {showCol && (
        <SliderField
          label="Column tree height"
          value={Math.round(colTreeFraction(spec) * 100)}
          min={8}
          max={45}
          step={1}
          unit="%"
          store={store}
          build={(v) => setColTreeOps(spec, v / 100)}
        />
      )}
      <p className="text-[11px] leading-relaxed text-muted-foreground/80">
        Lengthen the short leaf end-stubs between the branches and the heatmap — uniformly here, or one
        at a time by dragging a stub on the figure (hover to highlight it).
      </p>
      {showRow && <LeafTipLever store={store} spec={spec} axis="row" label="Row leaf tip length" />}
      {showCol && <LeafTipLever store={store} spec={spec} axis="col" label="Column leaf tip length" />}
    </Section>
  );
}

/**
 * The uniform "Leaf tip length" lever for one tree (dendrogram-tips-spec.md). Drives `meta.selom.
 * dendrogramTips.<axis>.gap` — an instant, undoable layout/meta edit the canvas projects at render
 * time (`applyDendrogramTips`), so the stubs grow without a re-run and the canonical trace is untouched.
 * Shown as 0–100 % of a sensible cap (half the tree's height) so the owner thinks in "stub length".
 */
function LeafTipLever({
  store,
  spec,
  axis,
  label,
}: {
  store: FigureStore;
  spec: FigureSpec;
  axis: TipAxis;
  label: string;
}) {
  const cap = Math.max(1e-3, maxDistance(spec, axis) * 0.5);
  const pct = Math.round((tipGap(spec, axis) / cap) * 100);
  return (
    <SliderField
      label={label}
      value={Math.min(100, Math.max(0, pct))}
      min={0}
      max={100}
      step={1}
      unit="%"
      store={store}
      build={(v) => tipLengthOps(spec, axis, (v / 100) * cap)}
    />
  );
}

/**
 * Labels: rename any gene (row) / sample (column) display label, highlight genes of interest (red),
 * and move the gene labels to a side (heatmap-clustermap-spec §6–8). All provenance-SAFE cosmetic
 * edits — they write the axis ticktext / side (instant, undoable, no re-run); the data, run params
 * and methods are untouched, the original stays in the hover, and the canonical IDs stay the source
 * of truth. Genes are searchable (a clustermap can show up to 100).
 */
function LabelsControls({ store, spec }: { store: FigureStore; spec: FigureSpec }) {
  const [query, setQuery] = React.useState("");
  if (mainHeatmapIndex(spec) < 0) return null;
  const samples = labelRows(spec, "x");
  const genes = labelRows(spec, "y");
  const q = query.trim().toLowerCase();
  const shownGenes = q
    ? genes.filter((g) => g.text.toLowerCase().includes(q) || g.original.toLowerCase().includes(q))
    : genes;

  // Gene labels are pinned to the right when a row dendrogram owns the left gutter (035617/035636);
  // without a tree the side is a free choice.
  const treePinned = hasRowDendrogram(spec);
  const geneSide = treePinned ? "right" : getAt<string>(spec, "/layout/yaxis/side", "left")!;

  // Colour the sample labels by an annotation track's group (035617/035636) — instant, reuses the
  // strip colours. Only offered when at least one annotation track is present. The "off" choice uses a
  // sentinel value (Radix Select forbids an empty-string item value).
  const tracks = annotationTrackNames(spec);
  const colorBy = labelColorBy(spec, "x") ?? COLOR_BY_NONE;

  return (
    <Section title="Labels">
      <p className="text-[11px] leading-relaxed text-muted-foreground/80">
        Renaming is display-only — the data, parameters and methods are untouched and the original
        label stays in the hover.
      </p>

      {samples.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
            Samples · {samples.length}
          </h4>
          {tracks.length > 0 && (
            <SelectField
              label="Colour labels by group"
              value={colorBy}
              options={[
                { value: COLOR_BY_NONE, label: "None" },
                ...tracks.map((t) => ({ value: t, label: t })),
              ]}
              onChange={(v) =>
                store.commit(colorLabelsByGroupOps(spec, "x", v === COLOR_BY_NONE ? null : v))
              }
            />
          )}
          {samples.map((r) => (
            <RenameRow
              key={`x${r.index}`}
              row={r}
              onCommit={(t) => store.commit(renameLabelOps(spec, "x", r.index, t))}
            />
          ))}
        </div>
      )}

      {genes.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
            Genes · {genes.length}
          </h4>
          {treePinned ? (
            <p className="text-[11px] text-muted-foreground/70">
              Gene labels sit on the right (the row dendrogram owns the left).
            </p>
          ) : (
            <SelectField
              label="Label side"
              value={geneSide === "right" ? "right" : "left"}
              options={[
                { value: "left", label: "Left" },
                { value: "right", label: "Right" },
              ]}
              onChange={(v) => store.commit(labelSideOps("y", v as "left" | "right"))}
            />
          )}
          {genes.length > 8 && (
            <Input
              value={query}
              placeholder="Filter genes…"
              className="h-7 text-xs"
              onChange={(e) => setQuery(e.target.value)}
            />
          )}
          <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
            {shownGenes.map((r) => (
              <RenameRow
                key={`y${r.index}`}
                row={r}
                onCommit={(t) => store.commit(renameLabelOps(spec, "y", r.index, t))}
                highlighted={r.highlighted}
                onToggleHighlight={(next) => store.commit(setHighlightOps(spec, "y", r.index, next))}
              />
            ))}
            {shownGenes.length === 0 && (
              <p className="text-[11px] text-muted-foreground/70">No genes match “{query}”.</p>
            )}
          </div>
        </div>
      )}
    </Section>
  );
}

/**
 * One compact rename row: an input pre-filled with the current label + a muted "was …" when changed,
 * plus an optional gene-of-interest highlight toggle (red, 035617). Uncontrolled (commit on blur /
 * Enter) and `key`-remounted on the committed text, so an external change (undo, reset) re-seeds it
 * without a setState-in-effect.
 */
function RenameRow({
  row,
  onCommit,
  highlighted,
  onToggleHighlight,
}: {
  row: LabelRow;
  onCommit: (text: string) => void;
  highlighted?: boolean;
  onToggleHighlight?: (next: boolean) => void;
}) {
  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-1.5">
        <Input
          key={row.text}
          defaultValue={row.text}
          placeholder={row.original}
          className="h-7 flex-1 text-xs"
          aria-label={`Rename ${row.original}`}
          onBlur={(e) => {
            if (e.target.value !== row.text) onCommit(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          }}
        />
        {onToggleHighlight && (
          <button
            type="button"
            onClick={() => onToggleHighlight(!highlighted)}
            aria-pressed={!!highlighted}
            title={highlighted ? "Remove highlight" : "Highlight as a gene of interest"}
            className={cn(
              "grid size-7 shrink-0 place-items-center rounded-md border text-[13px] leading-none transition-colors",
              highlighted
                ? "border-red-500/70 bg-red-500/10 text-red-600"
                : "border-input text-muted-foreground/50 hover:text-foreground",
            )}
          >
            ●
          </button>
        )}
      </div>
      {row.text !== row.original && (
        <p className="truncate pl-1 text-[10px] text-muted-foreground/70" title={row.original}>
          was {row.original}
        </p>
      )}
    </div>
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
