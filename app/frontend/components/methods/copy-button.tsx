"use client";

import * as React from "react";
import { Check, Copy } from "lucide-react";

import { cn } from "@/lib/ui/cn";
import { Button } from "@/components/ui/button";

/**
 * The one copy affordance for every paste-ready block (docs/paper-outputs/spec.md §3).
 *
 * Mobbin ruled the alternative OUT: Notion / Coda / ClickUp / Skiff all gate export behind a
 * configuration modal (format · page range · layout · paper size). That is right for a
 * whole-document export and wrong here — a write-up is four short generated blocks whose
 * destination is a manuscript the user already has open. The action is "copy this block", so it is
 * one inline button with a 1.5s confirmation, exactly as `PublishConfidence` already does at
 * figure scale.
 *
 * Clipboard access fails silently in an insecure context; the button says so rather than pretending
 * it copied.
 */
export function CopyButton({
  text,
  label = "Copy",
  title,
  className,
}: {
  /** Empty text disables the button — there is nothing to put on the clipboard. */
  text: string;
  label?: string;
  title?: string;
  className?: string;
}) {
  const [state, setState] = React.useState<"idle" | "copied" | "failed">("idle");

  React.useEffect(() => {
    if (state === "idle") return;
    const t = setTimeout(() => setState("idle"), 1500);
    return () => clearTimeout(t);
  }, [state]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed");
    }
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      disabled={!text}
      onClick={copy}
      title={title ?? (text ? `${label} to the clipboard` : "Nothing to copy yet")}
      className={cn("h-7 gap-1.5 px-2 text-xs", className)}
    >
      {state === "copied" ? <Check className="text-primary" /> : <Copy />}
      {state === "copied" ? "Copied" : state === "failed" ? "Copy blocked" : label}
    </Button>
  );
}
