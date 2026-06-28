"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { motion, useReducedMotion } from "motion/react";
import { Boxes, Folder, FolderPlus, Home, Search, Sparkles, Store } from "lucide-react";
import { cn } from "@/lib/ui/cn";
import { useCatalog } from "@/lib/catalog/registry";
import { getSkill } from "@/lib/catalog/seed";
import { skillColor, skillIcon } from "@/lib/catalog/modality";
import { projectStore, useProjects } from "@/lib/projects/store";
import { useWorkspace, workspaceStore, wselect } from "@/lib/workspace/store";
import { dispatchIntent } from "@/lib/workspace/intent";

/**
 * ⌘K command palette — the global launcher.
 *
 * A single fuzzy-searchable surface over everything you do from the keyboard:
 * jump to a project or figure, apply a skill to the current project, install
 * from the Store, or navigate. Opened from the header search or ⌘K/Ctrl-K
 * (wired in the app shell).
 *
 * a11y: a combobox driving a listbox via `aria-activedescendant` — focus stays
 * on the input, arrow keys move the active option, Enter runs it, Esc closes.
 * Focus is trapped to the input and restored to the trigger on close.
 */

interface Command {
  id: string;
  label: string;
  /** Secondary text — the verb / destination. */
  hint?: string;
  /** Extra text folded into the fuzzy match (never shown). */
  keywords?: string;
  icon: React.ReactNode;
  /** Accent hue for the icon tile. */
  color?: string;
  onRun: () => void;
}

interface Section {
  id: string;
  label: string;
  items: Command[];
}

/** When browsing (no query), cap the long groups so the list stays scannable. */
const BROWSE_CAP = 6;

/** In-order subsequence score over `t`, rewarding contiguity; null if no match. */
function subsequence(q: string, t: string): number | null {
  let ti = 0;
  let score = 0;
  let streak = 0;
  for (let qi = 0; qi < q.length; qi++) {
    const found = t.indexOf(q[qi], ti);
    if (found < 0) return null;
    streak = found === ti ? streak + 1 : 0;
    score += 12 + streak * 3 - (found - ti) * 0.4;
    ti = found + 1;
  }
  return score;
}

/**
 * Relevance score for a command. Tiered so results stay on-target:
 *   1. substring in the visible label  (best — earlier = stronger)
 *   2. substring in the extra text     (hint + keywords: summary, omics, …)
 *   3. subsequence in the label only   (fuzzy typing: "diffexp" → "Differential…")
 * Subsequence is deliberately NOT run over the long keyword blob — that surfaces
 * unrelated skills as loose noise. `q` must be lowercase. Returns null on no match.
 */
function matchScore(q: string, label: string, extra: string): number | null {
  if (!q) return 0;
  const l = label.toLowerCase();
  const li = l.indexOf(q);
  if (li >= 0) return 3000 - li * 2 - (l.length - q.length) * 0.1;

  const ei = extra.toLowerCase().indexOf(q);
  if (ei >= 0) return 2000 - ei * 0.05;

  const seq = subsequence(q, l);
  return seq === null ? null : 1000 + seq;
}

