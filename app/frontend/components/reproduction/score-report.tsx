"use client";

import * as React from "react";
import { Check, Copy, GitCompareArrows, Info, Loader2 } from "lucide-react";

import { tierLabel } from "@/lib/reproduction/api";
import type { FileFitReport } from "@/lib/reproduction/data-fit";
import type { Ledger, PaperScore, Scorecard } from "@/lib/reproduction/types";
import { explain } from "@/lib/ai/api";
import { buildScorecardPayload } from "@/lib/ai/explain-inputs";
import type { ExplainResponse } from "@/lib/ai/types";
import { ExplainSourceBadge } from "@/components/ai/explain-source-badge";
import { DataFitPanel } from "./data-fit-panel";
import { ReproHeatmap } from "./repro-heatmap";
import { PanelTable } from "./panel-table";

/**
 * The graded *body* of a reproduction ledger — the two-axis score, the findings-first banner, the
 * per-panel heatmap, and the golden-vs-computed evidence table. Extracted from `PaperDetail` so it
 * is shared, byte-identical, by BOTH the showcase detail (a staged ledger) and the live Score stage
 * (a driven run — live-reproduction-spec §7). The Score-stage ghost mirrors this exact structure, so
 * the layout doesn't reflow when the live run fills it (U6). Callers own the surrounding chrome
 * (back-link, metadata header, container); this renders only the score.
 */
export function ScoreReport({
  ledger,
  dataFits = [],
  showExplain = false,
}: {
  ledger: Ledger;
  /** The dropped-data fit ranking the run fed on (Slice 2) — surfaced on the live Score stage only;
   *  the showcase detail omits it (empty → the panel renders nothing). */
  dataFits?: FileFitReport[];
  /** Show the grounded "Explain this score" helper on the interpretation card — live Score stage
   *  only (the static showcase detail leaves it off so its staged fixture stays a clean demo). */
  showExplain?: boolean;
}) {
  const sc = ledger.scorecard;
  const score = sc?.score ?? null;
  return (
    <>
      {score && (
        <ScoreHeader
          score={score}
          findings={sc?.findings ?? {}}
          explainScorecard={showExplain ? sc : null}
        />
      )}

      {sc && <FindingsBanner findings={sc.findings} />}

      {sc && sc.provenance_divergences.length > 0 && (
        <ProvenanceCallout divergences={sc.provenance_divergences} />
      )}

      {dataFits.length > 0 && (
        <div className="mt-8">
          <DataFitPanel
            fits={dataFits}
            title="Data you ran on"
            sub="How well each file you attached fit these analyses — the same check shown before the run, kept with the result."
          />
        </div>
      )}

      {sc && sc.panel_scores.length > 0 && (
        <section className="mt-8">
          <SectionHeading
            title="Reproducibility heatmap"
            sub="Every panel, graded. Out-of-scope panels (wet-lab / not-deposited) are grey and excluded."
          />
          <div className="mt-4">
            <ReproHeatmap cells={sc.panel_scores} />
          </div>
        </section>
      )}

      <section className="mt-10">
        <SectionHeading
          title="Golden vs computed"
          sub="The printed target from the PDF against what Selom computed, with a verdict + blame per number."
        />
        <div className="mt-4">
          <PanelTable ledger={ledger} />
        </div>
      </section>
    </>
  );
}

/** The two-axis headline: reproducibility (paper+data) vs Selom-confidence (our tool). */
function ScoreHeader({
  score,
  findings,
  explainScorecard,
}: {
  score: PaperScore;
  findings: Record<string, number>;
  /** When set (live Score stage), render the grounded "Explain this score" helper. */
  explainScorecard?: Scorecard | null;
}) {
  const repro = score.reproducibility;
  const conf = score.selom_confidence;
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-[auto_auto_1fr] sm:items-stretch">
      <Axis
        big={repro}
        color={score.color}
        label="Reproducibility"
        sub={tierLabel(score.tier)}
        hint="Can the figure be regenerated? — a property of the paper & its data"
      />
      <Axis
        big={conf}
        color="#34d399"
        label="Selom confidence"
        sub="our reconstruction"
        hint="Is Selom's reconstruction trustworthy? — a property of our tool"
      />
      <div className="flex flex-col justify-center rounded-xl border border-border bg-card/50 p-5">
        <p className="text-sm leading-relaxed text-foreground/90">{interpret(score, findings)}</p>
        <p className="mt-2 text-xs text-muted-foreground">{score.coverage}</p>
        {explainScorecard && <ExplainScore scorecard={explainScorecard} />}
      </div>
    </div>
  );
}

