"use client";

import * as React from "react";
import { Search } from "lucide-react";
import { Sidebar } from "./sidebar";
import { projectStore } from "@/lib/projects/store";

/**
 * The persistent command-center frame: project rail + header + main stage.
 * Wraps every route (mounted from the root layout) so navigation never remounts
 * the sidebar — scroll and selection state persist (nav `state-preservation`).
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  // Load persisted projects on the client, once, after hydration.
  React.useEffect(() => {
    projectStore.hydrate();
  }, []);

  return (
    <div className="flex h-dvh overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card/30 px-5 backdrop-blur-sm">
          <label className="relative w-full max-w-sm">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              aria-label="Search projects and skills"
              placeholder="Search projects, datasets, skills…"
              className="h-9 w-full rounded-md border border-input bg-background/60 pl-8 pr-12 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
            />
            <kbd className="tabular pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              ⌘K
            </kbd>
          </label>
          <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
            <span className="hidden sm:inline">Non-code multi-omics IDE</span>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