export function CommandPalette({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const pathname = usePathname();
  const state = useProjects();
  const ws = useWorkspace();
  const { catalog } = useCatalog();

  const inputRef = React.useRef<HTMLInputElement>(null);
  const listRef = React.useRef<HTMLDivElement>(null);
  const restoreRef = React.useRef<HTMLElement | null>(null);
  const reduce = useReducedMotion();

  const [query, setQuery] = React.useState("");
  const [active, setActive] = React.useState(0);

  const currentProjectId = React.useMemo(() => {
    const m = pathname.match(/^\/p\/([^/]+)/);
    return m?.[1];
  }, [pathname]);
  const currentProject = currentProjectId
    ? state.projects.find((p) => p.id === currentProjectId)
    : undefined;

  // Focus the input on open; restore focus to the trigger on close.
  React.useEffect(() => {
    restoreRef.current = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
    return () => restoreRef.current?.focus?.();
  }, []);

  const go = React.useCallback(
    (run: () => void) => {
      run();
      onClose();
    },
    [onClose],
  );

  // ── Build the command universe ────────────────────────────────────────────
  const sections = React.useMemo<Section[]>(() => {
    const actions: Command[] = [
      {
        id: "act-new",
        label: "New project",
        hint: "Create & open",
        keywords: "create add start",
        icon: <FolderPlus />,
        color: "var(--primary)",
        onRun: () => {
          const p = projectStore.createProject("Untitled project");
          router.push(`/p/${p.id}`);
        },
      },
      {
        id: "act-home",
        label: "Go to Home",
        hint: "Dashboard",
        keywords: "dashboard start",
        icon: <Home />,
        color: "var(--stage-data)",
        onRun: () => router.push("/"),
      },
      {
        id: "act-store",
        label: "Browse Skill Store",
        hint: "Install skills",
        keywords: "skills catalog install marketplace",
        icon: <Store />,
        color: "var(--stage-skill)",
        onRun: () => router.push("/store"),
      },
    ];

    const projects: Command[] = state.projects.map((p) => ({
      id: `proj-${p.id}`,
      label: p.name,
      hint: p.id === currentProjectId ? "Current project" : "Open project",
      keywords: "project open folder",
      icon: <Folder />,
      color: p.color,
      onRun: () => router.push(`/p/${p.id}`),
    }));

    const figures: Command[] = [...state.figures]
      .sort((a, b) => b.createdAt - a.createdAt)
      .map((f) => {
        const proj = state.projects.find((p) => p.id === f.projectId);
        const skill = f.skillId ? getSkill(f.skillId) : undefined;
        return {
          id: `fig-${f.id}`,
          label: f.title,
          hint: proj ? `Figure · ${proj.name}` : "Figure",
          keywords: `figure ${skill?.name ?? ""}`,
          icon: <Sparkles />,
          color: "var(--stage-figure)",
          onRun: () => router.push(`/p/${f.projectId}`),
        };
      });

    // Installs are workspace-level now (account-wide, spec D1) — a skill is installed or not,
    // independent of any project. Applying still happens inside a project (the run target).
    const installed = wselect.installedSkillIds(ws);
    const fallbackProjectId = state.projects[0]?.id;

    const skills: Command[] = catalog.map((s) => {
      const verified = s.tier === "verified";
      const isInstalled = installed.has(s.id);
      const hint = currentProjectId
        ? isInstalled
          ? verified
            ? "Apply"
            : "Queued"
          : verified
            ? "Add & apply"
            : "Add"
        : isInstalled
          ? "Installed"
          : "In Store";
      return {
        id: `skill-${s.id}`,
        label: s.name,
        hint,
        keywords: `${s.summary} ${s.category} ${s.omics.join(" ")} ${verified ? "apply run verified" : "community queue"} ${isInstalled ? "installed" : "store"}`,
        icon: <SkillGlyph skillId={s.id} />,
        color: skillColor(s),
        onRun: () => {
          // Apply needs a project (current, else most-recent); installing is global. With no
          // project at all, an uninstalled skill just opens the Store.
          const target = currentProjectId ?? fallbackProjectId;
          if ((currentProjectId || isInstalled) && target) {
            workspaceStore.installSkill(s.id);
            dispatchIntent({ projectId: target, tab: "workbench", skillId: verified ? s.id : undefined });
            router.push(`/p/${target}`);
            return;
          }
          router.push("/store");
        },
      };
    });

    return [
      { id: "actions", label: "Actions", items: actions },
      { id: "projects", label: "Projects", items: projects },
      { id: "figures", label: "Figures", items: figures },
      { id: "skills", label: currentProjectId ? "Apply a skill" : "Skills", items: skills },
    ];
  }, [catalog, state, ws, router, currentProjectId]);

  // ── Filter + score ────────────────────────────────────────────────────────
  const filtered = React.useMemo<Section[]>(() => {
    const q = query.trim().toLowerCase();
    return sections
      .map((sec) => {
        if (!q) {
          const items =
            sec.id === "skills" || sec.id === "figures" ? sec.items.slice(0, BROWSE_CAP) : sec.items;
          return { ...sec, items };
        }
        const items = sec.items
          .map((it) => ({ it, score: matchScore(q, it.label, `${it.hint ?? ""} ${it.keywords ?? ""}`) }))
          .filter((x): x is { it: Command; score: number } => x.score !== null)
          .sort((a, b) => b.score - a.score)
          .map((x) => x.it);
        return { ...sec, items };
      })
      .filter((sec) => sec.items.length > 0);
  }, [sections, query]);

  // Flat order for keyboard navigation; each item knows its global index.
  const flat = React.useMemo(() => filtered.flatMap((sec) => sec.items), [filtered]);

  // Reset highlight to the top whenever the result set changes.
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset the highlighted row when the query changes
    setActive(0);
  }, [query]);
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- clamp the highlight when the result count shrinks
    if (active >= flat.length) setActive(0);
  }, [flat.length, active]);

  // Keep the active option scrolled into view.
  React.useEffect(() => {
    listRef.current?.querySelector(`[data-cmd-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActive((a) => (flat.length ? (a + 1) % flat.length : 0));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((a) => (flat.length ? (a - 1 + flat.length) % flat.length : 0));
        break;
      case "Home":
        e.preventDefault();
        setActive(0);
        break;
      case "End":
        e.preventDefault();
        setActive(Math.max(0, flat.length - 1));
        break;
      case "Enter": {
        e.preventDefault();
        const cmd = flat[active];
        if (cmd) go(cmd.onRun);
        break;
      }
      case "Escape":
        e.preventDefault();
        onClose();
        break;
      case "Tab":
        // Single focusable element → trap focus on the input.
        e.preventDefault();
        break;
    }
  }

  let runningIndex = -1;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center p-4 pt-[12vh]">
      <div aria-hidden onClick={onClose} className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        initial={reduce ? false : { opacity: 0, y: -8, scale: 0.985 }}
        animate={reduce ? undefined : { opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 flex max-h-[68vh] w-full max-w-xl flex-col overflow-hidden rounded-xl border border-border bg-popover shadow-2xl"
      >
        {/* search row */}
        <div className="flex items-center gap-2.5 border-b border-border px-4">
          <Search className="size-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            id="cmd-input"
            name="command"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            role="combobox"
            aria-expanded
            aria-controls="cmd-listbox"
            aria-activedescendant={flat[active] ? `cmd-opt-${active}` : undefined}
            aria-label="Search projects, figures, skills, and actions"
            placeholder="Search projects, figures, skills, actions…"
            className="h-12 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/70"
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className="tabular hidden shrink-0 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground sm:inline">
            esc
          </kbd>
        </div>

        {/* results */}
        <div ref={listRef} id="cmd-listbox" role="listbox" aria-label="Commands" className="min-h-0 flex-1 overflow-y-auto p-1.5">
          {flat.length === 0 ? (
            <div className="px-3 py-10 text-center">
              <p className="text-sm font-medium text-foreground">No matches</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Try a project, figure, or skill name — or “new project”.
              </p>
            </div>
          ) : (
            filtered.map((sec) => (
              <div key={sec.id} className="mb-1 last:mb-0">
                <p className="px-2.5 pb-1 pt-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
                  {sec.label}
                </p>
                {sec.items.map((cmd) => {
                  runningIndex += 1;
                  const index = runningIndex;
                  const isActive = index === active;
                  return (
                    <div
                      key={cmd.id}
                      id={`cmd-opt-${index}`}
                      data-cmd-index={index}
                      role="option"
                      aria-selected={isActive}
                      onMouseMove={() => setActive(index)}
                      onClick={() => go(cmd.onRun)}
                      className={cn(
                        "flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 transition-colors",
                        isActive ? "bg-accent/60" : "hover:bg-accent/30",
                      )}
                    >
                      <span
                        aria-hidden
                        className="grid size-8 shrink-0 place-items-center rounded-lg border [&_svg]:size-4"
                        style={{
                          borderColor: `color-mix(in oklab, ${cmd.color ?? "var(--primary)"} 45%, transparent)`,
                          background: `color-mix(in oklab, ${cmd.color ?? "var(--primary)"} 12%, var(--card))`,
                          color: cmd.color ?? "var(--primary)",
                        }}
                      >
                        {cmd.icon}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-sm text-foreground">{cmd.label}</span>
                      <span className="flex shrink-0 items-center gap-2">
                        {cmd.hint && <span className="text-xs text-muted-foreground">{cmd.hint}</span>}
                      </span>
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* footer hints */}
        <div className="flex items-center gap-3 border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
          <Hint keys="↑↓">navigate</Hint>
          <Hint keys="↵">select</Hint>
          <Hint keys="esc">close</Hint>
          <span className="ml-auto">
            {currentProject ? (
              <>
                In <span className="text-foreground/80">{currentProject.name}</span>
              </>
            ) : (
              <span className="inline-flex items-center gap-1">
                <Boxes className="size-3" /> Selom
              </span>
            )}
          </span>
        </div>
      </motion.div>
    </div>
  );
}

function Hint({ keys, children }: { keys: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1">
      <kbd className="tabular rounded border border-border bg-muted px-1 py-0.5 text-[10px] leading-none text-muted-foreground">
        {keys}
      </kbd>
      {children}
    </span>
  );
}

/** Modality-coloured skill glyph for a command row (matches the Store identity). */
function SkillGlyph({ skillId }: { skillId: string }) {
  const skill = getSkill(skillId);
  if (!skill) return <Boxes />;
  return React.createElement(skillIcon(skill));
}
