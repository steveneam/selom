"use client";

import * as React from "react";
import { Download, FilePlus2, Redo2, Undo2 } from "lucide-react";
import { SelomWordmark } from "@/components/brand/selom-mark";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { FigureStore } from "@/hooks/use-figure-store";

export function TopBar({
  store,
  fileName,
  hasFigure,
  onReset,
}: {
  store: FigureStore;
  fileName?: string;
  hasFigure: boolean;
  onReset: () => void;
}) {
  return (
    <TooltipProvider delayDuration={300}>
      <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-card/60 px-4 backdrop-blur-sm">
        <div className="flex min-w-0 items-center gap-3">
          <SelomWordmark />
          <span className="hidden text-xs text-muted-foreground sm:inline">
            Non-code multi-omics IDE
          </span>
        </div>

        {hasFigure && (
          <div className="flex items-center gap-1.5">
            {fileName && (
              <span className="tabular mr-1 hidden max-w-[16rem] truncate rounded-md border border-border bg-background/50 px-2 py-1 text-xs text-muted-foreground md:inline">
                {fileName}
              </span>
            )}

            <IconAction
              label="Undo"
              shortcut="⌘Z"
              disabled={!store.canUndo}
              onClick={store.undo}
            >
              <Undo2 />
            </IconAction>
            <IconAction
              label="Redo"
              shortcut="⌘⇧Z"
              disabled={!store.canRedo}
              onClick={store.redo}
            >
              <Redo2 />
            </IconAction>

            <Separator orientation="vertical" className="mx-1 h-6" />

            <Button variant="ghost" size="sm" onClick={onReset}>
              <FilePlus2 />
              New figure
            </Button>

            <Tooltip>
              <TooltipTrigger asChild>
                {/* span wrapper so the tooltip works on a disabled button */}
                <span tabIndex={0}>
                  <Button size="sm" disabled className="pointer-events-none">
                    <Download />
                    Export
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>
                Publication export (SVG / PDF / 300-dpi PNG) arrives with the live backend. PNG is
                available now from the figure toolbar.
              </TooltipContent>
            </Tooltip>
          </div>
        )}
      </header>
    </TooltipProvider>
  );
}

function IconAction({
  label,
  shortcut,
  disabled,
  onClick,
  children,
}: {
  label: string;
  shortcut?: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon" disabled={disabled} onClick={onClick} aria-label={label}>
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        {label}
        {shortcut && <span className="ml-2 text-muted-foreground">{shortcut}</span>}
      </TooltipContent>
    </Tooltip>
  );
}
