"use client";

import * as React from "react";
import { AlertTriangle, BadgeCheck, Captions, Check, ChevronDown, Copy, FileText, FlaskConical, Info, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { FigureLegend, SkillGuardrail, SkillMethods, SkillProvenance } from "@/lib/skills-api";

/**
 * Publish-confidence panel (charter B4) — the answer to "is THIS the right,
 * reproducible figure to put in my paper?". Shows the paste-ready methods text and figure
 * legend (the "drop data → run → publication-ready methods + legend" pair, P4c / workspace-
 * library §11) plus the per-figure reproducibility bundle (skill+version, the exact parameters,
 * the input data hash, and the analysis environment). Collapsed by default so it never steals
 * space from the editor; every part comes from the backend `/run` response, so it hides cleanly
 * when a run predates a field or the mock omits it.
 */
export function PublishConfidence({
  provenance,
  methods,
  legend,
  guardrails = [],
}: {
  provenance?: SkillProvenance;
  methods?: SkillMethods;
  legend?: FigureLegend;
  guardrails?: SkillGuardrail[];
}) {
  const [open, setOpen] = React.useState(false);
  if (!provenance && !methods && !legend && guardrails.length === 0) return null;

  const warnCount = guardrails.filter((g) => g.level === "warn").length;

  return (
    <div className="rounded-xl border border-border bg-card/60">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2.5 rounded-xl px-4 py-2.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
      >
        <BadgeCheck className="size-4 text-primary" />
        <span className="text-sm font-medium text-foreground">Publish confidence</span>
        <span className="hidden text-xs text-muted-foreground sm:inline">
          Quality checks, methods, figure legend &amp; reproducibility
        </span>
        {warnCount > 0 && (
          <span className="ml-auto flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-400">
            <AlertTriangle className="size-3" />
            {warnCount} to review
          </span>
        )}
        <ChevronDown
          className={`${warnCount > 0 ? "ml-1.5" : "ml-auto"} size-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="space-y-4 border-t border-border px-4 py-4">
          {guardrails.length > 0 && <Guardrails items={guardrails} />}
          {(methods || legend) && (
            <div className="grid gap-4 lg:grid-cols-2">
              {methods && <Methods methods={methods} />}
              {legend && <Legend legend={legend} />}
            </div>
          )}
          {provenance && <Reproducibility provenance={provenance} />}
        </div>
      )}
    </div>
  );
}

function Guardrails({ items }: { items: SkillGuardrail[] }) {
  // Warnings first — they're the publish-confidence caveats; info notes reassure.
  const sorted = [...items].sort((a, b) => (a.level === b.level ? 0 : a.level === "warn" ? -1 : 1));
  return (
    <section aria-labelledby="pc-checks" className="min-w-0">
      <div className="flex items-center gap-2">
        <ShieldCheck className="size-3.5 text-muted-foreground" />
        <h3 id="pc-checks" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Quality checks
        </h3>
      </div>
      <ul className="mt-2 space-y-2">
        {sorted.map((g, i) => {
          const warn = g.level === "warn";
          const Icon = warn ? AlertTriangle : Info;
          return (
            <li key={`${g.code}-${i}`} className="flex gap-2.5">
              <Icon className={`mt-0.5 size-4 shrink-0 ${warn ? "text-amber-400" : "text-primary/80"}`} />
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground/90">{g.title}</p>
                <p className="text-xs leading-relaxed text-muted-foreground">{g.detail}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Methods({ methods }: { methods: SkillMethods }) {
  const [copied, setCopied] = React.useState(false);

  async function copy() {
    const refs = methods.citations.length
      ? "\n\nReferences:\n" + methods.citations.map((c, i) => `${i + 1}. ${c}`).join("\n")
      : "";
    try {
      await navigator.clipboard.writeText(methods.text + refs);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked (e.g. insecure context) — no-op */
    }
  }

  return (
    <section aria-labelledby="pc-methods" className="min-w-0">
      <div className="flex items-center gap-2">
        <FileText className="size-3.5 text-muted-foreground" />
        <h3 id="pc-methods" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Methods
        </h3>
        <Button variant="ghost" size="sm" className="ml-auto h-7 gap-1.5 px-2 text-xs" onClick={copy}>
          {copied ? <Check className="text-primary" /> : <Copy />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <p className="mt-2 select-text text-sm leading-relaxed text-foreground/90">{methods.text}</p>
      {methods.citations.length > 0 && (
        <ol className="mt-3 space-y-1 text-[11px] leading-snug text-muted-foreground">
          {methods.citations.map((c, i) => (
            <li key={i} className="flex gap-1.5">
              <span className="tabular shrink-0 text-muted-foreground/70">{i + 1}.</span>
              <span>{c}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Legend({ legend }: { legend: FigureLegend }) {
  const [copied, setCopied] = React.useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(legend.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked (e.g. insecure context) — no-op */
    }
  }

  return (
    <section aria-labelledby="pc-legend" className="min-w-0">
      <div className="flex items-center gap-2">
        <Captions className="size-3.5 text-muted-foreground" />
        <h3 id="pc-legend" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Figure legend
        </h3>
        <Button variant="ghost" size="sm" className="ml-auto h-7 gap-1.5 px-2 text-xs" onClick={copy}>
          {copied ? <Check className="text-primary" /> : <Copy />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <p className="mt-2 select-text text-sm leading-relaxed text-foreground/90">{legend.text}</p>
      <p className="mt-2 text-[11px] text-muted-foreground">Draft caption — number it and edit before use.</p>
    </section>
  );
}

function Reproducibility({ provenance }: { provenance: SkillProvenance }) {
  const { skill, params, input, environment } = provenance;
  const paramEntries = Object.entries(params);
  const pkgs = Object.entries(environment.packages);

  return (
    <section aria-labelledby="pc-repro" className="min-w-0">
      <div className="flex items-center gap-2">
        <FlaskConical className="size-3.5 text-muted-foreground" />
        <h3 id="pc-repro" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Reproducibility
        </h3>
      </div>
      <dl className="mt-2 space-y-2.5 text-xs">
        <Row label="Skill">
          <span className="text-foreground">{skill.title}</span>{" "}
          <span className="tabular text-muted-foreground">v{skill.version}</span>
        </Row>
        <Row label="Parameters">
          {paramEntries.length === 0 ? (
            <span className="text-muted-foreground">defaults</span>
          ) : (
            <span className="flex flex-wrap gap-1.5">
              {paramEntries.map(([k, v]) => (
                <code
                  key={k}
                  className="tabular rounded border border-border bg-background/60 px-1.5 py-0.5 text-[11px] text-foreground/90"
                >
                  {k}={String(v)}
                </code>
              ))}
            </span>
          )}
        </Row>
        <Row label="Input">
          <span className="text-foreground">{input.filename ?? "uploaded data"}</span>
          <span className="tabular ml-1.5 text-muted-foreground">{formatBytes(input.n_bytes)}</span>
          <div className="tabular mt-0.5 break-all text-[11px] text-muted-foreground/80">
            sha256:{input.sha256.slice(0, 16)}…
          </div>
        </Row>
        <Row label="Environment">
          <span className="tabular text-muted-foreground">Python {environment.python}</span>
          {pkgs.length > 0 && (
            <span className="mt-1 flex flex-wrap gap-1.5">
              {pkgs.map(([name, v]) => (
                <code
                  key={name}
                  className="tabular rounded border border-border bg-background/60 px-1.5 py-0.5 text-[11px] text-foreground/90"
                >
                  {name} {v}
                </code>
              ))}
            </span>
          )}
        </Row>
      </dl>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[6.5rem_1fr] gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-foreground/90">{children}</dd>
    </div>
  );
}

function formatBytes(n: number): string {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  return `${(n / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}
