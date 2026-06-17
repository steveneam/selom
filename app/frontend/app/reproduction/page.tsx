import { Spectrum } from "@/components/reproduction/spectrum";

export const metadata = { title: "Reproduction — Selom" };

export default function ReproductionPage() {
  return (
    <div className="mx-auto max-w-7xl px-6 py-12 lg:px-10 lg:py-14">
      <div className="max-w-2xl">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary/80">
          Reproduction Engine
        </p>
        <h1 className="text-display mt-3 text-3xl text-foreground sm:text-4xl">
          Can the figure be <span className="accent-keyword">reproduced</span> — and did we do our job?
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Selom reproduces a paper&apos;s figures and their underlying numbers from just the PDF plus
          public raw data, then grades each one. The score has{" "}
          <span className="text-foreground">two separate axes</span>: how reproducible the figure is
          (a property of the paper and its data) versus how trustworthy Selom&apos;s reconstruction is.
          When they diverge, that&apos;s a discovery — not a failure.
        </p>
      </div>

      <div className="mt-10">
        <Spectrum />
      </div>
    </div>
  );
}
