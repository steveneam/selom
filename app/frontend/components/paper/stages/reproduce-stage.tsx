"use client";

import * as React from "react";
import {
  Check,
  FileSpreadsheet,
  FileText,
  FlaskConical,
  Loader2,
  RotateCcw,
  TriangleAlert,
  UploadCloud,
  X,
} from "lucide-react";

import { useCatalog } from "@/lib/catalog/registry";
import { skillColor } from "@/lib/catalog/modality";
import type { SkillCatalogEntry } from "@/lib/catalog/types";
import { oosLabel } from "@/lib/skill-match/api";
import { paperFiles, usePaperFiles } from "@/lib/paper/run-files";
import { useDataFit } from "@/lib/reproduction/data-fit";
import type { PaperRun } from "@/lib/reproduction/run";
import { workspaceStore } from "@/lib/workspace/store";
import { DataFitPanel } from "@/components/reproduction/data-fit-panel";
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
 * skills Skill Match routed (continuity from stage 1), the paper PDF + supplementary-materials
 * intake, and the live run readiness/progress. The trigger itself ("Run reproduction") is the
 * pipeline's top-right action (paper-shell.tsx), driven by the shared `run` controller passed here so
 * this stage shows the same lifecycle. The graded *output* lives on the Score stage.
 *
 * The bytes constraint (I5): the dropped File objects live in the session cache (`paperFiles`), not
 * localStorage — so a reload keeps the file *record* but not its contents, and the stage honestly
 * prompts to re-attach what's missing before a run.
 */
