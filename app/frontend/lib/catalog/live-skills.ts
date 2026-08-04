"use client";

/**
 * The live-registry overlay behind `getSkill` — the fix for a drift that made 19 shipped skills
 * unreachable.
 *
 * `registry.ts` already established the contract: **the backend is the source of truth for what runs
 * now**, and the static `seed.ts` CATALOG only supplies the browsable Community long-tail. But that
 * only ever applied to the Skill Store, which calls `useCatalog()`. Every OTHER surface resolves a
 * skill through `getSkill(id)`, which read the seed alone — so a skill that exists in `GET /skills`
 * but was never hand-added to the seed rendered as its RAW ID, with a "Queued" badge and a DISABLED
 * Apply button. Installing it from the Store produced a row you could not run.
 *
 * Measured 2026-08-04 against the live registry: 19 of 44 skills, including every plot type built in
 * the last several sessions (`boxplot` · `slope` · `lollipop` · `ridge` · `confusion` · `line` ·
 * `regression` · `qq` · `venn` · `forest`). It was invisible to every gate — the backend serves them,
 * the FE overlays exist, the param specs merge — and visible in the first real browser.
 * [[selom-shipped-not-reachable]]
 *
 * This module is the shared cell that lets `getSkill` stay SYNCHRONOUS (20 call sites, none of them
 * async) while still preferring live data: `registry.ts` writes it once the fetch lands, `seed.ts`
 * reads it, and `useLiveSkills()` re-renders the components that care. It is a separate module purely
 * to keep `seed.ts` ← → `registry.ts` from becoming an import cycle.
 */

import * as React from "react";

import type { SkillCatalogEntry } from "./types";

let live = new Map<string, SkillCatalogEntry>();
const listeners = new Set<() => void>();

/** Called by `registry.loadCatalog()` once the live registry resolves. */
export function setLiveSkills(entries: SkillCatalogEntry[]): void {
  live = new Map(entries.map((e) => [e.id, e]));
  for (const fn of listeners) fn();
}

/** The live entry for an id, or undefined before the fetch lands / when the backend is down. */
export function liveSkill(id: string): SkillCatalogEntry | undefined {
  return live.get(id);
}

/** Identity changes whenever the live set is replaced — the `useSyncExternalStore` snapshot. */
export function liveSkillsVersion(): Map<string, SkillCatalogEntry> {
  return live;
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/**
 * Re-render this component when the live registry lands, and make sure it is being fetched.
 *
 * Use it on any surface that NAMES or GATES a skill (`getSkill(...)?.name`, `?.tier === "verified"`).
 * Without it the component may paint once, before the fetch resolves, and keep the seed's answer —
 * which for a post-seed skill is "no such skill". Server render / no backend → the seed, unchanged.
 */
export function useLiveSkills(): void {
  React.useEffect(() => {
    // Import lazily so this module stays free of the registry (which imports the seed, which imports
    // this) — the cycle the split exists to avoid.
    void import("./registry").then((m) => m.loadCatalog());
  }, []);
  React.useSyncExternalStore(subscribe, liveSkillsVersion, liveSkillsVersion);
}
