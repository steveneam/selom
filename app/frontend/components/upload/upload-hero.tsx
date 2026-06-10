"use client";

import * as React from "react";
import { FileUp, Loader2, TriangleAlert } from "lucide-react";
import { SelomMark } from "@/components/brand/selom-mark";
import { cn } from "@/lib/cn";

type Status = "idle" | "running" | "error";

export function UploadHero({
  onFile,
  status,
  error,
  fileName,
}: {
  onFile: (file: File) => void;
  status: Status;
  error?: string;
  fileName?: string;
}) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = React.useState(false);
  const busy = status === "running";

  const pick = (files: FileList | null) => {
    const f = files?.[0];
    if (f) onFile(f);
  };

  return (
    <div className="relative grid flex-1 place-items-center overflow-hidden px-6">
      {/* atmosphere: a quiet cyan glow rising behind the drop card */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(60rem 36rem at 50% 0%, color-mix(in oklab, var(--primary) 12%, transparent), transparent 70%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.18]"
        style={{
          backgroundImage:
            "linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
          maskImage: "radial-gradient(48rem 30rem at 50% 38%, black, transparent 75%)",
        }}
      />

      <div className="relative z-10 w-full max-w-xl text-center">
        <div className="mb-6 flex justify-center">
          <SelomMark className="size-11 text-primary [filter:drop-shadow(0_0_14px_color-mix(in_oklab,var(--primary)_55%,transparent))]" />
        </div>
        <h1 className="text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          Visualizing biology. Without code.
        </h1>
        <p className="mx-auto mt-3 max-w-md text-pretty text-sm leading-relaxed text-muted-foreground">
          Drop a single-cell or bulk omics matrix and get a publication-quality, fully editable
          figure — no bioinformatician, no scripts.
        </p>

        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (!busy) pick(e.dataTransfer.files);
          }}
          className={cn(
            "group mt-8 flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-input bg-card/60 px-6 py-12 backdrop-blur-sm transition-colors duration-150",
            "hover:border-primary/60 hover:bg-card/80",
            dragging && "border-primary bg-accent/40",
            busy && "pointer-events-none opacity-80",
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".h5ad,.csv"
            className="sr-only"
            disabled={busy}
            onChange={(e) => pick(e.target.files)}
          />
          <span
            className={cn(
              "grid size-12 place-items-center rounded-full border border-border bg-background/70 text-primary transition-colors",
              "group-hover:border-primary/50",
            )}
          >
            {busy ? (
              <Loader2 className="size-5 animate-spin" />
            ) : (
              <FileUp className="size-5" />
            )}
          </span>
          <div className="space-y-0.5">
            <p className="text-sm font-medium text-foreground">
              {busy
                ? `Analyzing ${fileName ?? "your data"}…`
                : "Drop a file or click to browse"}
            </p>
            <p className="tabular text-xs text-muted-foreground">.h5ad or .csv · scRNA-seq, bulk RNA-seq</p>
          </div>
        </label>

        {status === "error" && (
          <div
            role="alert"
            className="mt-4 flex items-center justify-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            <TriangleAlert className="size-4 shrink-0" />
            <span>{error ?? "Something went wrong. Please try again."}</span>
          </div>
        )}

        <p className="mt-6 text-[11px] text-muted-foreground/70">
          Runs the <span className="tabular">umap_scrna</span> skill. Your file is processed for this
          figure only.
        </p>
      </div>
    </div>
  );
}