export function ReproduceStage({ paper, run }: { paper: SavedPaper; run: PaperRun }) {
  const fv = usePaperFiles(paper.id);
  const fit = useDataFit(paper.id);
  return (
    <div className="space-y-10">
      <MatchedSkills paper={paper} />
      <PaperPdfSection paper={paper} hasMain={fv.hasMain} mainName={fv.mainName} />
      <SupplementsSection paper={paper} attached={fv.attached} />
      <DataFitPanel fits={fit.fits} loading={fit.loading} error={fit.error} />
      <ReproduceStatus paper={paper} run={run} attached={fv.attached} hasMain={fv.hasMain} />
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

/** The paper PDF itself — reproduction reads its methods + captions to know what to run. Captured at
 *  the Skill-Match handoff; a reload drops the bytes (I5), so we re-prompt for it honestly. */
function PaperPdfSection({
  paper,
  hasMain,
  mainName,
}: {
  paper: SavedPaper;
  hasMain: boolean;
  mainName: string | null;
}) {
  return (
    <section>
      <SectionHeading
        title="The paper"
        sub="Reproduction reads the methods and figure captions from the paper PDF to know which skills to run."
      />
      <div className="mt-3">
        {hasMain ? (
          <Card className="flex items-center gap-3 p-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-border bg-muted text-primary [&_svg]:size-4">
              <FileText />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground" title={mainName ?? paper.filename}>
                {mainName ?? paper.filename}
              </p>
              <p className="mt-0.5 inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                <Check className="size-3" />
                Attached for this run
              </p>
            </div>
          </Card>
        ) : (
          <Dropzone
            onFile={(f) => paperFiles.setMain(paper.id, f)}
            accept=".pdf,application/pdf"
            title="Re-attach the paper PDF"
            hint="The file contents aren't kept between sessions — drop the paper PDF again to run."
            formats="PDF"
            icon={FileText}
            variant="secondary"
          />
        )}
      </div>
    </section>
  );
}

/** The supplementary-materials intake (umbrella §10 stage 2). Captures both the metadata (persisted
 *  on the paper) and the File bytes (session-only, for the run). */
function SupplementsSection({ paper, attached }: { paper: SavedPaper; attached: Set<string> }) {
  const supplements = paper.supplements ?? [];
  const [skipped, setSkipped] = React.useState(0);

  function add(files: File[]) {
    const valid: Omit<SavedSupplement, "id" | "addedAt">[] = [];
    const validFiles: File[] = [];
    let bad = 0;
    for (const f of files) {
      const kind = supplementKind(f.name);
      if (!kind) {
        bad += 1;
        continue;
      }
      valid.push({ filename: f.name, kind, size: f.size });
      validFiles.push(f);
    }
    setSkipped(bad);
    if (valid.length) workspaceStore.addPaperSupplements(paper.id, valid);
    paperFiles.addSupplements(paper.id, validFiles); // bytes for the run (session-only)
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
              <SupplementRow
                key={s.id}
                paperId={paper.id}
                supp={s}
                ready={attached.has(s.filename.toLowerCase())}
              />
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

function SupplementRow({
  paperId,
  supp,
  ready,
}: {
  paperId: string;
  supp: SavedSupplement;
  ready: boolean;
}) {
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
          <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <span className="rounded border border-border bg-background px-1.5 py-px text-[10px] font-medium uppercase tracking-wide">
              {KIND_LABEL[supp.kind]}
            </span>
            {size && <span className="tabular">{size}</span>}
            {ready ? (
              <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                <Check className="size-3" />
                Ready
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
                <RotateCcw className="size-3" />
                Re-attach to run
              </span>
            )}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-muted-foreground hover:text-destructive"
          onClick={() => {
            workspaceStore.removePaperSupplement(paperId, supp.id);
            paperFiles.removeSupplement(paperId, supp.filename);
          }}
          aria-label={`Remove ${supp.filename}`}
          title="Remove this supplement"
        >
          <X className="size-4" />
        </Button>
      </Card>
    </li>
  );
}

/** The run readiness / progress / error card. The trigger is the pipeline's "Run reproduction" button
 *  (paper-shell.tsx); this narrates what it will do and what's still missing (the I5 re-attach note). */
function ReproduceStatus({
  paper,
  run,
  attached,
  hasMain,
}: {
  paper: SavedPaper;
  run: PaperRun;
  attached: Set<string>;
  hasMain: boolean;
}) {
  const supps = paper.supplements ?? [];
  const missing = supps.filter((s) => !attached.has(s.filename.toLowerCase())).length;
  const needsReattach = missing > 0 || (!hasMain && (supps.length > 0 || !!paper.filename));

  if (run.phase === "running") {
    return (
      <StatusCard tone="info">
        <div className="flex items-center gap-2.5">
          <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
          <div>
            <p className="text-sm font-semibold text-foreground">Reproducing the figures…</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Running the matched skills on your data and reading back the printed numbers.
            </p>
          </div>
        </div>
      </StatusCard>
    );
  }

  if (run.phase === "failed") {
    return (
      <StatusCard tone="bad">
        <div className="flex items-start gap-2.5">
          <TriangleAlert className="size-4 shrink-0 text-destructive" />
          <div>
            <p className="text-sm font-semibold text-foreground">Reproduction didn&apos;t start</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {run.error ?? "Something went wrong."} Fix it above, then hit Run reproduction up top.
            </p>
          </div>
        </div>
      </StatusCard>
    );
  }

  // Idle — readiness summary.
  let title: string;
  let body: string;
  let badge: { label: string; tone: BadgeTone };
  if (!hasMain) {
    title = "Attach the paper PDF to run";
    body = "Reproduction needs the paper PDF (above) plus at least one Excel/CSV supplement.";
    badge = { label: "Needs files", tone: "warn" };
  } else if (run.supplementCount === 0) {
    title = "Add supplementary data to run";
    body = "Drop at least one Excel/CSV table above — that's where the printed targets live.";
    badge = { label: "Needs files", tone: "warn" };
  } else {
    title = "Ready to reproduce";
    body =
      `${run.supplementCount} supplement${run.supplementCount > 1 ? "s" : ""} attached. Hit Run ` +
      "reproduction up top — Selom runs the matched skills, sweeps the parameters toward the printed " +
      "numbers, and grades every figure on the Score tab.";
    badge = { label: "Ready", tone: "ok" };
  }

  return (
    <StatusCard tone="muted">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground">{title}</p>
          <p className="mt-1 max-w-xl text-xs leading-relaxed text-muted-foreground">{body}</p>
          {needsReattach && (
            <p className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-400">
              <RotateCcw className="size-3" />
              Files aren&apos;t kept between sessions — re-attach anything marked above to run.
            </p>
          )}
        </div>
        <StatusBadge {...badge} />
      </div>
    </StatusCard>
  );
}

type BadgeTone = "ok" | "warn";

function StatusBadge({ label, tone }: { label: string; tone: BadgeTone }) {
  const c = tone === "ok" ? "#34d399" : "#f59e0b";
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide"
      style={{
        backgroundColor: `color-mix(in oklab, ${c} 12%, transparent)`,
        borderColor: `color-mix(in oklab, ${c} 38%, transparent)`,
        color: `color-mix(in oklab, ${c} 82%, white)`,
      }}
    >
      {label}
    </span>
  );
}

function StatusCard({
  tone,
  children,
}: {
  tone: "muted" | "info" | "bad";
  children: React.ReactNode;
}) {
  const cls =
    tone === "bad"
      ? "border-destructive/40 bg-destructive/5"
      : tone === "info"
        ? "border-primary/30 bg-primary/5"
        : "border-dashed bg-card/40";
  return <Card className={`p-5 ${cls}`}>{children}</Card>;
}

function SectionHeading({ title, sub }: { title: string; sub: string }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{sub}</p>
    </div>
  );
}
