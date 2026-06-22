"use client";

import * as React from "react";
import {
  AlertTriangle,
  ArrowRight,
  ChevronDown,
  Compass,
  Info,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { getSkill } from "@/lib/catalog/seed";
import type { DataCheck, DataRouting, QcFlag, SuggestedStep } from "@/lib/skills-api";

/**
 * "Is-my-data-clean?" verdict (P1c / P3a — the native moat for non-bioinformaticians).
 *
 * Two surfaces over one engine verdict (engine/qc.py + engine/route.py), carried on the
 * run response as `data_check`:
 *
 *  - **verdict** — alongside a produced figure: the modality Selom detected, any QC flags
 *    (each with a plain message + a concrete fix), and the suggested analysis pipeline for
 *    that modality (clickable to set up the next step). When the engine ISN'T confident about
 *    the routing (`DataRouting.confident === false` — modality unclear / coming-soon /
 *    unclassifiable), the pipeline is reframed as an honest, calm "not sure" surface instead of
 *    masquerading as a recommendation, with a "Choose a skill yourself" hand-off. A collapsible
 *    panel mirroring `PublishConfidence`; auto-opens when there's something to review OR to decide.
 *  - **blocked** — the run was halted by a `block`-severity problem (engine-spine D-e5: warn +
 *    require an explicit override, never a silent misleading figure). Always open, calm tone:
 *    the fix is the hero; "Review & run anyway" is a deliberately-subordinate escape hatch
 *    (the user owns their data) carrying a caution.
 */
export function DataCheckPanel({
  dataCheck,
  variant = "verdict",
  skillName,
  onPickSkill,
  onPickManually,
  onOverride,
  onDismiss,
  overriding = false,
}: {
  dataCheck: DataCheck;
  variant?: "verdict" | "blocked";
  /** The skill the blocked run was for (blocked variant) — names what "run anyway" will run. */
  skillName?: string;
  /** Set up a suggested pipeline step in the workbench (verdict variant). */
  onPickSkill?: (skillId: string) => void;
  /** Take over and browse skills when Selom isn't sure how to route (verdict variant, not confident). */
  onPickManually?: () => void;
  /** Run the analysis anyway, past the block (blocked variant). */
  onOverride?: () => void;
  /** Dismiss the block card (blocked variant). */
  onDismiss?: () => void;
  overriding?: boolean;
}) {
  const { kind, qc, routing } = dataCheck;
  // Nothing inspectable (fail-soft upload) → no verdict to show.
  if (!qc) return null;

  const flags = qc.flags ?? [];
  const blockFlags = flags.filter((f) => f.severity === "block");
  const warnFlags = flags.filter((f) => f.severity === "warn");
  const infoFlags = flags.filter((f) => f.severity === "info");
  const reviewCount = blockFlags.length + warnFlags.length;

  if (variant === "blocked") {
    return (
      <div
        role="alert"
        className="rounded-xl border border-destructive/40 bg-destructive/[0.06] p-4"
        data-testid="data-check-blocked"
      >
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 size-5 shrink-0 text-destructive" />
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-foreground">
              Let&apos;s fix your data before analyzing it
            </h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Selom read this as <KindChip kind={kind} /> and found something that would make the
              figure misleading. Here&apos;s what to check{skillName ? ` before running ${skillName}` : ""}.
            </p>
          </div>
        </div>

        <ul className="mt-3 space-y-2">
          {/* Block flags first (the reason we stopped), then any warnings worth seeing. */}
          {[...blockFlags, ...warnFlags].map((f, i) => (
            <FlagRow key={`${f.code}-${i}`} flag={f} prominent />
          ))}
        </ul>

        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
          <p className="mr-auto max-w-sm text-[11px] leading-relaxed text-muted-foreground">
            It&apos;s your data — you can run anyway, but the result may be misleading.
          </p>
          {onDismiss && (
            <Button variant="ghost" size="sm" onClick={onDismiss} disabled={overriding}>
              Not now
            </Button>
          )}
          {onOverride && (
            <Button
              variant="outline"
              size="sm"
              onClick={onOverride}
              disabled={overriding}
              data-testid="data-check-override"
              className="border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
            >
              {overriding ? <Loader2 className="animate-spin" /> : <AlertTriangle />}
              {overriding ? "Running…" : "Review & run anyway"}
            </Button>
          )}
        </div>
      </div>
    );
  }

  // ── verdict variant ──────────────────────────────────────────────────────────
  return (
    <VerdictPanel
      kind={kind}
      ok={qc.ok && reviewCount === 0}
      reviewCount={reviewCount}
      flags={[...blockFlags, ...warnFlags, ...infoFlags]}
      routing={routing}
      onPickSkill={onPickSkill}
      onPickManually={onPickManually}
    />
  );
}

function VerdictPanel({
  kind,
  ok,
  reviewCount,
  flags,
  routing,
  onPickSkill,
  onPickManually,
}: {
  kind: string;
  ok: boolean;
  reviewCount: number;
  flags: QcFlag[];
  routing: DataRouting | null;
  onPickSkill?: (skillId: string) => void;
  onPickManually?: () => void;
}) {
  // Selom couldn't confidently match this data to an analysis (engine/route.py confident=false).
  const notSure = !!routing && !routing.confident;
  const steps = routing?.steps ?? [];
  // Auto-open when there's something to review (QC) OR to decide (routing isn't sure); collapsed
  // only when it's clean AND confidently routed.
  const [open, setOpen] = React.useState(reviewCount > 0 || notSure);

  return (
    <div className="rounded-xl border border-border bg-card/60" data-testid="data-check-verdict">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2.5 rounded-xl px-4 py-2.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
      >
        {ok ? (
          <ShieldCheck className="size-4 text-primary" />
        ) : (
          <AlertTriangle className="size-4 text-amber-400" />
        )}
        <span className="text-sm font-medium text-foreground">Data check</span>
        <KindChip kind={kind} />
        <span className="hidden text-xs text-muted-foreground sm:inline">
          {reviewCount > 0
            ? `${reviewCount} to review`
            : notSure
              ? "clean, but not sure how to analyze"
              : "looks clean to analyze"}
        </span>
        <ChevronDown
          className={cn("ml-auto size-4 text-muted-foreground transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <div className="space-y-4 border-t border-border px-4 py-4">
          {flags.length > 0 ? (
            <ul className="space-y-2">
              {flags.map((f, i) => (
                <FlagRow key={`${f.code}-${i}`} flag={f} />
              ))}
            </ul>
          ) : (
            <p className="flex items-start gap-2 text-sm text-muted-foreground">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary/80" />
              No data-quality problems found — this is safe to analyze.
            </p>
          )}

          {routing &&
            (notSure ? (
              <UncertainRouting
                note={routing.note}
                steps={steps}
                onPickSkill={onPickSkill}
                onPickManually={onPickManually}
              />
            ) : steps.length > 0 ? (
              <section aria-labelledby="dc-pipeline" className="min-w-0">
                <div className="flex items-center gap-2">
                  <Sparkles className="size-3.5 text-muted-foreground" />
                  <h3
                    id="dc-pipeline"
                    className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    Suggested next steps
                  </h3>
                </div>
                {routing.note && <p className="mt-1.5 text-xs text-muted-foreground">{routing.note}</p>}
                <ol className="mt-2.5 space-y-1.5">
                  {steps.map((s, i) => (
                    <StepRow key={`${s.skill_id}-${i}`} index={i + 1} step={s} onPick={onPickSkill} />
                  ))}
                </ol>
              </section>
            ) : null)}
        </div>
      )}
    </div>
  );
}

/**
 * Routing the engine ISN'T sure about (engine/route.py `confident: false` — modality unclear,
 * a coming-soon modality, or unclassifiable). Honest + calm, NOT an error: a dashed "tentative"
 * card that names the uncertainty, explains why (the engine's note), reframes any suggestions as
 * exploratory starting points (still runnable), and hands control back with a clear "Choose a
 * skill yourself" CTA — so a low-confidence guess never masquerades as a recommendation.
 */
function UncertainRouting({
  note,
  steps,
  onPickSkill,
  onPickManually,
}: {
  note: string;
  steps: SuggestedStep[];
  onPickSkill?: (skillId: string) => void;
  onPickManually?: () => void;
}) {
  return (
    <section
      aria-labelledby="dc-unsure"
      className="rounded-lg border border-dashed border-border bg-muted/20 p-3.5"
      data-testid="data-check-unsure"
    >
      <div className="flex items-start gap-2.5">
        <Compass className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <h3 id="dc-unsure" className="text-sm font-medium text-foreground">
            Not sure how to analyze this
          </h3>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
            {note ||
              "Selom couldn't confidently match this data to an analysis. Choose a skill yourself, or try a starting point below."}
          </p>
        </div>
      </div>

      {steps.length > 0 && (
        <div className="mt-3">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">
            Exploratory starting points
          </p>
          <ol className="mt-2 space-y-1.5">
            {steps.map((s, i) => (
              <StepRow key={`${s.skill_id}-${i}`} index={i + 1} step={s} onPick={onPickSkill} />
            ))}
          </ol>
        </div>
      )}

      {onPickManually && (
        <Button
          variant="outline"
          size="sm"
          className="mt-3"
          onClick={onPickManually}
          data-testid="data-check-pick-manually"
        >
          Choose a skill yourself
          <ArrowRight />
        </Button>
      )}
    </section>
  );
}

/** One QC flag (engine/qc.py): severity icon + plain message + a concrete fix (E3). */
function FlagRow({ flag, prominent = false }: { flag: QcFlag; prominent?: boolean }) {
  const { Icon, tone } = SEVERITY[flag.severity] ?? SEVERITY.info;
  return (
    <li className="flex gap-2.5">
      <Icon className={cn("mt-0.5 size-4 shrink-0", tone)} />
      <div className="min-w-0">
        <p className={cn("text-sm", prominent ? "font-medium text-foreground" : "text-foreground/90")}>
          {flag.message}
        </p>
        {flag.fix && (
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{flag.fix}</p>
        )}
      </div>
    </li>
  );
}

/** One suggested pipeline step: ordinal + role badge + skill name + why, clickable to set up. */
function StepRow({
  index,
  step,
  onPick,
}: {
  index: number;
  step: { skill_id: string; role: string; reason: string };
  onPick?: (skillId: string) => void;
}) {
  const name = getSkill(`selom.${step.skill_id}`)?.name ?? getSkill(step.skill_id)?.name ?? step.skill_id;
  const inner = (
    <>
      <span className="tabular mt-0.5 w-4 shrink-0 text-center text-[11px] font-medium text-muted-foreground/70">
        {index}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-foreground">{name}</span>
          {step.role && <RoleBadge role={step.role} />}
        </div>
        {step.reason && <p className="mt-0.5 text-xs text-muted-foreground">{step.reason}</p>}
      </div>
      {onPick && <ArrowRight className="mt-0.5 size-3.5 shrink-0 text-muted-foreground/60" />}
    </>
  );
  if (!onPick) return <li className="flex gap-2.5">{inner}</li>;
  return (
    <li>
      <button
        type="button"
        onClick={() => onPick(step.skill_id)}
        className="flex w-full gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        {inner}
      </button>
    </li>
  );
}

function RoleBadge({ role }: { role: string }) {
  return (
    <span className="rounded-full border border-border bg-muted/50 px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
      {role}
    </span>
  );
}

/** The detected modality, as a quiet chip — Selom's read of "what is this data?". */
function KindChip({ kind }: { kind: string }) {
  return (
    <span className="rounded-full border border-border bg-background/60 px-2 py-0.5 text-[11px] font-medium text-foreground/80">
      {KIND_LABELS[kind] ?? kind}
    </span>
  );
}

const SEVERITY: Record<string, { Icon: typeof Info; tone: string }> = {
  block: { Icon: ShieldAlert, tone: "text-destructive" },
  warn: { Icon: AlertTriangle, tone: "text-amber-400" },
  info: { Icon: Info, tone: "text-primary/80" },
};

const KIND_LABELS: Record<string, string> = {
  sc_counts: "Single-cell counts",
  bulk_counts: "Bulk counts",
  de_results: "DE results",
  proteomics: "Proteomics",
  metabolomics: "Metabolomics",
  generic_table: "Table",
  unknown: "Unrecognized",
};
