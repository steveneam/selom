"use client";

/**
 * Registry-driven catalog (B3).
 *
 * The Skill Store no longer trusts a hard-coded Verified list: it reads the live
 * `GET /skills` registry (app/backend/skills/registry.py) for what actually runs now,
 * and keeps the static seed only for the browsable Community long-tail (bioSkills /
 * ClawBio) that has no runner yet. Backend down or mock-without-handler → full seed.
 */

import * as React from "react";

import { setLiveSkills } from "./live-skills";
import { CATALOG } from "./seed";
import type { SkillCatalogEntry } from "./types";

const SKILLS_URL = "/api/skills";

/** Verified skills straight from the backend registry (same shape as SkillCatalogEntry). */
async function fetchLiveSkills(): Promise<SkillCatalogEntry[]> {
  const res = await fetch(SKILLS_URL, { headers: { accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${SKILLS_URL} -> ${res.status}`);
  const data: unknown = await res.json();
  if (!Array.isArray(data)) throw new Error("registry: expected an array");
  return data.filter(
    (s): s is SkillCatalogEntry =>
      !!s && typeof (s as SkillCatalogEntry).id === "string" && typeof (s as SkillCatalogEntry).name === "string",
  );
}

/**
 * Merge the live Verified registry over the static seed. The backend is the source of
 * truth for what runs now (the Selom-native slice); the seed supplies the Community
 * long-tail. A seed Selom entry absent from the live set is dropped — Verified means
 * backend-confirmed, never aspirational.
 */
export function mergeCatalog(live: SkillCatalogEntry[]): SkillCatalogEntry[] {
  const community = CATALOG.filter((s) => s.source !== "selom");
  return [...live, ...community];
}

let cache: Promise<SkillCatalogEntry[]> | null = null;

/** Load the merged catalog once and share it; fall back to the full seed offline. */
export function loadCatalog(): Promise<SkillCatalogEntry[]> {
  if (!cache) {
    cache = fetchLiveSkills()
      .then((live) => {
        // Publish to the overlay BEFORE merging, so every synchronous `getSkill(id)` on every other
        // surface resolves against the backend too — not just the Store, which is what `useCatalog`
        // serves. Without this a post-seed skill renders as its raw id (see live-skills.ts).
        setLiveSkills(live);
        return mergeCatalog(live);
      })
      .catch(() => CATALOG); // backend unreachable -> browsable static seed, unchanged
  }
  return cache;
}

/** Seed immediately (SSR-safe), then swap to the live merged catalog once it loads. */
export function useCatalog(): { catalog: SkillCatalogEntry[]; live: boolean } {
  const [catalog, setCatalog] = React.useState<SkillCatalogEntry[]>(CATALOG);
  const [live, setLive] = React.useState(false);
  React.useEffect(() => {
    let on = true;
    loadCatalog().then((c) => {
      if (!on) return;
      setCatalog(c);
      setLive(c !== CATALOG); // the catch returns the CATALOG reference -> still seed
    });
    return () => {
      on = false;
    };
  }, []);
  return { catalog, live };
}