/**
 * The grounded "Explain this score" helper (informational — NOT a mutation). Posts the flat
 * scorecard to `/ai/explain` and expands the returned text inline. Deterministic by default
 * (gateway OFF) → labelled "Grounded summary"; the ✨ "AI" badge appears only when a live key
 * produced it. The deterministic score above is never affected — failures degrade to a calm note.
 */
function ExplainScore({ scorecard }: { scorecard: Scorecard }) {
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<ExplainResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);

  async function run() {
    const payload = buildScorecardPayload(scorecard);
    if (!payload) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setCopied(false); // a re-score swap must not leave a stale "Copied" over text the user never copied
    try {
      setResult(await explain({ request: "explain_score", stage: "grade", scorecard: payload }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't generate an explanation.");
    } finally {
      setLoading(false);
    }
  }

  async function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    await run();
  }

  // #8 — Copy the grounded explanation (a reproducer wants to capture the prose).
  async function copy() {
    if (!result?.text) return;
    // Attribution travels with exported AI prose: the ✨ "AI" tag lives only on-screen, so a pasted
    // explanation would otherwise read as the user's own. Prepend a marker for AI-generated text;
    // a deterministic "Grounded summary" is copied verbatim (fe-review A-attributable, 2026-06-30).
    const payload = result.source === "ai" ? `[AI-generated]\n\n${result.text}` : result.text;
    try {
      // No optional chaining: when navigator.clipboard is absent (non-secure context) accessing
      // .writeText throws → caught → we do NOT flash a false "Copied" over an empty clipboard.
      await navigator.clipboard.writeText(payload);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable/blocked → no false confirmation; the text stays on screen to select */
    }
  }

  // #9 — refresh on re-score. ExplainScore caches the result; if the scorecard changes (a re-scored
  // run) we must not show stale text. Key on the flat payload the helper actually reads: re-fetch when
  // OPEN, drop the cache when CLOSED so the next open is fresh. (run() captures the latest scorecard.)
  const payloadKey = React.useMemo(
    () => JSON.stringify(buildScorecardPayload(scorecard) ?? null),
    [scorecard],
  );
  const prevKey = React.useRef(payloadKey);
  React.useEffect(() => {
    if (prevKey.current === payloadKey) return; // initial mount or no change
    prevKey.current = payloadKey;
    // Re-sync the cached explanation to the changed score: re-fetch if open, else drop the stale cache.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional re-sync to an external scorecard change
    if (open) void run(); else setResult(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run() reads the fresh scorecard closure
  }, [payloadKey, open]);

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border bg-background/60 px-2.5 py-1 text-xs font-medium text-foreground/80 transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
      >
        <Info className="size-3.5" /> {open ? "Hide explanation" : "Explain this score"}
      </button>
      {open && (
        <div className="mt-2 rounded-lg border border-border bg-background/50 px-3 py-2.5">
          {loading ? (
            <p className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" /> Reading the scorecard…
            </p>
          ) : error ? (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              {error} The score above is unaffected.{" "}
              <button
                type="button"
                onClick={run}
                className="cursor-pointer font-medium text-foreground underline underline-offset-2 hover:text-primary"
              >
                Try again
              </button>
            </p>
          ) : result ? (
            <>
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Explanation
                </span>
                <div className="flex items-center gap-2">
                  <ExplainSourceBadge source={result.source} />
                  <button
                    type="button"
                    onClick={copy}
                    aria-label={copied ? "Copied" : "Copy explanation"}
                    className="inline-flex cursor-pointer items-center gap-1 rounded border border-border bg-background/60 px-1.5 py-0.5 text-[10px] font-medium text-foreground/75 transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 [&_svg]:size-3"
                  >
                    {copied ? <Check className="text-emerald-500" /> : <Copy />}
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
              </div>
              <p className="text-xs leading-relaxed text-foreground/85">{result.text}</p>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}

function Axis({
  big,
  color,
  label,
  sub,
  hint,
}: {
  big: number | null;
  color: string;
  label: string;
  sub: string;
  hint: string;
}) {
  return (
    <div
      className="flex flex-col rounded-xl border border-border bg-card p-5"
      style={{ boxShadow: `inset 0 2px 0 0 color-mix(in oklab, ${color} 55%, transparent)` }}
      title={hint}
    >
      <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="tabular mt-1 text-5xl font-bold leading-none" style={{ color }}>
        {big ?? "—"}
        <span className="ml-0.5 text-lg font-normal text-muted-foreground">/100</span>
      </span>
      <span className="mt-1.5 text-xs text-muted-foreground">{sub}</span>
    </div>
  );
}

/** Findings-first (D10): what the engine *discovered*, elevated over plain pass/fail. */
function FindingsBanner({ findings }: { findings: Record<string, number> }) {
  const items: { key: string; label: string; tone: "good" | "found" | "bad" }[] = [
    { key: "reproduced", label: "reproduced", tone: "good" },
    { key: "paper_irreproducible", label: "paper-irreproducible", tone: "found" },
    { key: "structural_limit", label: "structural-limit", tone: "found" },
    { key: "engine_delta", label: "engine-delta", tone: "found" },
    { key: "upstream_delta", label: "upstream-delta", tone: "found" },
    { key: "selom_engine_bugs", label: "Selom defects", tone: "bad" },
  ];
  const shown = items.filter((i) => (findings[i.key] ?? 0) > 0 || i.key === "selom_engine_bugs");
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card/40 px-4 py-3">
      <span className="mr-1 inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        <GitCompareArrows className="size-3.5" />
        What the engine found
      </span>
      {shown.map((i) => {
        const n = findings[i.key] ?? 0;
        const c =
          i.tone === "good"
            ? "#34d399"
            : i.tone === "bad"
              ? n > 0
                ? "#ef4444"
                : "#34d399"
              : "#f59e0b";
        return (
          <span
            key={i.key}
            className="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs"
            style={{
              backgroundColor: `color-mix(in oklab, ${c} 12%, transparent)`,
              borderColor: `color-mix(in oklab, ${c} 38%, transparent)`,
              color: `color-mix(in oklab, ${c} 82%, white)`,
            }}
          >
            <span className="tabular font-semibold">{n}</span>
            {i.label}
          </span>
        );
      })}
    </div>
  );
}

/** D14: a faithful-to-deposit panel that diverges from the published figure — surfaced, not blamed. */
function ProvenanceCallout({ divergences }: { divergences: string[] }) {
  return (
    <div className="mt-4 rounded-xl border border-border bg-card/40 px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        Source-provenance divergence
      </p>
      <p className="mt-1.5 text-sm leading-relaxed text-foreground/85">
        These panels reproduce their deposited source faithfully but differ from the published figure
        (commonly a different replicate) — recorded transparently, never as a paper error:
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {divergences.map((d) => (
          <span
            key={d}
            className="tabular rounded border border-border bg-background/60 px-2 py-1 text-xs text-muted-foreground"
          >
            {d}
          </span>
        ))}
      </div>
    </div>
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

/** The headline interpretation — the two-axis story in one sentence. */
function interpret(score: PaperScore, findings: Record<string, number>): string {
  const repro = score.reproducibility ?? 0;
  const conf = score.selom_confidence ?? 0;
  const defects = findings.selom_engine_bugs ?? 0;
  const gap = conf - repro;
  if (defects > 0) {
    return `Selom found ${defects} defect${defects > 1 ? "s" : ""} in its own reconstruction — the score reflects a tool issue to fix, not the paper.`;
  }
  if (gap >= 15) {
    return `This figure is hard to reproduce (${repro}), but Selom's reconstruction is sound (${conf} confidence, 0 defects) — the gap is the paper and its data, not the tool.`;
  }
  if (repro >= 80) {
    return `Reproduced cleanly from the deposited data (${repro}) with full confidence (${conf}).`;
  }
  return `Reproducibility ${repro} with ${conf} confidence — the panel evidence below shows where each number lands.`;
}
