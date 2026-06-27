import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Unit tests for the C5 param-spec local cache (part A). The vitest env is "node", so we stub a
 * minimal in-memory `localStorage` + `window` (the module guards on `typeof window`). These prove
 * the round-trip, version-keyed overwrite, and the fail-soft degradation to "no cache" — the
 * guarantees that let the Figure-data Inputs seed instantly + survive offline without ever throwing.
 */

import type { BackendParamSpec } from "./params";

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
  clear() {
    this.m.clear();
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
});

async function fresh() {
  vi.resetModules();
  return await import("./param-spec-cache");
}

const SPEC: BackendParamSpec = {
  resolution: { type: "float", default: 1.0, min: 0.1, max: 4 },
  normalize: { type: "bool", default: true },
};

describe("param-spec-cache", () => {
  it("round-trips a written spec by runtime slug", async () => {
    const { readCachedSpec, writeCachedSpec } = await fresh();
    expect(readCachedSpec("cluster")).toBeNull();
    writeCachedSpec("cluster", "0.3.0", SPEC);
    expect(readCachedSpec("cluster")).toEqual({ version: "0.3.0", spec: SPEC });
  });

  it("keeps separate entries per skill", async () => {
    const { readCachedSpec, writeCachedSpec } = await fresh();
    writeCachedSpec("cluster", "1", SPEC);
    writeCachedSpec("umap_scrna", "2", { n_pcs: { type: "int", default: 50 } });
    expect(readCachedSpec("cluster")?.spec).toEqual(SPEC);
    expect(readCachedSpec("umap_scrna")?.version).toBe("2");
  });

  it("overwrites a stale spec on a version bump", async () => {
    const { readCachedSpec, writeCachedSpec } = await fresh();
    writeCachedSpec("cluster", "1", SPEC);
    const bumped: BackendParamSpec = { resolution: { type: "float", default: 2.0 } };
    writeCachedSpec("cluster", "2", bumped);
    expect(readCachedSpec("cluster")).toEqual({ version: "2", spec: bumped });
  });

  it("returns null for a missing entry and an empty cache", async () => {
    const { readCachedSpec } = await fresh();
    expect(readCachedSpec("nope")).toBeNull();
  });

  it("degrades to null on corrupt JSON, never throwing", async () => {
    ls.setItem("selom.paramSpecs.v1", "{not valid json");
    const { readCachedSpec } = await fresh();
    expect(readCachedSpec("cluster")).toBeNull();
  });

  it("is SSR-safe: no window → read null, write is a no-op", async () => {
    vi.stubGlobal("window", undefined);
    const { readCachedSpec, writeCachedSpec } = await fresh();
    expect(() => writeCachedSpec("cluster", "1", SPEC)).not.toThrow();
    expect(readCachedSpec("cluster")).toBeNull();
  });

  it("swallows a quota / write failure without throwing", async () => {
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    });
    vi.stubGlobal("window", { localStorage: globalThis.localStorage });
    const { writeCachedSpec } = await fresh();
    expect(() => writeCachedSpec("cluster", "1", SPEC)).not.toThrow();
  });
});
