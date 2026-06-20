"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUpRight,
  FileSpreadsheet,
  FileText,
  FlaskConical,
  Hourglass,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";

import { useCatalog } from "@/lib/catalog/registry";
import { skillColor } from "@/lib/catalog/modality";
import type { SkillCatalogEntry } from "@/lib/catalog/types";
import { oosLabel } from "@/lib/skill-match/api";
import { useWorkspace, workspaceStore, wselect } from "@/lib/workspace/store";
import {
  KIND_LABEL,
  SUPPLEMENT_ACCEPT,
  formatBytes,
  supplementKind,
} from "@/lib/workspace/supplements";
import type { SavedPaper, SavedSupplement, SupplementKind } from "@/lib/workspace/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dropzone } from "@/components/project/dropzone";
import { PaperPipeline } from "@/components/paper/pipeline";
import { PaperMetaHeader } from "@/components/paper/paper-meta-header";

/**
 * The per-paper Reproduction WORKSPACE — the pre-reproduction state of the same page family as
 * the read-only showcase detail (components/reproduction/paper-detail.tsx). A paper carried over
 * from Skill Match (no re-drop) lands here; the user adds its supplementary materials, then runs
 * reproduction. It deliberately mirrors PaperDetail's layout — header → two-axis score → heatmap —
 * but with the score + heatmap GHOSTED ("awaiting reproduction") and the supplementary dropzone as
 * the action, so once the live drive lands (a later backend contract) the very same page fills with
 * real metrics. The showcase index + dogfood detail are left untouched (additive integration).
 */
export function PaperWorkspace({ id }: { id: string }) {
  const ws = useWorkspace();
  const paper = wselect.paper(ws, id);

  if (!paper) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-20 text-center">
        <p className="text-sm text-muted-foreground">
          This paper isn&apos;t in your Library.
        </p>
        <p className="mt-1.5 text-xs text-muted-foreground">
          Match a paper in{" "}
          <Link href="/skill-match" className="text-primary hover:underline">
            Skill Match
          </Link>{" "}
          and open it in Reproduction, or pick one from your{" "}
          <Link href="/library" className="text-primary hover:underline">
            Library
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10 lg:px-10">
      <Link
        href="/library"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Library
      </Link>

      {/* The shared workflow pipeline — you're at the Reproduce stage (carried from Skill Match).
          Click the "Skill Match" pill to jump back to the match this paper was derived from. */}
      <PaperPipeline
        current="reproduce"
        className="mt-4"
        links={{ "skill-match": `/skill-match/${paper.id}` }}
      />

      <PaperMetaHeader
        meta={paper}
        filename={paper.filename}
        className="mt-6"
        eyebrow={
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary/80">
            Reproduction · carried from Skill Match
          </p>
        }
      />

      <AwaitingScore />

      <MatchedSkills paper={paper} />

      <SupplementsSection paper={paper} />

      <ReproduceStep paper={paper} />

      <AwaitingHeatmap />
    </div>
  );
}

/** The two-axis ScoreHeader shape, ghosted — the slots the real scores fill once reproduced. */
function AwaitingScore() {
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-[auto_auto_1fr] sm:items-stretch">
      <GhostAxis label="Reproducibility" />
      <GhostAxis label="Selom confidence" />
      <div className="flex flex-col justify-center rounded-xl border border-dashed border-border bg-card/30 p-5">
        <p className="inline-flex items-center gap-1.5 text-sm font-medium text-foreground/80">
          <Hourglass className="size-4 text-muted-foreground" />
          Awaiting reproduction
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
          Add the paper&apos;s supplementary data below, then run reproduction — Selom grades every
          figure on two axes: how reproducible it is, and how confident Selom is in its own work.
        </p>
      </div>
    </div>
  );
}

function GhostAxis({ label }: { label: string }) {
  return (
    <div className="flex flex-col rounded-xl border border-dashed border-border bg-card/30 p-5">
      <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="tabular mt-1 text-5xl font-bold leading-none text-muted-foreground/30">
        —<span className="ml-0.5 text-lg font-normal text-muted-foreground/40">/100</span>
      </span>
      <span className="mt-1.5 text-xs text-muted-foreground/70">not yet scored</span>
    </div>
  );
}

