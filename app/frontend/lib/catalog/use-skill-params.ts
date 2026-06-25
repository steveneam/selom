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

import { runtimeSkillId } from "@/lib/skills-api";
import { paramFieldsFromSpec, type BackendParamSpec, type ParamField } from "./params";

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
    const data = (await res.json()) as { param_spec?: unknown };
    const spec = data?.param_spec;
    return { spec: spec && typeof spec === "object" ? (spec as BackendParamSpec) : {}, ok: true };
  } catch {
    // Backend unreachable / unknown skill / timeout. Evict so the next call (or a Retry) re-fetches.
    cache.delete(runtimeId);
    return { spec: {}, ok: false };
  } finally {
    clearTimeout(timer);
  }
}

/** Pane status for the param-spec load (Task B3) — a typed tag instead of parallel booleans:
 *  `idle` (no skill) · `loading` · `error` (fetch failed/timed out) · `empty` (no tunable inputs) ·
 *  `ready`. Consumers map it to a {@link PaneState}/`<PaneShell>` so loading ≠ empty ≠ error. */
export type SkillParamsStatus = "idle" | "loading" | "error" | "empty" | "ready";

/**
 * Load a skill's parameter fields (presentation overlay merged over the backend spec).
 * Returns `{ fields, loading, status, retry }`. `fields` is `[]` while loading and for any skill with
 * no overlay / unreachable spec. `loading` is kept for back-compat; `status` distinguishes a FAILED
 * fetch (`error`, with a working `retry`) from a successful one with no inputs (`empty`). Pass
 * `null`/`undefined` (no skill selected) to stay `idle`.
 */
export function useSkillParams(catalogOrRuntimeId: string | null | undefined): {
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

  React.useEffect(() => {
    if (!runtimeId) return;
    let on = true;
    // A Retry re-runs this effect (the failed entry was evicted from the cache, so this re-fetches).
    loadSkillParamSpec(runtimeId).then((res) => {
      if (on) setLoaded({ id: runtimeId, spec: res.spec, ok: res.ok, attempt });
    });
    return () => {
      on = false;
    };
  }, [runtimeId, attempt]);

  const ready = !!runtimeId && loaded?.id === runtimeId && loaded?.attempt === attempt;
  const spec = ready && loaded!.ok ? loaded!.spec : null;
  const fields = React.useMemo(
    () => (runtimeId && spec ? paramFieldsFromSpec(runtimeId, spec) : []),
    [runtimeId, spec],
  );

  const retry = React.useCallback(() => setAttempt((n) => n + 1), []);

  const status: SkillParamsStatus = !runtimeId
    ? "idle"
    : !ready
      ? "loading"
      : !loaded!.ok
        ? "error"
        : fields.length === 0
          ? "empty"
          : "ready";

  return { fields, loading: !!runtimeId && !ready, status, retry };
}
