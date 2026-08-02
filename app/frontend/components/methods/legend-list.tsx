"use client";

import * as React from "react";
import { Captions } from "lucide-react";

import { legendBlock, type FigureLegend } from "@/lib/litsynth/api";
import { CopyButton } from "./copy-button";
import { ProseBlock } from "./prose-block";

/**
 * The write-up's figure legends — one paste-ready caption per in-scope analysis panel, in the
 * ledger's own figure order (docs/paper-outputs/spec.md §2).
 *
 * Each caption keeps its own Copy because captions are pasted one at a time, next to the figure
 * they describe; "Copy all" on the block header exists for the whole set. The label ("Figure 4e.")
 * comes from the ledger's numbering — the caption text itself deliberately bakes in no number, so
 * a user renumbering figures for a different journal is not fighting the generated text.
 */
export function LegendList({
  legends,
  loading = false,
  error,
  unavailable,
}: {
  legends: FigureLegend[];
  loading?: boolean;
  error?: string;
  unavailable?: string;
}) {
  const all = React.useMemo(() => legendBlock(legends), [legends]);

  return (
    <ProseBlock
      id="wu-legends"
      title="Figure legends"
      icon={Captions}
      sub={
        legends.length > 0 ? (
          <span className="text-[11px] text-muted-foreground/70">
            {legends.length} figure{legends.length === 1 ? "" : "s"}
          </span>
        ) : undefined
      }
      copyText={all}
      copyLabel="Copy all"
      note="Draft captions — check the numbering against your figure order and edit before use."
      loading={loading}
      error={error}
      unavailable={unavailable}
      emptyNote="This paper has no in-scope analysis panel to caption."
    >
      {legends.length > 0 && (
        <ul className="mt-2 space-y-2.5">
          {legends.map((l) => (
            <li key={`${l.figure}${l.panel}-${l.skill_id}`} className="group flex items-start gap-1.5">
              <p className="min-w-0 flex-1 select-text text-sm leading-relaxed text-foreground/90">
                <span className="font-semibold text-foreground">{l.label}</span> {l.text}
              </p>
              <CopyButton
                text={`${l.label} ${l.text}`}
                label=""
                title={`Copy ${l.label}`}
                className="h-6 px-1.5 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
              />
            </li>
          ))}
        </ul>
      )}
    </ProseBlock>
  );
}
