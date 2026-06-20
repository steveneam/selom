"use client";

import * as React from "react";
import {
  FileSpreadsheet,
  FileText,
  FlaskConical,
  Hourglass,
  UploadCloud,
  X,
} from "lucide-react";

import { useCatalog } from "@/lib/catalog/registry";
import { skillColor } from "@/lib/catalog/modality";
import type { SkillCatalogEntry } from "@/lib/catalog/types";
import { oosLabel } from "@/lib/skill-match/api";
import { workspaceStore } from "@/lib/workspace/store";
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

/**
 * The Reproduce stage body in the Paper shell — the *inputs* half of reproduction: a recap of the
 * skills Skill Match routed (continuity from stage 1), the supplementary-materials intake (umbrella
 * §10 stage 2), and the staged Reproduce CTA. The graded *output* (two-axis score + heatmap) lives on
 * the Score stage. Lifted from the former `PaperWorkspace` (its chrome now lives in `PaperShell`).
 */
export function ReproduceStage({ paper }: { paper: SavedPaper }) {
  return (
    <div className="space-y-10">
      <MatchedSkills paper={paper} />
      <SupplementsSection paper={paper} />
      <ReproduceStep paper={paper} />
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
    <section>
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
    <section>
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

/** Step 2 — a status note for the run. The trigger itself ("Run reproduction") is the prominent
 *  top-right action in the pipeline (paper-shell.tsx); this explains what it does + supplement state.
 *  The live drive is a later backend contract, so the run stays staged ("Live run coming"). */
function ReproduceStep({ paper }: { paper: SavedPaper }) {
  const n = (paper.supplements ?? []).length;
  return (
    <section>
      <Card className="flex flex-col gap-3 border-dashed bg-card/40 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground">Reproduce the figures</p>
          <p className="mt-1 max-w-xl text-xs leading-relaxed text-muted-foreground">
            {n > 0
              ? `${n} supplement${n > 1 ? "s" : ""} attached. Hit Run reproduction up top — Selom runs the matched skills, sweeps the parameters to hit the printed numbers, and grades every figure on the Score tab.`
              : "Attach the supplementary data above, then hit Run reproduction up top — Selom searches its parameters for what reproduces the paper's printed numbers."}
          </p>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          <Hourglass className="size-3" />
          Live run coming
        </span>
      </Card>
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
