"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { Menu, Search } from "lucide-react";
import { Sidebar } from "./sidebar";
import { CommandPalette } from "./command-palette";
import { UndoToast } from "./undo-toast";
import { projectStore } from "@/lib/projects/store";

/**
 * The persistent command-center frame: project rail + header + main stage.
 * Wraps every route (mounted from the root layout) so navigation never remounts
 * the sidebar — scroll and selection state persist (nav `state-preservation`).
 *
 * Below `lg` the rail is an off-canvas drawer toggled from the header; at desktop
 * it's a static column. The drawer closes on any navigation (route change).
 */
const RAIL_COLLAPSED_KEY = "selom.rail.collapsed";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [navOpen, setNavOpen] = React.useState(false);
  const [paletteOpen, setPaletteOpen] = React.useState(false);
  // Desktop app-rail collapse (icon-only spine). Starts expanded (matches SSR), then
  // syncs from localStorage after mount so the preference persists across navigation.
  const [railCollapsed, setRailCollapsed] = React.useState(false);

  // Load persisted projects + the rail-collapse preference on the client, once.
  React.useEffect(() => {
    projectStore.hydrate();
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydrate of a persisted UI pref on mount (SSR-safe)
      if (localStorage.getItem(RAIL_COLLAPSED_KEY) === "1") setRailCollapsed(true);
    } catch {
      /* storage unavailable */
    }
  }, []);

  const toggleRail = React.useCallback(() => {
    setRailCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem(RAIL_COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        /* storage unavailable */
      }
      return next;
    });
  }, []);

  // Close the mobile drawer whenever the route changes.
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- close the mobile drawer on navigation
    setNavOpen(false);
  }, [pathname]);

  // Skill Match is a width-hungry two-pane view (PDF viewer + matched skills) — auto-collapse the
  // desktop rail to its icon spine there so both panes get room (nav stays reachable as icons).
  const forceCollapsed = pathname.startsWith("/skill-match");
  const collapsed = railCollapsed || forceCollapsed;

  // ⌘K / Ctrl-K toggles the command palette from anywhere.
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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
      <Sidebar
        open={navOpen}
        collapsed={collapsed}
        onToggleCollapse={forceCollapsed ? undefined : toggleRail}
        onNavigate={() => setNavOpen(false)}
      />
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
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            aria-label="Search and run commands"
            aria-keyshortcuts="Meta+K Control+K"
            className="group relative flex h-9 w-full max-w-sm items-center rounded-md border border-input bg-background/60 pl-8 pr-12 text-left text-sm text-muted-foreground/70 outline-none transition-colors hover:border-ring/40 hover:text-muted-foreground focus-visible:border-ring/60 focus-visible:ring-2 focus-visible:ring-ring/30"
          >
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            Search projects, figures, skills…
            <kbd className="tabular pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              ⌘K
            </kbd>
          </button>
          <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
            <span className="hidden sm:inline">Non-code multi-omics IDE</span>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
      <UndoToast />
    </div>
  );
}
