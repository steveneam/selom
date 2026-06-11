"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { Menu, Search } from "lucide-react";
import { Sidebar } from "./sidebar";
import { projectStore } from "@/lib/projects/store";

/**
 * The persistent command-center frame: project rail + header + main stage.
 * Wraps every route (mounted from the root layout) so navigation never remounts
 * the sidebar — scroll and selection state persist (nav `state-preservation`).
 *
 * Below `lg` the rail is an off-canvas drawer toggled from the header; at desktop
 * it's a static column. The drawer closes on any navigation (route change).
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [navOpen, setNavOpen] = React.useState(false);

  // Load persisted projects on the client, once, after hydration.
  React.useEffect(() => {
    projectStore.hydrate();
  }, []);

  // Close the mobile drawer whenever the route changes.
  React.useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  return (
    <div className="flex h-dvh overflow-hidden">
      {/* Scrim behind the mobile drawer (desktop never shows it). */}
      {navOpen && (
        <div
          aria-hidden
          onClick={() => setNavOpen(false)}
          className="fixed inset-0 z-30 bg-black/55 lg:hidden"
        />
      )}
      <Sidebar open={navOpen} onNavigate={() => setNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card/30 px-4 backdrop-blur-sm sm:px-5">
          <button
            type="button"
            onClick={() => setNavOpen(true)}
            aria-label="Open navigation"
            aria-expanded={navOpen}
            className="grid size-9 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 lg:hidden"
          >
            <Menu className="size-5" />
          </button>
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
