import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BackendParamSpec } from "./params";

/**
 * C5 (part A) behavioural tests for the param-spec loader. The hook itself needs a DOM (the vitest
 * env is "node"), so these exercise the testable seam — `loadSkillParamSpec` / its fetch path — and
 * prove the cache contract the hook relies on:
 *   • a successful describe persists the spec to the local cache, and
 *   • a failed describe (offline) falls back to that cached spec (ok:true), only erroring (ok:false)
 *     when nothing was ever cached — B3's floor.
 * Each test imports a FRESH module (`vi.resetModules()`) so the in-process promise cache starts clean.
 */

class MemStorage {
  private m = new Map<string, string>();
  getItem(k: string) {
    return this.m.has(k) ? (this.m.get(k) as string) : null;
  }
  setItem(k: string, v: string) {
    this.m.set(k, v);
  }
  removeItem(k: string) {
    this.m.delete(k);
  }
}

let ls: MemStorage;

beforeEach(() => {
  ls = new MemStorage();
  vi.stubGlobal("localStorage", ls);
  vi.stubGlobal("window", { localStorage: ls });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function fresh() {
  vi.resetModules();
  return {
    mod: await import("./use-skill-params"),
    cache: await import("./param-spec-cache"),
  };
}

const PARAM_SPEC: BackendParamSpec = {
  resolution: { type: "float", default: 1.0, min: 0.1, max: 4 },
};

function okFetch(body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: async () => body,
  } as unknown as Response);
}

describe("loadSkillParamSpec (C5 part A)", () => {
  it("persists a fetched spec to the local cache", async () => {
    vi.stubGlobal("fetch", okFetch({ version: "0.3.0", param_spec: PARAM_SPEC }));
    const { mod, cache } = await fresh();

    const res = await mod.loadSkillParamSpec("cluster");
    expect(res.ok).toBe(true);
    expect(res.spec).toEqual(PARAM_SPEC);
    expect(cache.readCachedSpec("cluster")).toEqual({ version: "0.3.0", spec: PARAM_SPEC });
  });

  it("falls back to a cached spec when the describe fails (offline already-run)", async () => {
    const { mod, cache } = await fresh();
    cache.writeCachedSpec("cluster", "0.3.0", PARAM_SPEC); // a prior session fetched it
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    const res = await mod.loadSkillParamSpec("cluster");
    expect(res.ok).toBe(true); // tunable, not an error — the cache covers the offline open
    expect(res.spec).toEqual(PARAM_SPEC);
  });

  it("reports not-ok only when the describe fails AND nothing is cached (B3 floor)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    const { mod } = await fresh();

    const res = await mod.loadSkillParamSpec("cluster");
    expect(res.ok).toBe(false);
    expect(res.spec).toEqual({});
  });

  it("treats a non-200 describe as a failure (then cache-fallback applies)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 } as Response));
    const { mod, cache } = await fresh();

    expect((await mod.loadSkillParamSpec("cluster")).ok).toBe(false); // nothing cached → floor

    cache.writeCachedSpec("cluster", "1", PARAM_SPEC);
    const { mod: mod2 } = await fresh(); // fresh promise cache; same localStorage
    expect((await mod2.loadSkillParamSpec("cluster")).spec).toEqual(PARAM_SPEC);
  });
});
