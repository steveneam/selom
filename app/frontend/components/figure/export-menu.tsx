"use client";

import * as React from "react";
import { AlertCircle, Download, Loader2, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { exportFigure, fetchExportPresets, type ExportFormat, type ExportPreset } from "@/lib/export-api";
import type { FigureSpec } from "@/lib/figure-spec";

const FORMATS: { id: ExportFormat; label: string; hint: string }[] = [
  { id: "png", label: "PNG", hint: "raster" },
  { id: "svg", label: "SVG", hint: "vector" },
  { id: "pdf", label: "PDF", hint: "vector" },
];

// Sentinel for "export at the figure's own size" — Radix Select values must be non-empty.
const FIT = "__fit__";

/**
 * Export the edited figure to a publication-ready file (charter B4 journal export).
 * A compact popover: choose a format and a journal size preset, then download. The
 * on-screen figure is never mutated — the backend skins a copy and rasterizes it via
 * Kaleido. A disabled "Style" row marks where installable journal styles will land.
 */
export function ExportMenu({ spec, filename = "selom-figure" }: { spec: FigureSpec; filename?: string }) {
  const [open, setOpen] = React.useState(false);
  const [format, setFormat] = React.useState<ExportFormat>("png");
  const [presets, setPresets] = React.useState<ExportPreset[]>([]);
  const [presetId, setPresetId] = React.useState<string>(FIT);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const ref = React.useRef<HTMLDivElement>(null);

  // Load the journal presets the first time the menu opens (optional — falls back to FIT).
  React.useEffect(() => {
    if (!open || presets.length) return;
    let cancelled = false;
    fetchExportPresets()
      .then((ps) => !cancelled && setPresets(ps))
      .catch(() => {
        /* presets are optional; "Fit to figure" still works */
      });
    return () => {
      cancelled = true;
    };
  }, [open, presets.length]);

  // Dismiss on outside-click / Escape.
  React.useEffect(() => {
    if (!open) return;
    function onDown(e: PointerEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function onExport() {
    setBusy(true);
    setError(null);
    try {
      await exportFigure(spec, {
        format,
        preset: presetId === FIT ? undefined : presetId,
        filename,
      });
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div ref={ref} className="relative">
      <Button
        variant="outline"
        size="sm"
        className="gap-1.5"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <Download className="size-4" />
        Export
      </Button>

      {open && (
        <div
          role="dialog"
          aria-label="Export figure"
          className="absolute right-0 z-50 mt-2 w-72 origin-top-right rounded-xl border border-border bg-popover p-3 text-popover-foreground shadow-xl"
        >
          {/* Format — segmented control */}
          <fieldset className="space-y-1.5">
            <legend className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Format</legend>
            <div className="grid grid-cols-3 gap-1 rounded-lg border border-border bg-background/60 p-1">
              {FORMATS.map((f) => {
                const active = f.id === format;
                return (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFormat(f.id)}
                    aria-pressed={active}
                    className={`flex flex-col items-center rounded-md px-2 py-1.5 text-xs font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/50 ${
                      active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"
                    }`}
                  >
                    <span>{f.label}</span>
                    <span className={`text-[10px] ${active ? "text-primary-foreground/75" : "text-muted-foreground/70"}`}>
                      {f.hint}
                    </span>
                  </button>
                );
              })}
            </div>
          </fieldset>

          {/* Size — journal presets */}
          <div className="mt-3 space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Size</label>
            <Select value={presetId} onValueChange={setPresetId}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={FIT}>Fit to figure</SelectItem>
                {presets.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="min-h-[1rem] text-[11px] text-muted-foreground">
              {presetId === FIT
                ? format === "png"
                  ? "On-screen size, 2× for a crisp raster."
                  : "On-screen size, scalable vector."
                : (presets.find((p) => p.id === presetId)?.note ?? "")}
            </p>
          </div>

          {/* Style slot — forward-compatible (installable journal styles land here) */}
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-dashed border-border/70 px-2.5 py-1.5">
            <Lock className="size-3.5 text-muted-foreground/70" />
            <span className="text-xs text-muted-foreground">Style</span>
            <span className="ml-auto text-[11px] text-muted-foreground/80">Selom default · more soon</span>
          </div>

          {error && (
            <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-snug text-destructive">
              <AlertCircle className="mt-px size-3.5 shrink-0" />
              <span>{error}</span>
            </p>
          )}

          <Button className="mt-3 w-full gap-1.5" size="sm" onClick={onExport} disabled={busy}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
            {busy ? "Rendering…" : `Export ${format.toUpperCase()}`}
          </Button>
        </div>
      )}
    </div>
  );
}
