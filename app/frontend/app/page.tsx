"use client";

import Link from "next/link";
import { ArrowRight, Boxes, FileBarChart, FolderPlus, LayoutGrid, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CATALOG_TOTAL_ESTIMATE, getSkill, VERIFIED_SEEDED } from "@/lib/catalog/seed";
import { select, useProjects } from "@/lib/projects/store";

function timeAgo(t: number): string {
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 3600) return `${Math.max(1, Math.floor(s / 60))}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function HomePage() {
  const state = useProjects();
  const { projects, datasets, figures } = state;
  const recentFigures = [...figures].sort((a, b) => b.createdAt - a.createdAt).slice(0, 4);

  const stats = [
    { label: "Projects", value: projects.length, icon: <LayoutGrid /> },
    { label: "Datasets", value: datasets.length, icon: <FileBarChart /> },
    { label: "Figures", value: figures.length, icon: <Sparkles /> },
    { label: "Skills runnable", value: `${VERIFIED_SEEDED} / ${CATALOG_TOTAL_ESTIMATE}`, icon: <Boxes /> },
  ];

  return (
    <div className="relative">
      {/* atmosphere: faint graph-paper, masked, behind the header band */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-72 opacity-[0.16]"
        style={{
          backgroundImage:
            "linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
          maskImage: "radial-gradient(40rem 18rem at 20% 0%, black, transparent 75%)",
        }}
      />

      <div className="relative mx-auto max-w-6xl px-6 py-8 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-primary/80">Command center</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
              Welcome back, Steven
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Drop data into a project, install skills, and let Selom propose the analysis.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href="/store">
                <Boxes /> Skill Store
              </Link>
            </Button>
            <Button asChild size="sm">
              <Link href="/p/demo-pbmc">
                <FolderPlus /> Open a project
              </Link>
            </Button>
          </div>
        </div>

        {/* stat tiles */}
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {stats.map((s) => (
            <Card key={s.label} className="flex items-center gap-3 p-4">
              <span className="grid size-9 place-items-center rounded-lg border border-border bg-background/60 text-primary [&_svg]:size-4">
                {s.icon}
              </span>
              <div className="min-w-0">
                <p className="tabular text-lg font-semibold leading-none text-foreground">{s.value}</p>
                <p className="mt-1 truncate text-xs text-muted-foreground">{s.label}</p>
              </div>
            </Card>
          ))}
        </div>

        {/* recent projects */}
        <section className="mt-9">
          <SectionHeader title="Recent projects" href="/p/demo-pbmc" cta="Open" />
          {projects.length === 0 ? (
            <EmptyProjects />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {projects.slice(0, 6).map((p) => {
                const dCount = select.datasets(state, p.id).length;
                const iCount = select.installs(state, p.id).length;
                const fCount = select.figures(state, p.id).length;
                return (
                  <Link key={p.id} href={`/p/${p.id}`} className="group">
                    <Card className="h-full p-4 transition-colors group-hover:border-primary/40 group-hover:bg-card/80">
                      <div className="flex items-center gap-2.5">
                        <span
                          aria-hidden
                          className="size-3 rounded-[4px] ring-1 ring-inset ring-black/20"
                          style={{ backgroundColor: p.color }}
                        />
                        <span className="min-w-0 truncate font-medium text-foreground">{p.name}</span>
                        <ArrowRight className="ml-auto size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                      </div>
                      <p className="tabular mt-3 text-xs text-muted-foreground">
                        {dCount} dataset{dCount === 1 ? "" : "s"} · {iCount} skill
                        {iCount === 1 ? "" : "s"} · {fCount} figure{fCount === 1 ? "" : "s"}
                      </p>
                    </Card>
                  </Link>
                );
              })}
            </div>
          )}
        </section>

        {/* recent figures */}
        <section className="mt-9">
          <SectionHeader title="Jump back in" />
          {recentFigures.length === 0 ? (
            <Card className="p-6 text-sm text-muted-foreground">
              No figures yet — open a project, run a skill, and your figures land here.
            </Card>
          ) : (
            <Card className="divide-y divide-border p-0">
              {recentFigures.map((f) => {
                const skill = f.skillId ? getSkill(f.skillId) : undefined;
                return (
                  <Link
                    key={f.id}
                    href={`/p/${f.projectId}`}
                    className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent/40"
                  >
                    <span className="grid size-8 place-items-center rounded-md border border-border bg-background/60 text-primary [&_svg]:size-4">
                      <Sparkles />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{f.title}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {skill?.name ?? "figure"} · {timeAgo(f.createdAt)}
                      </p>
                    </div>
                    <ArrowRight className="ml-auto size-4 text-muted-foreground" />
                  </Link>
                );
              })}
            </Card>
          )}
        </section>

        {/* store promo */}
        <section className="mt-9 mb-4">
          <Card className="flex flex-wrap items-center gap-4 p-5">
            <span className="grid size-10 place-items-center rounded-lg border border-primary/30 bg-[color-mix(in_oklab,var(--primary)_10%,transparent)] text-primary [&_svg]:size-5">
              <Boxes />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="font-medium text-foreground">Browse the Skill Store</p>
                <Badge variant="verified">Verified runs now</Badge>
              </div>
              <p className="mt-0.5 text-sm text-muted-foreground">
                ~{CATALOG_TOTAL_ESTIMATE} bioinformatics skills from bioSkills + ClawBio. Install one
                into a project and apply it to your data.
              </p>
            </div>
            <Button asChild variant="secondary" size="sm">
              <Link href="/store">
                Open Store <ArrowRight />
              </Link>
            </Button>
          </Card>
        </section>
      </div>
    </div>
  );
}

function SectionHeader({ title, href, cta }: { title: string; href?: string; cta?: string }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h2>
      {href && cta && (
        <Link href={href} className="text-xs font-medium text-primary hover:underline">
          {cta}
        </Link>
      )}
    </div>
  );
}

function EmptyProjects() {
  return (
    <Card className="grid place-items-center gap-2 p-10 text-center">
      <FolderPlus className="size-6 text-muted-foreground" />
      <p className="text-sm font-medium text-foreground">No projects yet</p>
      <p className="max-w-sm text-xs text-muted-foreground">
        Use the <span className="text-foreground">+</span> in the sidebar to create your first
        project, then drop in a dataset.
      </p>
    </Card>
  );
}
