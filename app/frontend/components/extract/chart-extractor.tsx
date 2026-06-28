"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, ImageDown, ScanLine, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dropzone } from "@/components/project/dropzone";
import { EditorWorkspace } from "@/components/figure/editor-workspace";
import { StatsPanel } from "@/components/project/stats-panel";
import { useFigureStore } from "@/hooks/use-figure-store";
import {
  EMPTY_CALIBRATION,
  buildExtractParams,
  calibrationComplete,
  calibrationDegenerate,
  type AxisKey,
  type CalibrationState,
  type ChartForm,
} from "@/lib/extract/calibrate";
import { extractChart, type ExtractChartResponse } from "@/lib/extract/api";
import { CalibrationCanvas, type ActiveRef } from "./calibration-canvas";
import { ExtractControls, type ExtractOptionsState } from "./extract-controls";

const EMPTY_OPTIONS: ExtractOptionsState = { color: "", labels: "", seriesName: "", xName: "", yName: "" };

const ORDER: ActiveRef[] = [
  { axis: "x", index: 0 },
  { axis: "x", index: 1 },
  { axis: "y", index: 0 },
  { axis: "y", index: 1 },
];

function cloneCalib(c: CalibrationState): CalibrationState {
  return { ...c, x: [c.x[0], c.x[1]], y: [c.y[0], c.y[1]] };
}

/** The first reference (in X1·X2·Y1·Y2 order) not yet placed, to guide targeting. */
function firstUnplaced(c: CalibrationState): ActiveRef | null {
  return ORDER.find((s) => !c[s.axis][s.index]) ?? null;
}

/** Entry context when the picker is opened from a Reproduction panel ("Digitize this panel"). */
export interface DigitizeOrigin {
  imageUrl: string; // proxied URL of the lifted panel (/api/repro-assets/...)
  slug: string; // paper slug, for the back link
  panelKey: string; // e.g. "4C"
  form: ChartForm;
}

/**
 * "Recover data from a figure" — the X4 chart-extractor surface. Drop a published
 * bar/line/scatter panel, mark two reference ticks per axis (WebPlotDigitizer-style),
 * and the backend reads back the underlying numbers as an editable figure + Statistics
 * table — landing in the real figure editor, exactly like a skill's output.
 *
 * `origin` (★D bridge) pre-loads the lifted panel from a Reproduction figure. Digitizing is
 * vision-grade and is NEVER part of the Reproducibility Score — the banner says so.
 */
