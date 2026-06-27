/**
 * Local cache for skill `param_spec`s (Task C5, part A).
 *
 * A skill's `param_spec` is immutable per `skill_version`, yet the Figure-data Inputs
 * pane re-fetches it (`GET /api/skills/{id}`) on every figure open — so a figure that
 * "renders with no backend" can't show its inputs (B3's error slot is the floor). This
 * persists each successfully-fetched spec to `localStorage`, keyed by the runtime skill
 * slug + the version it came from, so a later open seeds the inputs instantly and an
 * offline already-run figure still shows tunable controls (a re-run still needs the
 * backend). The complementary half (part B) stamps the same spec into each figure's
 * provenance at run, so the figure is self-describing even on a fresh browser.
 *
 * One localStorage key holds a `{ [runtimeId]: { version, spec } }` map (bounded by the
 * skill count — a few dozen small dicts), mirroring the projects store's single-key
 * convention. SSR-safe: every accessor guards `typeof window` and swallows quota/parse
 * errors, so a corrupt or unavailable store degrades to "no cache", never a throw.
 */

import type { BackendParamSpec } from "./params";

const KEY = "selom.paramSpecs.v1";

/** A cached spec + the skill version it was captured at (so a version bump overwrites). */
export interface CachedParamSpec {
  version: string;
  spec: BackendParamSpec;
}

type CacheMap = Record<string, CachedParamSpec>;

function readAll(): CacheMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as CacheMap) : {};
  } catch {
    return {}; // unavailable / corrupt JSON → behave as an empty cache
  }
}

/**
 * The cached spec for a runtime skill slug, or `null` if none is stored (or the store is
 * unavailable). The caller already holds the runtime slug (`runtimeSkillId`).
 */
export function readCachedSpec(runtimeId: string): CachedParamSpec | null {
  const entry = readAll()[runtimeId];
  if (!entry || typeof entry !== "object" || typeof entry.spec !== "object" || entry.spec === null) {
    return null;
  }
  return { version: typeof entry.version === "string" ? entry.version : "", spec: entry.spec };
}

/**
 * Persist a fetched (or provenance-stamped) spec for a runtime skill slug. Overwrites any
 * prior entry for that slug (a `skill_version` bump replaces a stale spec). No-op when
 * there is no window or the store rejects the write (quota/private mode) — caching is a
 * best-effort accelerator, never required for correctness.
 */
export function writeCachedSpec(runtimeId: string, version: string, spec: BackendParamSpec): void {
  if (typeof window === "undefined" || !runtimeId || !spec) return;
  try {
    const all = readAll();
    all[runtimeId] = { version: version ?? "", spec };
    window.localStorage.setItem(KEY, JSON.stringify(all));
  } catch {
    // ignore — a failed cache write must never break the inputs pane
  }
}
