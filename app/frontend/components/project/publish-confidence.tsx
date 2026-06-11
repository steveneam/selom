"use client";

import * as React from "react";
import { BadgeCheck, Check, ChevronDown, Copy, FileText, FlaskConical } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { SkillMethods, SkillProvenance } from "@/lib/skills-api";

/**
 * Publish-confidence panel (charter B4) — the answer to "is THIS the right,
 * reproducible figure to put in my paper?". Shows the auto methods-text (copyable,
 * with citations) and the per-figure reproducibility bundle (skill+version, the exact
 * parameters, the input data hash, and the analysis environment). Collapsed by default
 * so it never steals space from the editor; both halves come from the backend `/run`
 * response, so it hides cleanly when a run predates B4 or the mock omits it.
 */
export function PublishConfidence({
  provenance,
  methods,
}: {
  provenance?: SkillProvenance;
  methods?: SkillMethods;
}) {
  const [open, setOpen] = React.useState(false);
  if (!provenance && !methods) return null;

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
          Methods text &amp; reproducibility bundle
        </span>
        <ChevronDown
          className={`ml-auto size-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="grid gap-4 border-t border-border px-4 py-4 lg:grid-cols-2">
          {methods && <Methods methods={methods} />}
          {provenance && <Reproducibility provenance={provenance} />}
        </div>
      )}
    </div>
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