export function ChartExtractor({ origin }: { origin?: DigitizeOrigin } = {}) {
  const [image, setImage] = React.useState<File | null>(null);
  const [src, setSrc] = React.useState<string | null>(null);
  const [dims, setDims] = React.useState<{ naturalW: number; naturalH: number } | null>(null);
  const [form, setForm] = React.useState<ChartForm>(origin?.form ?? "bar");
  const [calib, setCalib] = React.useState<CalibrationState>(EMPTY_CALIBRATION);
  const [active, setActive] = React.useState<ActiveRef | null>(null);
  const [options, setOptions] = React.useState<ExtractOptionsState>(EMPTY_OPTIONS);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<ExtractChartResponse | null>(null);
  const store = useFigureStore();
  const urlRef = React.useRef<string | null>(null);

  // Revoke the object URL on unmount so the dropped image isn't leaked.
  React.useEffect(
    () => () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    },
    [],
  );

  // ★D: when opened from a panel, fetch the lifted image and pre-load it into the picker. A
  // fetch failure (e.g. mock mode with no backend) degrades to the normal empty dropzone + a note.
  React.useEffect(() => {
    if (!origin?.imageUrl) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(origin.imageUrl);
        if (!res.ok) throw new Error(String(res.status));
        const blob = await res.blob();
        if (cancelled) return;
        const file = new File([blob], `${origin.slug}-${origin.panelKey}.png`, {
          type: blob.type || "image/png",
        });
        loadFile(file);
        setForm(origin.form);
      } catch {
        if (!cancelled) setError("Couldn't load the panel image — drop it manually to digitize.");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once for this origin
  }, [origin?.imageUrl]);

  function loadFile(file: File) {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    const url = URL.createObjectURL(file);
    urlRef.current = url;
    setImage(file);
    setSrc(url);
    setDims(null);
    setCalib(EMPTY_CALIBRATION);
    setActive({ axis: "x", index: 0 }); // prime the first target
    setOptions(EMPTY_OPTIONS);
    setResult(null);
    setError(null);
    store.reset();
  }

  // Clear everything back to the drop target.
  function loadFileReset() {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
    setImage(null);
    setSrc(null);
    setDims(null);
    setCalib(EMPTY_CALIBRATION);
    setActive(null);
    setOptions(EMPTY_OPTIONS);
    setResult(null);
    setError(null);
    store.reset();
  }

  function placeRef(axis: AxisKey, index: 0 | 1, frac: { fx: number; fy: number }) {
    const next = cloneCalib(calib);
    next[axis][index] = { fx: frac.fx, fy: frac.fy, value: calib[axis][index]?.value ?? null };
    setCalib(next);
    setActive(firstUnplaced(next)); // advance the guided sequence
  }

  function setValue(axis: AxisKey, index: 0 | 1, value: number | null) {
    setCalib((c) => {
      const r = c[axis][index];
      if (!r) return c;
      const next = cloneCalib(c);
      next[axis][index] = { ...r, value };
      return next;
    });
  }

  function toggleLog(axis: AxisKey) {
    setCalib((c) => (axis === "x" ? { ...c, xLog: !c.xLog } : { ...c, yLog: !c.yLog }));
  }

  async function runExtract() {
    if (!image || !dims) return;
    setBusy(true);
    setError(null);
    try {
      const params = buildExtractParams(calib, form, dims.naturalW, dims.naturalH, {
        color: options.color.trim() || null,
        labels:
          form === "bar" && options.labels.trim()
            ? options.labels.split(",").map((s) => s.trim()).filter(Boolean)
            : null,
        seriesName: options.seriesName.trim() || undefined,
        xName: options.xName.trim() || undefined,
        yName: options.yName.trim() || undefined,
      });
      const res = await extractChart(image, params);
      setResult(res);
      store.init(res.figure);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extraction failed.");
    } finally {
      setBusy(false);
    }
  }

  const canExtract =
    !!image &&
    !!dims &&
    !busy &&
    calibrationComplete(calib) &&
    !calibrationDegenerate(calib, dims.naturalW, dims.naturalH);

  // --- Empty state: the drop target -------------------------------------------------
  if (!src) {
    return (
      <div className="flex h-full min-h-0 flex-col">
        {origin && <DigitizeBanner origin={origin} />}
        <div className="mx-auto flex min-h-0 max-w-3xl flex-1 flex-col items-center justify-center px-6 py-12 text-center">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary/80">Data extractor</p>
        <h1 className="text-display mt-3 text-3xl text-foreground sm:text-4xl">Recover data from a figure</h1>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
          Drop a published bar, line, or scatter panel. Mark two reference ticks on each axis, and
          Selom reads back the underlying numbers as an editable figure and Statistics table.
        </p>
        <Dropzone
          className="mt-8 w-full"
          onFile={loadFile}
          accept="image/*"
          title="Drop a chart panel image"
          hint="A single bar / line / scatter panel works best"
          formats="PNG · JPG · WEBP"
          icon={ImageDown}
        />
        <p className="mt-4 flex items-center gap-1.5 text-xs text-muted-foreground/80">
          <ShieldAlert className="size-3.5" />
          Recovered values are vision-grade estimates — review them before using as data.
        </p>
        </div>
      </div>
    );
  }

  // --- Result: the recovered figure in the real editor ------------------------------
  if (result) {
    return (
      <div className="flex h-full min-h-0 flex-col">
        {origin && <DigitizeBanner origin={origin} />}
        <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-border bg-card/30 px-5 py-2.5">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-300">
            <ShieldAlert className="size-3.5" /> Vision-grade — confirm before trusting
          </span>
          <span className="text-xs text-muted-foreground">
            Confidence {result.confidence.toFixed(2)} · recovered as an editable figure
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setResult(null)}>
              Re-calibrate
            </Button>
            <Button variant="outline" size="sm" onClick={() => loadFileReset()}>
              Recover another
            </Button>
          </div>
        </div>
        <div className="min-h-0 flex-1">
          <EditorWorkspace store={store} />
        </div>
        <div className="shrink-0 border-t border-border bg-card/20 p-3">
          <StatsPanel table={result.table} defaultOpen />
        </div>
      </div>
    );
  }

  // --- Calibration: image on the artboard + the controls rail -----------------------
  return (
    <div className="flex h-full min-h-0 flex-col">
      {origin && <DigitizeBanner origin={origin} />}
      <div className="flex min-h-0 flex-1">
      <div className="relative flex min-w-0 flex-1 items-center justify-center overflow-auto p-6 lg:p-10">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(48rem 28rem at 50% 12%, color-mix(in oklab, var(--primary) 9%, transparent), transparent 72%)",
          }}
        />
        <div className="relative rounded-xl border border-border bg-artboard p-3 shadow-2xl ring-1 ring-black/5">
          <CalibrationCanvas src={src} calib={calib} active={active} onPlace={placeRef} onImageLoad={setDims} />
        </div>
      </div>
      <ExtractControls
        form={form}
        onForm={setForm}
        calib={calib}
        active={active}
        onActivate={(axis, index) => setActive({ axis, index })}
        onValue={setValue}
        onToggleLog={toggleLog}
        options={options}
        onOptions={setOptions}
        canExtract={canExtract}
        busy={busy}
        error={error}
        onExtract={runExtract}
        onReset={loadFileReset}
      />
      </div>
    </div>
  );
}

/** ★D: the integrity banner shown when the picker is opened from a Reproduction panel. The
 *  digitize ≠ reproduce signal — color is reinforced with the icon + explicit text (not colour
 *  alone), and a back link returns to the paper. */
function DigitizeBanner({ origin }: { origin: DigitizeOrigin }) {
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-amber-500/30 bg-amber-500/[0.06] px-5 py-2">
      <Link
        href={`/reproduction/${origin.slug}`}
        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden /> Back to {origin.slug}
      </Link>
      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-300">
        <ScanLine className="size-3.5" aria-hidden /> Digitizing Fig {origin.panelKey}
      </span>
      <span className="text-xs text-muted-foreground">
        Recovered values are vision-grade and are{" "}
        <span className="font-medium text-foreground/90">not part of the Reproducibility Score</span>.
      </span>
    </div>
  );
}
