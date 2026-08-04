"use client";

/**
 * Spec-driven skill parameters (P2.5c).
 *
 * The backend `param_spec` is the source of truth for a skill's tunable knobs. It
 * isn't in the catalog list (`GET /skills`) — only the per-skill describe endpoint
 * (`GET /skills/{id}`, app/backend/main.py) returns it. This module fetches that
 * spec (cached per skill), merges it with the frontend presentation overlay
 * (`paramFieldsFromSpec`), and exposes the rendered fields through `useSkillParams`.
 *
 * Fail-soft: if the spec can't be fetched (backend down, unknown skill) the skill
 * renders no inline controls and runs with its backend defaults — never a fabricated
 * field set. The run path already fills defaults server-side, so a control the user
 * never touches simply isn't sent.
 */

import * as React from "react";

import { runtimeSkillId } from "@/lib/skills/api";
import { paramFieldsFromSpec, type BackendParamSpec, type ParamDataContext, type ParamField } from "./params";
import { readCachedSpec, writeCachedSpec } from "./param-spec-cache";

const DESCRIBE_URL = (runtimeId: string) => `/api/skills/${encodeURIComponent(runtimeId)}`;

/** How long to wait for the describe endpoint before treating it as failed (Task B3): a hung backend
 *  must surface an ERROR state, not an infinite "Loading inputs…" spinner. */
const FETCH_TIMEOUT_MS = 8000;

/** The outcome of a param-spec load — `ok:false` distinguishes a FAILED/timed-out fetch (→ error
 *  state) from a successful fetch that simply has no tunable params (→ empty / fixed-defaults). */
export interface ParamSpecResult {
  spec: BackendParamSpec;
  ok: boolean;
}

const cache = new Map<string, Promise<ParamSpecResult>>();

/**
 * Fetch (and cache) a skill's backend `param_spec`, with an {@link FETCH_TIMEOUT_MS} timeout.
 * Resolves `{ spec, ok }` — never rejects. On failure/timeout `ok` is false and the entry is evicted
 * from the cache, so a retry (or the next mount) re-fetches rather than serving a stuck failure.
 */
export function loadSkillParamSpec(catalogOrRuntimeId: string): Promise<ParamSpecResult> {
  const runtimeId = runtimeSkillId(catalogOrRuntimeId);
  let p = cache.get(runtimeId);
  if (!p) {
    p = fetchParamSpec(runtimeId);
    cache.set(runtimeId, p);
  }
  return p;
}

async function fetchParamSpec(runtimeId: string): Promise<ParamSpecResult> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(DESCRIBE_URL(runtimeId), {
      headers: { accept: "application/json" },
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error(`GET ${DESCRIBE_URL(runtimeId)} -> ${res.status}`);
    const data = (await res.json()) as { version?: unknown; param_spec?: unknown };
    const raw = data?.param_spec;
    const spec = raw && typeof raw === "object" ? (raw as BackendParamSpec) : {};
    // C5 (part A): persist the fetched spec so a later open / an offline session can seed the
    // inputs without a round-trip. The spec is immutable per skill_version, so caching is safe.
    writeCachedSpec(runtimeId, typeof data?.version === "string" ? data.version : "", spec);
    return { spec, ok: true };
  } catch {
    // Backend unreachable / unknown skill / timeout. Evict so the next call (or a Retry) re-fetches.
    cache.delete(runtimeId);
    // C5 (part A): fall back to a previously-cached spec so an offline already-run skill still
    // shows tunable inputs (the floor — B3's error/Retry — only applies when nothing is cached).
    const cached = readCachedSpec(runtimeId);
    if (cached) return { spec: cached.spec, ok: true };
    return { spec: {}, ok: false };
  } finally {
    clearTimeout(timer);
  }
}

/** Pane status for the param-spec load (Task B3) — a typed tag instead of parallel booleans:
 *  `idle` (no skill) · `loading` · `error` (fetch failed/timed out) · `empty` (no tunable inputs) ·
 *  `ready`. Consumers map it to a {@link PaneState}/`<PaneShell>` so loading ≠ empty ≠ error. */
export type SkillParamsStatus = "idle" | "loading" | "error" | "empty" | "ready";

/** A spec the caller already holds — the figure's own provenance `param_spec` (C5 part B). When
 *  present, the inputs render from it instantly with NO describe round-trip (the spec is immutable
 *  per skill_version), and the figure stays tunable offline. `version` warms the local cache. */
export interface ParamSpecSeed {
  version: string;
  spec: BackendParamSpec;
}

function seedSpecOf(seed: ParamSpecSeed | null | undefined): BackendParamSpec | null {
  return seed?.spec && Object.keys(seed.spec).length > 0 ? seed.spec : null;
}