/** A recap of the skills Skill Match routed this paper to — continuity from the entry stage. */
function MatchedSkills({ paper }: { paper: SavedPaper }) {
  const { catalog } = useCatalog();
  const bySlug = React.useMemo(() => {
    const m = new Map<string | undefined, SkillCatalogEntry>();
    for (const e of catalog) m.set(e.id.split(".").pop(), e);
    return m;
  }, [catalog]);
  const installed = React.useMemo(
    () => new Set(catalog.filter((e) => e.tier === "verified").map((e) => e.id.split(".").pop())),
    [catalog],
  );

  if (paper.skills.length === 0 && paper.outOfScope.length === 0) return null;

  return (
    <section className="mt-8">
      <SectionHeading
        title="Matched skills"
        sub="What Skill Match routed this paper to — the skills reproduction will drive once the data is in."
      />
      <div className="mt-3 flex flex-wrap gap-1.5">
        {paper.skills.map((slug) => {
          const entry = bySlug.get(slug);
          const color = entry ? skillColor(entry) : "#64748b";
          const isInstalled = installed.has(slug);
          return (
            <span
              key={slug}
              className="inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium"
              style={{
                backgroundColor: `color-mix(in oklab, ${color} 12%, transparent)`,
                borderColor: `color-mix(in oklab, ${color} 38%, transparent)`,
                color: `color-mix(in oklab, ${color} 82%, white)`,
              }}
              title={isInstalled ? "Installed — runs in your account" : "Available in the Skill Store"}
            >
              <span
                aria-hidden
                className="size-1.5 rounded-full"
                style={{ backgroundColor: color, opacity: isInstalled ? 1 : 0.4 }}
              />
              {entry?.name ?? slug}
            </span>
          );
        })}
      </div>
      {paper.outOfScope.length > 0 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-muted-foreground">Out of scope:</span>
          {paper.outOfScope.map((r) => (
            <span
              key={r}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              <FlaskConical className="size-3" />
              {oosLabel(r)}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

/** Step 1 — the supplementary-materials intake the owner asked for (umbrella §10 stage 2). */
function SupplementsSection({ paper }: { paper: SavedPaper }) {
  const supplements = paper.supplements ?? [];
  const [skipped, setSkipped] = React.useState(0);

  function add(files: File[]) {
    const valid: Omit<SavedSupplement, "id" | "addedAt">[] = [];
    let bad = 0;
    for (const f of files) {
      const kind = supplementKind(f.name);
      if (!kind) {
        bad += 1;
        continue;
      }
      valid.push({ filename: f.name, kind, size: f.size });
    }
    setSkipped(bad);
    if (valid.length) workspaceStore.addPaperSupplements(paper.id, valid);
  }

  return (
    <section className="mt-10">
      <SectionHeading
        title="Add the supplementary data"
        sub="Drop the paper's supplementary files — Excel / CSV tables (the printed targets like ST2, ST6) and extended-methods PDFs. Reproduction matches Selom's computed numbers against these."
      />

      <div className="mt-4 space-y-3">
        {supplements.length > 0 && (
          <ul className="space-y-2">
            {supplements.map((s) => (
              <SupplementRow key={s.id} paperId={paper.id} supp={s} />
            ))}
          </ul>
        )}

        <Dropzone
          multiple
          onFiles={add}
          accept={SUPPLEMENT_ACCEPT}
          title={supplements.length ? "Add more supplementary files" : "Drop supplementary materials"}
          hint="Excel, CSV, or PDF — or click to browse. Files stay on your machine; we read the tables and methods."
          formats=".xlsx · .xls · .csv · .pdf"
          icon={UploadCloud}
          variant={supplements.length ? "secondary" : "primary"}
        />

        {skipped > 0 && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            Skipped {skipped} unsupported file{skipped > 1 ? "s" : ""} — supplements must be{" "}
            <span className="tabular">.xlsx / .xls / .csv / .pdf</span>.
          </p>
        )}
      </div>
    </section>
  );
}

const KIND_ICON: Record<SupplementKind, typeof FileText> = {
  pdf: FileText,
  xlsx: FileSpreadsheet,
  csv: FileSpreadsheet,
};

function SupplementRow({ paperId, supp }: { paperId: string; supp: SavedSupplement }) {
  const Icon = KIND_ICON[supp.kind];
  const size = formatBytes(supp.size);
  return (
    <li>
      <Card className="flex items-center gap-3 p-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-border bg-muted text-primary [&_svg]:size-4">
          <Icon />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground" title={supp.filename}>
            {supp.filename}
          </p>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="rounded border border-border bg-background px-1.5 py-px text-[10px] font-medium uppercase tracking-wide">
              {KIND_LABEL[supp.kind]}
            </span>
            {size && <span className="tabular">{size}</span>}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-muted-foreground hover:text-destructive"
          onClick={() => workspaceStore.removePaperSupplement(paperId, supp.id)}
          aria-label={`Remove ${supp.filename}`}
          title="Remove this supplement"
        >
          <X className="size-4" />
        </Button>
      </Card>
    </li>
  );
}

/** Step 2 — the staged Reproduce CTA (live drive is a later backend contract; be honest). */
function ReproduceStep({ paper }: { paper: SavedPaper }) {
  const n = (paper.supplements ?? []).length;
  return (
    <section className="mt-10">
      <Card className="flex flex-col gap-3 border-dashed bg-card/40 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground">Reproduce the figures</p>
          <p className="mt-1 max-w-xl text-xs leading-relaxed text-muted-foreground">
            {n > 0
              ? `${n} supplement${n > 1 ? "s" : ""} attached. Selom will run the matched skills, sweep the parameters to hit the printed numbers, and grade every figure.`
              : "Attach the supplementary data above first — Selom searches its parameters for what reproduces the paper's printed numbers."}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            <Hourglass className="size-3" />
            Live run coming
          </span>
          <Button disabled title="The live reproduction drive is a backend step in progress">
            <FlaskConical />
            Reproduce
          </Button>
        </div>
      </Card>
    </section>
  );
}

/** The detail page's heatmap section, ghosted — with a pointer to a real graded example. */
function AwaitingHeatmap() {
  return (
    <section className="mt-10">
      <SectionHeading
        title="Reproducibility heatmap"
        sub="Once reproduced, every figure is graded here — the same per-panel heatmap the example papers show."
      />
      <div className="mt-4 flex flex-wrap gap-1.5" aria-hidden>
        {Array.from({ length: 12 }).map((_, i) => (
          <span
            key={i}
            className="size-6 rounded-[5px] border border-dashed border-border bg-muted/40"
          />
        ))}
      </div>
      <Link
        href="/reproduction/jev"
        className="mt-3 inline-flex items-center gap-1 text-xs text-primary/90 hover:text-primary hover:underline"
      >
        See a graded example
        <ArrowUpRight className="size-3" />
      </Link>
    </section>
  );
}

function SectionHeading({ title, sub }: { title: string; sub: string }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{sub}</p>
    </div>
  );
}
