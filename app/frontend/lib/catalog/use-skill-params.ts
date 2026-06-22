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

const cache = new Map<string, Promise<BackendParamSpec>>();

/** Fetch (and cache) a skill's backend `param_spec`. Empty object on any failure. */
export function loadSkillParamSpec(catalogOrRuntimeId: string): Promise<BackendParamSpec> {
  const runtimeId = runtimeSkillId(catalogOrRuntimeId);
  let p = cache.get(runtimeId);
  if (!p) {
    p = fetch(DESCRIBE_URL(runtimeId), { headers: { accept: "application/json" } })
      .then(async (res) => {
        if (!res.ok) throw new Error(`GET ${DESCRIBE_URL(runtimeId)} -> ${res.status}`);
        const data = (await res.json()) as { param_spec?: unknown };
        const spec = data?.param_spec;
        return spec && typeof spec === "object" ? (spec as BackendParamSpec) : {};
      })
      .catch(() => ({}) as BackendParamSpec); // backend unreachable / unknown skill -> no controls
    cache.set(runtimeId, p);
  }
  return p;
}

/**
 * Load a skill's parameter fields (presentation overlay merged over the backend spec).
 * Returns `{ fields, loading }`. `fields` is `[]` while loading and for any skill with no
 * overlay / unreachable spec. Pass `null`/`undefined` (no skill selected) to stay idle.
 */
export function useSkillParams(catalogOrRuntimeId: string | null | undefined): {
  fields: ParamField[];
  loading: boolean;
} {
  const runtimeId = catalogOrRuntimeId ? runtimeSkillId(catalogOrRuntimeId) : null;
  // Keep the spec tagged with the skill it belongs to, so a stale in-flight response from
  // a previously-selected skill never renders against the current one. `loading` is derived
  // (no separate state) — true whenever a skill is selected but its spec hasn't loaded yet.
  const [loaded, setLoaded] = React.useState<{ id: string; spec: BackendParamSpec } | null>(null);

  React.useEffect(() => {
    if (!runtimeId) return;
    let on = true;
    loadSkillParamSpec(runtimeId).then((spec) => {
      if (on) setLoaded({ id: runtimeId, spec });
    });
    return () => {
      on = false;
    };
  }, [runtimeId]);

  const ready = !!runtimeId && loaded?.id === runtimeId;
  const spec = ready ? loaded!.spec : null;
  const fields = React.useMemo(
    () => (runtimeId && spec ? paramFieldsFromSpec(runtimeId, spec) : []),
    [runtimeId, spec],
  );

  return { fields, loading: !!runtimeId && !ready };
}
