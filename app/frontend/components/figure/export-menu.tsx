"use client";

import * as React from "react";
import { AlertCircle, Cloud, Download, Loader2, Palette } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { exportFigure, fetchExportPresets, resolveExportDimensions, type ExportFormat, type ExportPreset } from "@/lib/figure/export";
import type { FigureSpec } from "@/lib/figure/figure-spec";

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
export function ExportMenu({
  spec,
  filename = "selom-figure",
  activeStyleLabel = "Selom default",
  onOpenChange,
}: {
  spec: FigureSpec;
  filename?: string;
  activeStyleLabel?: string;
  /** Notifies the parent when the popover opens/closes (so it can keep the figure
   *  crisp above the scrim while the rest of the page blurs). */
  onOpenChange?: (open: boolean) => void;
}) {
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    onOpenChange?.(open);
  }, [open, onOpenChange]);
  const [format, setFormat] = React.useState<ExportFormat>("png");
  const [presets, setPresets] = React.useState<ExportPreset[]>([]);
  const [presetId, setPresetId] = React.useState<string>(FIT);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const ref = React.useRef<HTMLDivElement>(null);

  // Preview the exact file this will produce (mirrors the backend's resolve_dimensions).
  const dims = React.useMemo(
    () => resolveExportDimensions(spec, format, presetId === FIT ? undefined : presets.find((p) => p.id === presetId)),
    [spec, format, presetId, presets],
  );
  const isVector = format !== "png";

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
      const target = e.target as HTMLElement | null;
      // The Size <Select> renders its listbox in a Radix portal OUTSIDE this popover,
      // so a click on a preset option is technically "outside" — don't let that dismiss
      // the popover (otherwise picking a journal size closes the whole menu).
      if (target?.closest("[data-radix-popper-content-wrapper]")) return;
      if (ref.current && target && !ref.current.contains(target)) setOpen(false);
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
        // Raise the trigger above its OWN scrim (z-40) ONLY while the menu is open — otherwise a
        // permanent z-50 makes the button poke THROUGH the z-40 AI panel overlay when that's open.
        className={`relative gap-1.5 ${open ? "z-50" : ""}`}
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <Download className="size-4" />
        Export
      </Button>

      {open && (
        <>
          {/* Scrim: dim + blur the busy page so the popover reads as a focused layer. */}
          <div
            className="fixed inset-0 z-40 bg-background/55 backdrop-blur-[3px] motion-safe:animate-in motion-safe:fade-in-0"
            aria-hidden
            onClick={() => setOpen(false)}
          />
          <div
            role="dialog"
            aria-label="Export figure"
            className="absolute right-0 z-50 mt-2 w-72 origin-top-right rounded-xl border border-border bg-popover p-3 text-popover-foreground shadow-2xl ring-1 ring-border motion-safe:animate-in motion-safe:fade-in-0 motion-safe:zoom-in-95"
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
            {/* Output preview: the exact file you'll get. A journal preset sets the
                column width + DPI; the height keeps the figure's aspect (no crop). */}
            <div className="rounded-md bg-muted/40 px-2.5 py-1.5 text-[11px] leading-snug">
              <div className="font-semibold text-foreground/85">
                {dims.widthMm != null
                  ? `${dims.widthMm} × ${dims.heightMm} mm`
                  : `${dims.widthPx.toLocaleString()} × ${dims.heightPx.toLocaleString()} px`}
              </div>
              <div className="text-muted-foreground">
                {dims.widthMm != null
                  ? isVector
                    ? "scalable vector"
                    : `${dims.widthPx.toLocaleString()} × ${dims.heightPx.toLocaleString()} px · ${dims.dpi} dpi`
                  : isVector
                    ? "figure size · scalable vector"
                    : "figure size · 2× raster"}
              </div>
            </div>
          </div>

          {/* Style — reflects the active journal style (set in the editor toolbar);
              export is WYSIWYG, so the download uses whatever style is showing. */}
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-border/70 bg-background/40 px-2.5 py-1.5">
            <Palette className="size-3.5 text-muted-foreground/80" />
            <span className="text-xs text-muted-foreground">Style</span>
            <span className="ml-auto truncate text-[11px] font-medium text-foreground/80" title="Change in the toolbar">
              {activeStyleLabel}
            </span>
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

          {/* Export to cloud — scaffold entry; lights up with the cloud-storage integrations. */}
          <button
            type="button"
            disabled
            title="Coming soon"
            className="mt-2 flex w-full items-center gap-2 rounded-lg border border-border/70 bg-background/40 px-2.5 py-1.5 text-left opacity-70"
          >
            <Cloud className="size-3.5 text-muted-foreground/80" />
            <span className="text-xs text-muted-foreground">Export to cloud</span>
            <span className="ml-auto text-[11px] font-medium text-muted-foreground/70">Coming soon</span>
          </button>
          </div>
        </>
      )}
    </div>
  );
}