/**
 * Load a skill's parameter fields (presentation overlay merged over the backend spec).
 * Returns `{ fields, loading, status, retry }`. `fields` is `[]` while loading and for any skill with
 * no overlay / unreachable spec. `loading` is kept for back-compat; `status` distinguishes a FAILED
 * fetch (`error`, with a working `retry`) from a successful one with no inputs (`empty`). Pass
 * `null`/`undefined` (no skill selected) to stay `idle`.
 *
 * C5: an optional `seed` (the open figure's provenance `param_spec`) makes the figure self-describing
 * — the inputs render from it immediately with no describe round-trip, and stay tunable with no
 * backend. Absent a seed, a spec persisted by a prior fetch (param-spec-cache) still seeds an instant
 * render and an offline fallback; only with neither does B3's loading→error/Retry floor apply.
 *
 * `ctx` is the loaded dataset's schema ({@link ParamDataContext}) — it turns a "type the column name"
 * field into a picker over the columns that exist. It never triggers a fetch (the payload is already
 * persisted on the dataset) and it is optional: with none, the fields are exactly what they were.
 * **Memoize it at the call site** — it participates in the field memo, so a fresh object every render
 * would rebuild the schema every render.
 */
export function useSkillParams(
  catalogOrRuntimeId: string | null | undefined,
  seed?: ParamSpecSeed | null,
  ctx?: ParamDataContext | null,
): {
  fields: ParamField[];
  loading: boolean;
  status: SkillParamsStatus;
  retry: () => void;
} {
  const runtimeId = catalogOrRuntimeId ? runtimeSkillId(catalogOrRuntimeId) : null;
  // Tag the result with the skill AND the attempt it belongs to, so neither a stale response from a
  // previously-selected skill nor a pre-Retry result renders against the current request — `ready`
  // checks both. Deriving readiness this way (vs a synchronous reset) keeps the loading skeleton
  // showing during a switch/Retry without a setState in the effect body.
  const [loaded, setLoaded] = React.useState<{ id: string; spec: BackendParamSpec; ok: boolean; attempt: number } | null>(null);
  const [attempt, setAttempt] = React.useState(0);

  // A self-describing figure (provenance carries the spec) needs no network at all — its spec is
  // authoritative and immutable for that version. This is the "no describe round-trip" acceptance.
  // `provSpec` is the stable `.spec` reference (the wrapper `seed` may be a fresh object per render);
  // keying effects/memos on it (not `seed`) avoids re-running on unrelated re-renders.
  const provSpec = seedSpecOf(seed);
  const seedVersion = seed?.version ?? "";

  React.useEffect(() => {
    if (!runtimeId || provSpec) return; // self-describing → skip the fetch entirely (C5 part B)
    let on = true;
    // A Retry re-runs this effect (the failed entry was evicted from the cache, so this re-fetches;
    // on failure fetchParamSpec falls back to a cached spec — C5 part A).
    loadSkillParamSpec(runtimeId).then((res) => {
      if (on) setLoaded({ id: runtimeId, spec: res.spec, ok: res.ok, attempt });
    });
    return () => {
      on = false;
    };
  }, [runtimeId, attempt, provSpec]);

  // Warm the local cache from the figure's provenance so a sibling surface / a later session can
  // seed instantly even before it fetches. Side-effect kept out of render (the seed read is pure).
  React.useEffect(() => {
    if (runtimeId && provSpec) writeCachedSpec(runtimeId, seedVersion, provSpec);
  }, [runtimeId, provSpec, seedVersion]);

  // The spec to render: the figure's own provenance spec, else a previously-cached one (instant,
  // offline), else null until a fetch resolves. Read synchronously so the first paint already shows
  // the controls — no loading flash for a re-opened or cached skill.
  const seededSpec = React.useMemo<BackendParamSpec | null>(() => {
    if (!runtimeId) return null;
    return provSpec ?? readCachedSpec(runtimeId)?.spec ?? null;
  }, [runtimeId, provSpec]);

  const ready = !!runtimeId && loaded?.id === runtimeId && loaded?.attempt === attempt;
  // A completed, successful fetch wins (it may be a fresher refresh of the cached seed); otherwise
  // fall back to the synchronous seed so the inputs render before/without any network.
  const fetchedSpec = ready && loaded!.ok ? loaded!.spec : null;
  const spec = fetchedSpec ?? seededSpec;
  const fields = React.useMemo(
    () => (runtimeId && spec ? paramFieldsFromSpec(runtimeId, spec, ctx ?? undefined) : []),
    [runtimeId, spec, ctx],
  );

  const retry = React.useCallback(() => setAttempt((n) => n + 1), []);

  // `loading` only while we have no spec to show yet AND a fetch is still outstanding; a seed (prov
  // or cache) means we already render `ready`. `error` is the floor: a resolved fetch with no usable
  // spec and nothing cached/seeded. `empty` = a real spec with no tunable knobs.
  const settled = ready || !!seededSpec || !runtimeId;
  const status: SkillParamsStatus = !runtimeId
    ? "idle"
    : !settled
      ? "loading"
      : spec == null
        ? "error"
        : fields.length === 0
          ? "empty"
          : "ready";

  return { fields, loading: !!runtimeId && !settled, status, retry };
}
