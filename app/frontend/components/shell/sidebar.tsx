"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Dna, Home, PanelLeftClose, PanelLeftOpen, Plus, Settings, Store } from "lucide-react";
import { SelomMark, SelomWordmark } from "@/components/brand/selom-mark";
import { cn } from "@/lib/cn";
import { projectStore, useProjects } from "@/lib/projects/store";

export function Sidebar({
  open = false,
  collapsed = false,
  onToggleCollapse,
  onNavigate,
}: {
  /** Drawer state below `lg` (ignored at desktop, where the rail is static). */
  open?: boolean;
  /** Desktop icon-only mode (the rail collapses to a spine). */
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  /** Called on any in-rail navigation so the mobile drawer can close itself. */
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { projects } = useProjects();

  function newProject() {
    const p = projectStore.createProject("Untitled project");
    onNavigate?.();
    router.push(`/p/${p.id}`);
  }

  return (
    <aside
      aria-label="Primary"
      className={cn(
        // Mobile: off-canvas drawer (opaque, above content + scrim).
        "fixed inset-y-0 left-0 z-40 flex shrink-0 flex-col border-r border-border bg-card",
        "transition-[transform,width] duration-200 ease-out",
        open ? "translate-x-0" : "-translate-x-full",
        // Desktop: static in-flow rail with the translucent brand surface; width
        // tracks the collapse state (icon-only spine vs. full rail).
        "lg:static lg:z-auto lg:translate-x-0 lg:bg-card/40",
        collapsed ? "w-[4.5rem]" : "w-64",
      )}
    >
      <div className={cn("flex h-14 items-center", collapsed ? "justify-center px-2" : "px-4")}>
        <Link href="/" aria-label="Selom home" onClick={onNavigate}>
          {collapsed ? (
            <SelomMark className="size-6 text-primary [filter:drop-shadow(0_0_6px_color-mix(in_oklab,var(--primary)_55%,transparent))]" />
          ) : (
            <SelomWordmark />
          )}
        </Link>
      </div>

      <nav className={cn("pb-2", collapsed ? "px-2" : "px-3")}>
        <RailLink href="/" icon={<Home />} label="Home" active={pathname === "/"} collapsed={collapsed} onNavigate={onNavigate} />
        <RailLink href="/store" icon={<Store />} label="Skill Store" active={pathname.startsWith("/store")} collapsed={collapsed} onNavigate={onNavigate} />
        <RailLink href="/gene-sets" icon={<Dna />} label="Gene Sets" active={pathname.startsWith("/gene-sets")} collapsed={collapsed} onNavigate={onNavigate} />
      </nav>

      <div className={cn("mt-2 flex items-center pb-1", collapsed ? "justify-center px-2" : "justify-between px-4")}>
        {!collapsed && (
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Projects</span>
        )}
        <button
          type="button"
          onClick={newProject}
          aria-label="New project"
          title="New project"
          className="grid size-6 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          <Plus className="size-4" />
        </button>
      </div>

      <div className={cn("min-h-0 flex-1 overflow-y-auto pb-3", collapsed ? "px-2" : "px-3")}>
        {projects.length === 0 ? (
          !collapsed && (
            <p className="px-2 py-6 text-center text-xs text-muted-foreground/80">
              No projects yet. Press <span className="text-foreground">+</span> to start.
            </p>
          )
        ) : (
          <ul className="space-y-0.5">
            {projects.map((p) => {
              const active = pathname.startsWith(`/p/${p.id}`);
              return (
                <li key={p.id}>
                  <Link
                    href={`/p/${p.id}`}
                    onClick={onNavigate}
                    title={collapsed ? p.name : undefined}
                    className={cn(
                      "group flex items-center gap-2.5 rounded-md text-sm transition-colors",
                      collapsed ? "justify-center px-0 py-2" : "px-2 py-1.5",
                      active
                        ? "bg-accent text-accent-foreground"
                        : "text-foreground/80 hover:bg-accent/50 hover:text-foreground",
                    )}
                  >
                    <span
                      aria-hidden
                      className="size-2.5 shrink-0 rounded-[3px] ring-1 ring-inset ring-black/20"
                      style={{ backgroundColor: p.color }}
                    />
                    {!collapsed && <span className="min-w-0 truncate">{p.name}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className={cn("border-t border-border", collapsed ? "px-2 py-3" : "p-3")}>
        {/* Collapse / expand toggle (desktop only — the mobile drawer is full-width). */}
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "hidden items-center gap-2.5 rounded-md text-sm text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground lg:flex [&_svg]:size-4 [&_svg]:shrink-0",
              collapsed ? "justify-center px-0 py-1.5" : "px-2 py-1.5",
            )}
          >
            {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
            {!collapsed && <span>Collapse</span>}
          </button>
        )}
        <RailLink href="/" icon={<Settings />} label="Settings" active={false} muted collapsed={collapsed} onNavigate={onNavigate} />
        <div className={cn("mt-2 flex items-center gap-2", collapsed ? "justify-center px-0 py-1.5" : "px-2 py-1.5")}>
          <span
            title={collapsed ? "Steven · Workspace" : undefined}
            className="grid size-7 shrink-0 place-items-center rounded-full bg-secondary text-xs font-semibold text-secondary-foreground"
          >
            S
          </span>
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-foreground">Steven</p>
              <p className="truncate text-[11px] text-muted-foreground">Workspace</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

function RailLink({
  href,
  icon,
  label,
  active,
  muted,
  collapsed,
  onNavigate,
}: {
  href: string;
  icon: ReactNode;
  label: string;
  active: boolean;
  muted?: boolean;
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      title={collapsed ? label : undefined}
      aria-label={collapsed ? label : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-md text-sm transition-colors [&_svg]:size-4 [&_svg]:shrink-0",
        collapsed ? "justify-center px-0 py-2" : "px-2 py-1.5",
        active
          ? "bg-accent font-medium text-accent-foreground"
          : muted
            ? "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            : "text-foreground/85 hover:bg-accent/50 hover:text-foreground",
      )}
    >
      {icon}
      {!collapsed && <span>{label}</span>}
    </Link>
  );
}
