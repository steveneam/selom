"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight, Check, Download, ExternalLink, Plus, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getSkill } from "@/lib/catalog/seed";
import {
  hasSkillInfo,
  referenceHref,
  referenceMeta,
  referenceTypeLabel,
} from "@/lib/catalog/references";
import type { SkillCatalogEntry, SkillReference } from "@/lib/catalog/types";

export function SkillDetail({
  skill,
  installed,
  targetProjectName,
  onClose,
  onToggleInstall,
}: {
  skill: SkillCatalogEntry | null;
  installed: boolean;
  targetProjectName?: string;
  onClose: () => void;
  // Optional: when omitted (e.g. opened from Skill Match, which has no target project) the dialog is
  // read-only — the install action is replaced by an install-status line + a link into the Store.
  onToggleInstall?: () => void;
}) {
  const dialogRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!skill) return;
    // Move focus into the dialog on open; restore it to the trigger on close.
    const previouslyFocused = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previouslyFocused?.focus?.();
    };
  }, [skill, onClose]);

  if (!skill) return null;
  const verified = skill.tier === "verified";

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <div
        aria-hidden
        onClick={onClose}
        className="absolute inset-0 bg-black/55 backdrop-blur-sm"
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`${skill.name} details`}
        tabIndex={-1}
        className="relative z-10 w-full max-w-lg overflow-hidden rounded-xl border border-border bg-popover shadow-2xl outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-border p-5">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="truncate text-base font-semibold text-foreground">{skill.name}</h2>
              <Badge variant={verified ? "verified" : "community"}>
                {verified ? "Verified" : "Community"}
              </Badge>
            </div>
            <p className="tabular mt-1 text-xs text-muted-foreground">
              {skill.source} · v{skill.version} · {skill.category}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid size-8 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="space-y-4 p-5">
          <p className="text-sm leading-relaxed text-foreground/90">{skill.summary}</p>

          <Meta label="Omics">
            <div className="flex flex-wrap gap-1.5">
              {skill.omics.map((o) => (
                <span key={o} className="rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">
                  {o}
                </span>
              ))}
            </div>
          </Meta>

          <div className="grid grid-cols-2 gap-4">
            <Meta label="Inputs">
              <span className="tabular text-xs text-foreground/80">{skill.inputFormats.join(", ")}</span>
            </Meta>
            <Meta label="Outputs">
              <span className="text-xs text-foreground/80">{skill.outputs.join(", ")}</span>
            </Meta>
            <Meta label="Engine">
              <span className="tabular text-xs text-foreground/80">{skill.engine}</span>
            </Meta>
            <Meta label="License">
              <span className="tabular text-xs text-foreground/80">{skill.license}</span>
            </Meta>
          </div>

          {skill.chainsWith.length > 0 && (
            <Meta label="Works well with">
              <div className="flex flex-wrap gap-1.5">
                {skill.chainsWith.map((id) => (
                  <span key={id} className="rounded-md bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground">
                    {getSkill(id)?.name ?? id}
                  </span>
                ))}
              </div>
            </Meta>
          )}

          {hasSkillInfo(skill) && <SkillInfo skill={skill} />}

          {!verified && (
            <p className="rounded-md border border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
              This skill is browsable now. It runs in a future sandbox (or once ported to a native
              runner via the Skill Foundry) — installing queues it for your account.
            </p>
          )}

          <div className="flex items-center gap-2 border-t border-border pt-4">
            {onToggleInstall ? (
              <Button
                variant={installed ? "secondary" : verified ? "default" : "outline"}
                size="sm"
                onClick={onToggleInstall}
              >
                {installed ? (
                  <>
                    <Check /> Installed{targetProjectName ? ` · ${targetProjectName}` : ""}
                  </>
                ) : verified ? (
                  <>
                    <Download /> Install{targetProjectName ? ` to ${targetProjectName}` : ""}
                  </>
                ) : (
                  <>
                    <Plus /> Queue{targetProjectName ? ` for ${targetProjectName}` : ""}
                  </>
                )}
              </Button>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                {installed ? (
                  <>
                    <Check className="size-3.5 text-emerald-500" /> Installed — runs in your account now
                  </>
                ) : (
                  <>
                    <Download className="size-3.5 text-primary" /> Available in the Skill Store
                  </>
                )}
                <Link href="/store" className="inline-flex items-center gap-0.5 text-primary hover:underline">
                  Open <ArrowUpRight className="size-3" />
                </Link>
              </span>
            )}
            <a
              href={`https://github.com/${skill.provenance.repo}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <ExternalLink className="size-3.5" /> {skill.provenance.repo}
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">{label}</p>
      {children}
    </div>
  );
}

/**
 * Provenance card (docs/skill-references/spec.md) — the "Skill Information" section: a
 * plain-language background paragraph + the structured references that back the skill,
 * each a linked citation. Sits beside the origin/license/tier chips so the install
 * decision has "what is this, where's it from, can I cite it" in one place.
 */
function SkillInfo({ skill }: { skill: SkillCatalogEntry }) {
  const refs = skill.references ?? [];
  return (
    <section
      aria-label="Skill information"
      className="space-y-3 rounded-lg border border-border bg-muted/30 p-4"
    >
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
        Skill Information
      </p>
      {skill.background && (
        <p className="text-xs leading-relaxed text-foreground/85">{skill.background}</p>
      )}
      {refs.length > 0 && (
        <ul className="space-y-2.5 border-t border-border/60 pt-3">
          {refs.map((ref, i) => (
            <ReferenceRow key={`${ref.title}-${i}`} reference={ref} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ReferenceRow({ reference }: { reference: SkillReference }) {
  const href = referenceHref(reference);
  const meta = referenceMeta(reference);
  return (
    <li className="space-y-0.5">
      <div className="flex items-baseline gap-2">
        <span className="mt-px shrink-0 rounded border border-border px-1 py-px text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
          {referenceTypeLabel(reference.type)}
        </span>
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="group inline-flex items-baseline gap-1 text-xs font-medium text-foreground hover:text-primary hover:underline"
          >
            {reference.title}
            <ExternalLink className="size-3 shrink-0 translate-y-px text-muted-foreground group-hover:text-primary" />
          </a>
        ) : (
          <span className="text-xs font-medium text-foreground/90">{reference.title}</span>
        )}
      </div>
      {meta && <p className="tabular pl-[calc(0.5rem+1.6rem)] text-[11px] text-muted-foreground">{meta}</p>}
      {reference.note && (
        <p className="pl-[calc(0.5rem+1.6rem)] text-[11px] leading-snug text-muted-foreground/80">
          {reference.note}
        </p>
      )}
    </li>
  );
}
