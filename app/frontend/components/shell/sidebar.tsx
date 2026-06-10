"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Home, Plus, Settings, Store } from "lucide-react";
import { SelomWordmark } from "@/components/brand/selom-mark";
import { cn } from "@/lib/cn";
import { projectStore, useProjects } from "@/lib/projects/store";

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { projects } = useProjects();

  function newProject() {
    const p = projectStore.createProject("Untitled project");
    router.push(`/p/${p.id}`);
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-card/40">
      <div className="flex h-14 items-center px-4">
        <Link href="/" aria-label="Selom home">
          <SelomWordmark />
        </Link>
      </div>

      <nav className="px-3 pb-2">
        <RailLink href="/" icon={<Home />} label="Home" active={pathname === "/"} />
        <RailLink href="/store" icon={<Store />} label="Skill Store" active={pathname.startsWith("/store")} />
      </nav>

      <div className="mt-2 flex items-center justify-between px-4 pb-1">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Projects
        </span>
        <button
          type="button"
          onClick={newProject}
          aria-label="New project"
          className="grid size-6 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          <Plus className="size-4" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {projects.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-muted-foreground/80">
            No projects yet. Press <span className="text-foreground">+</span> to start.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {projects.map((p) => {
              const active = pathname.startsWith(`/p/${p.id}`);
              return (
                <li key={p.id}>
                  <Link
                    href={`/p/${p.id}`}
                    className={cn(
                      "group flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors",
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
                    <span className="min-w-0 truncate">{p.name}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="border-t border-border p-3">
        <RailLink href="/" icon={<Settings />} label="Settings" active={false} muted />
        <div className="mt-2 flex items-center gap-2 px-2 py-1.5">
          <span className="grid size-7 place-items-center rounded-full bg-secondary text-xs font-semibold text-secondary-foreground">
            S
          </span>
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-foreground">Steven</p>
            <p className="truncate text-[11px] text-muted-foreground">Workspace</p>
          </div>
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
}: {
  href: string;
  icon: ReactNode;
  label: string;
  active: boolean;
  muted?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors [&_svg]:size-4 [&_svg]:shrink-0",
        active
          ? "bg-accent font-medium text-accent-foreground"
          : muted
            ? "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            : "text-foreground/85 hover:bg-accent/50 hover:text-foreground",
      )}
    >
      {icon}
      <span>{label}</span>
    </Link>
  );
}
