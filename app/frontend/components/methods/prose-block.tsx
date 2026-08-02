"use client";

import * as React from "react";
import { type LucideIcon, TriangleAlert } from "lucide-react";

import { cn } from "@/lib/ui/cn";
import { CopyButton } from "./copy-button";

/**
 * One paste-ready block of generated prose — the write-up's unit of composition
 * (docs/paper-outputs/spec.md §2).
 *
 * Deliberately the same anatomy as the shipped figure-scale panel (`PublishConfidence`): an
 * uppercase section label with an icon, the copy action on the right, selectable prose, and a
 * standing "draft — edit before use" note. Manuscript text is never auto-submitted; the note is
 * part of the contract, not decoration.
 *
 * States are explicit and never silently empty: `loading` shows skeleton lines sized like the real
 * prose, `error` says which section failed, and `unavailable` states a structural limit (a section
 * this source genuinely cannot fill) in different language from a failure — because "we can't do
 * this yet" and "this broke" are different facts.
 */
export function ProseBlock({
  id,
  title,
  icon: Icon,
  sub,
  text,
  copyText,
  copyLabel,
  note,
  loading = false,
  error,
  unavailable,
  emptyNote,
  action,
  children,
  className,
}: {
  id: string;
  title: string;
  icon: LucideIcon;
  sub?: React.ReactNode;
  /** The rendered prose. Omit and pass `children` for a structured body (e.g. a legend list). */
  text?: string;
  /** What Copy puts on the clipboard — defaults to `text`. */
  copyText?: string;
  copyLabel?: string;
  /** The standing edit-before-use caveat shown under the prose. */
  note?: string;
  loading?: boolean;
  error?: string;
  unavailable?: string;
  /** Shown when the section resolved successfully but has nothing in it. */
  emptyNote?: string;
  /** An extra control beside Copy (e.g. the reference-list search toggle). */
  action?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  const body = copyText ?? text ?? "";
  const hasBody = Boolean(text?.trim()) || Boolean(children);

  return (
    <section aria-labelledby={id} className={cn("min-w-0", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <Icon className="size-3.5 shrink-0 text-muted-foreground" />
        <h3
          id={id}
          className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
        >
          {title}
        </h3>
        {sub}
        <div className="ml-auto flex items-center gap-1">
          {action}
          {!unavailable && !error && <CopyButton text={body} label={copyLabel} />}
        </div>
      </div>

      {loading ? (
        <ProseSkeleton />
      ) : error ? (
        <BlockNotice tone="error">
          Couldn&apos;t generate this section — {error}.
        </BlockNotice>
      ) : unavailable ? (
        <BlockNotice tone="limit">{unavailable}</BlockNotice>
      ) : hasBody ? (
        <>
          {text ? (
            <p className="mt-2 select-text whitespace-pre-line text-sm leading-relaxed text-foreground/90">
              {text}
            </p>
          ) : null}
          {children}
          {note ? <p className="mt-2 text-[11px] text-muted-foreground">{note}</p> : null}
        </>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">
          {emptyNote ?? "Nothing to show for this paper."}
        </p>
      )}
    </section>
  );
}

/** Sized like the real prose so the block doesn't reflow when the text lands (U6). */
function ProseSkeleton() {
  return (
    <div className="mt-2.5 space-y-2" aria-hidden>
      {["w-full", "w-11/12", "w-full", "w-4/5"].map((w, i) => (
        <div key={i} className={cn("h-3 animate-pulse rounded-sm bg-muted/60", w)} />
      ))}
    </div>
  );
}

/**
 * A failure and a stated limit read differently on purpose: an error is amber and apologetic, a
 * limit is neutral and explanatory. Collapsing them would teach the user that a known boundary is a
 * bug, or that a bug is normal.
 */
function BlockNotice({ tone, children }: { tone: "error" | "limit"; children: React.ReactNode }) {
  return (
    <p
      className={cn(
        "mt-2 flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2.5 text-xs leading-relaxed",
        tone === "error"
          ? "border-amber-500/30 bg-amber-500/5 text-amber-700 dark:text-amber-400"
          : "border-border bg-muted/30 text-muted-foreground",
      )}
    >
      {tone === "error" && <TriangleAlert className="mt-px size-3.5 shrink-0" />}
      <span>{children}</span>
    </p>
  );
}
