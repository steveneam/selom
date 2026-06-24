"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Boxes, FileCheck2, FolderPlus, Paintbrush, ScrollText, ShieldCheck } from "lucide-react";
import { Pipeline } from "@/components/pipeline";
import { HoverLift, Reveal, Stagger, StaggerItem } from "@/components/ui/motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CATALOG_TOTAL_ESTIMATE, getSkill, VERIFIED_SEEDED } from "@/lib/catalog/seed";
import { projectStore, select, useProjects } from "@/lib/projects/store";

function timeAgo(t: number): string {
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 3600) return `${Math.max(1, Math.floor(s / 60))}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function HomePage() {
  const router = useRouter();
  const state = useProjects();
  const { projects, datasets, figures } = state;
  const recentFigures = [...figures].sort((a, b) => b.createdAt - a.createdAt).slice(0, 4);

  const workspace = [
    { label: "Projects", value: projects.length },
    { label: "Datasets", value: datasets.length },
    { label: "Figures", value: figures.length },
    { label: "Skills runnable", value: `${VERIFIED_SEEDED}/${CATALOG_TOTAL_ESTIMATE}` },
  ];

  function newProject() {
    const p = projectStore.createProject("Untitled project");
    router.push(`/p/${p.id}`);
  }

  return (
    <div className="relative">
      {/* Atmosphere — one soft cyan light source over a masked graph-paper grid. */}
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-[460px] overflow-hidden">
        <div className="absolute left-1/2 top-[-160px] h-[400px] w-[760px] -translate-x-1/2 glow-orb opacity-70" />
        <div
          className="absolute inset-0 bg-grid opacity-[0.13]"
          style={{ maskImage: "radial-gradient(58% 58% at 50% 0%, black, transparent 76%)" }}
        />
      </div>

      <div className="relative mx-auto max-w-7xl px-6 py-12 lg:px-10 lg:py-16">
        {/* Hero */}
        <Reveal>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary/80">Command center</p>
          <h1 className="text-display mt-3 max-w-3xl text-4xl text-foreground sm:text-5xl lg:text-[3.5rem]">
            Your data. Your figures. <span className="accent-keyword">No code.</span>
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-relaxed text-muted-foreground">
            Welcome back, Steven. Drop a dataset, apply a skill, and get a publication-ready figure —
            with the methods text written for you.
          </p>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Button size="lg" onClick={newProject}>
              <FolderPlus /> New project
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link href="/store">
                <Boxes /> Browse Skill Store
              </Link>
            </Button>
          </div>
        </Reveal>

        {/* Workspace strip — counts as a single quiet band, not a hero-metric grid. */}
        <Reveal delay={0.08}>
          <Card className="mt-10 grid grid-cols-2 divide-border p-0 sm:grid-cols-4 sm:divide-x">
            {workspace.map((w) => (
              <div key={w.label} className="px-5 py-4">
                <p className="tabular text-2xl font-semibold leading-none text-foreground">{w.value}</p>
                <p className="mt-1.5 text-sm text-muted-foreground">{w.label}</p>
              </div>
            ))}
          </Card>
        </Reveal>

        {/* The loop — Selom's pipeline, the no-code value prop made legible. */}
        <section className="mt-16 lg:mt-20">
          <Reveal>
            <div className="max-w-2xl">
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                From file to figure, in four steps
              </h2>
              <p className="mt-2 text-base text-muted-foreground">
                Every figure is traceable to a versioned, citable recipe — not a black-box button.
              </p>
            </div>
          </Reveal>
          <Reveal delay={0.06}>
            <Pipeline variant="feature" className="mt-12" />
          </Reveal>
        </section>

        {/* Recent projects */}
        <section className="mt-16 lg:mt-20">
          <SectionHeader title="Recent projects" sub="Pick up where you left off." />
          {projects.length === 0 ? (
            <EmptyProjects onCreate={newProject} />
          ) : (
            <Stagger className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {projects.slice(0, 6).map((p) => {
                const dCount = select.datasets(state, p.id).length;
                const figs = select.figures(state, p.id);
                const fCount = figs.length;
                // Skills USED to generate this project's figures (distinct) — a per-project metric
                // that stays meaningful now that *installs* are account-wide (spec D1).
                const sCount = new Set(figs.map((f) => f.skillId).filter(Boolean)).size;
                return (
                  <StaggerItem key={p.id}>
                    <HoverLift>
                      <Link href={`/p/${p.id}`} className="group block">
                        <Card className="h-full p-5 transition-colors group-hover:border-primary/40 group-hover:bg-card/80">
                          <div className="flex items-center gap-3">
                            <span
                              aria-hidden
                              className="size-3.5 rounded-[5px] ring-1 ring-inset ring-black/20"
                              style={{ backgroundColor: p.color }}
                            />
                            <span className="min-w-0 truncate font-medium text-foreground">{p.name}</span>
                            <ArrowRight className="ml-auto size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                          </div>
                          <p className="tabular mt-4 text-sm text-muted-foreground">
                            {dCount} dataset{dCount === 1 ? "" : "s"} · {sCount} skill{sCount === 1 ? "" : "s"} ·{" "}
                            {fCount} figure{fCount === 1 ? "" : "s"}
                          </p>
                        </Card>
                      </Link>
                    </HoverLift>
                  </StaggerItem>
                );
              })}
            </Stagger>
          )}
        </section>

        {/* Recent figures */}
        {recentFigures.length > 0 && (
          <section className="mt-16 lg:mt-20">
            <SectionHeader title="Jump back in" sub="Your most recent figures." />
            <Card className="divide-y divide-border p-0">
              {recentFigures.map((f) => {
                const skill = f.skillId ? getSkill(f.skillId) : undefined;
                return (
                  <Link
                    key={f.id}
                    href={`/p/${f.projectId}`}
                    className="flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-accent/40"
                  >
                    <span className="grid size-9 place-items-center rounded-lg border border-border bg-background/60 text-primary [&_svg]:size-4">
                      <Paintbrush />
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
          </section>
        )}

        {/* Trust band — the "no black box" promise, told as three concrete guarantees. */}
        <section className="mt-16 lg:mt-20">
          <SectionHeader title="Built for serious science" sub="Trust is the product — every figure ships its receipts." />
          <Stagger className="grid gap-4 sm:grid-cols-3">
            {[
              {
                icon: <ScrollText />,
                title: "Auto methods text",
                body: "Every run writes a methods paragraph with the exact parameters and canonical citations.",
                color: "var(--stage-data)",
              },
              {
                icon: <FileCheck2 />,
                title: "Full provenance",
                body: "Skill version, typed params, input checksum and environment — captured on every figure.",
                color: "var(--stage-skill)",
              },
              {
                icon: <ShieldCheck />,
                title: "Statistical guardrails",
                body: "Batch effects, low cell counts and multiple-testing risks surface before you publish.",
                color: "var(--stage-publish)",
              },
            ].map((t) => (
              <StaggerItem key={t.title}>
                <Card className="h-full p-5">
                  <span
                    className="grid size-10 place-items-center rounded-xl border [&_svg]:size-5"
                    style={{
                      borderColor: `color-mix(in oklab, ${t.color} 50%, transparent)`,
                      background: `color-mix(in oklab, ${t.color} 12%, var(--card))`,
                      color: t.color,
                    }}
                  >
                    {t.icon}
                  </span>
                  <p className="mt-4 font-medium text-foreground">{t.title}</p>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{t.body}</p>
                </Card>
              </StaggerItem>
            ))}
          </Stagger>
        </section>

        {/* Skill Store promo */}
        <section className="mt-16 lg:mb-4 lg:mt-20">
          <HoverLift>
            <Link href="/store" className="group block">
              <Card className="flex flex-wrap items-center gap-5 p-6 transition-colors group-hover:border-primary/40 group-hover:bg-card/80">
                <span className="grid size-12 place-items-center rounded-xl border border-primary/30 bg-[color-mix(in_oklab,var(--primary)_10%,transparent)] text-primary [&_svg]:size-6">
                  <Boxes />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <p className="text-lg font-semibold tracking-tight text-foreground">Browse the Skill Store</p>
                    <Badge variant="verified">Verified runs now</Badge>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    ~{CATALOG_TOTAL_ESTIMATE} bioinformatics skills from bioSkills + ClawBio. Install one into a
                    project and apply it to your data.
                  </p>
                </div>
                <span className="flex items-center gap-1.5 text-sm font-medium text-primary">
                  Open Store <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                </span>
              </Card>
            </Link>
          </HoverLift>
        </section>
      </div>
    </div>
  );
}

function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <Reveal>
      <div className="mb-6">
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
        {sub && <p className="mt-1.5 text-base text-muted-foreground">{sub}</p>}
      </div>
    </Reveal>
  );
}

function EmptyProjects({ onCreate }: { onCreate: () => void }) {
  return (
    <Card className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <span className="grid size-12 place-items-center rounded-2xl border border-border bg-background/60 text-primary [&_svg]:size-6">
        <FolderPlus />
      </span>
      <p className="text-base font-medium text-foreground">No projects yet</p>
      <p className="max-w-sm text-sm text-muted-foreground">
        A project holds your datasets, the skills you install, and the figures you make. Create your first one to
        get going.
      </p>
      <Button className="mt-2" onClick={onCreate}>
        <FolderPlus /> New project
      </Button>
    </Card>
  );
}
