import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { overlayParamKeys } from "./params";
import { SKILL_PARAM_SPECS } from "@/mocks/skill-spec-fixture";

/**
 * Registry-completeness gate (architecture-consistency Task B5).
 *
 * The backend `skills/<slug>/skill.json` param_spec is the ONE source of truth for the
 * tunable knobs a skill accepts. Two frontend mirrors decorate it: the `params.ts`
 * PRESENTATION overlay (labels/widgets) and the `dev:mock` param-spec fixture (the
 * offline twin of `GET /skills/{id}`). Either can drift — an overlay key the runner
 * doesn't have, or a fixture that's missing a control live renders. `paramFieldsFromSpec`
 * only *warns* (console) on the overlay case; this gate promotes that drift to a FAILING
 * test (acceptance: a typo'd / renamed param fails CI, not just a dev console warn).
 *
 * It reads the REAL backend skill.json files — the cross-lane read is the point: the test
 * exists precisely to catch FE↔BE contract drift. No engine, no network → it stays in the
 * fast gate. (The capability half — `_capabilities.py` `_PROFILES` ↔ the registry — is
 * Python-native and lives in the backend's `tests/test_capabilities.py`.)
 */

// Resolve the backend skills dir relative to THIS file: lib/catalog → app/frontend → app → backend.
const SKILLS_DIR = fileURLToPath(new URL("../../../backend/skills", import.meta.url));

/**
 * Walk `skills/` (including the `proprietary/<id>/` namespace) → { skillId: Set<param key> },
 * keyed by each skill.json's own `id` field (robust to the proprietary nesting). Throws if the
 * dir is unreadable — a broken path must fail loudly, never yield an empty map (false green).
 */
function loadParamSpecs(): Record<string, Set<string>> {
  const out: Record<string, Set<string>> = {};
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(p);
      } else if (entry.name === "skill.json") {
        const json = JSON.parse(fs.readFileSync(p, "utf8"));
        if (json?.id) out[json.id] = new Set(Object.keys(json.param_spec ?? {}));
      }
    }
  };
  walk(SKILLS_DIR);
  return out;
}

const SPECS = loadParamSpecs();
const OVERLAYS = overlayParamKeys();

describe("registry-completeness — backend skill.json is reachable", () => {
  // Guards against a silently-broken relative path: an empty SPECS would make every
  // for-loop below vacuously pass. A few known skills must always be present.
  it("loads param_specs for the on-disk skills", () => {
    expect(Object.keys(SPECS).length).toBeGreaterThan(20);
    for (const id of ["volcano", "heatmap", "umap_scrna", "erg_traces"]) {
      expect(SPECS[id], `no skill.json found for "${id}"`).toBeDefined();
    }
  });
});

describe("params.ts overlay ↔ backend param_spec (promotes warnDeadKnob)", () => {
  it("every overlay skill has a backing skill.json", () => {
    const missing = Object.keys(OVERLAYS).filter((id) => !SPECS[id]);
    expect(missing, `overlay skills with no backing skill.json: ${missing.join(", ")}`).toEqual([]);
  });

  it("every overlay param key exists in the backend param_spec (no dead knobs)", () => {
    const dead: string[] = [];
    for (const [id, keys] of Object.entries(OVERLAYS)) {
      const spec = SPECS[id];
      if (!spec) continue; // reported by the test above
      for (const key of keys) if (!spec.has(key)) dead.push(`${id}.${key}`);
    }
    expect(dead, `overlay keys absent from the backend param_spec: ${dead.join(", ")}`).toEqual([]);
  });
});

describe("dev:mock param-spec fixture ↔ backend param_spec", () => {
  it("renders the same controls as live (every overlay key in the real spec is in the fixture)", () => {
    const gaps: string[] = [];
    for (const [id, keys] of Object.entries(OVERLAYS)) {
      const spec = SPECS[id];
      if (!spec) continue;
      const fixture = SKILL_PARAM_SPECS[id];
      for (const key of keys) {
        if (!spec.has(key)) continue; // dead-knob case handled above
        if (!fixture || !(key in fixture)) gaps.push(`${id}.${key}`);
      }
    }
    expect(gaps, `fixture missing controls the live spec serves: ${gaps.join(", ")}`).toEqual([]);
  });

  it("carries no stale key (every fixture key still exists in the backend param_spec)", () => {
    const stale: string[] = [];
    for (const [id, fixture] of Object.entries(SKILL_PARAM_SPECS)) {
      const spec = SPECS[id];
      expect(spec, `fixture declares "${id}" with no backing skill.json`).toBeDefined();
      if (!spec) continue;
      for (const key of Object.keys(fixture)) if (!spec.has(key)) stale.push(`${id}.${key}`);
    }
    expect(stale, `fixture keys removed/renamed in the backend param_spec: ${stale.join(", ")}`).toEqual([]);
  });
});

/**
 * Reachability: a skill the backend RUNS must be nameable and runnable from the app.
 *
 * `getSkill(id)` is how ~20 surfaces resolve a skill's name, tier and icon — and the Workbench gates
 * its Apply button on `getSkill(id)?.tier === "verified"`. It used to read the static seed alone, so
 * a skill present in `GET /skills` but never hand-added to `seed.ts` rendered as its RAW ID with a
 * "Queued" badge and a DISABLED Apply: installable from the Store, then dead. Measured 2026-08-04:
 * 19 of 44 live skills, including every plot type built in the preceding sessions.
 *
 * Nothing could see it — the backend serves them, the param specs merge, the overlays exist — until a
 * real browser drove the real Workbench [[selom-shipped-not-reachable]]. `getSkill` now prefers the
 * live registry, and this is the executable form of that guarantee: it reads the same on-disk
 * `skill.json` files the rest of this file does, so the drift cannot come back silently.
 */
describe("reachability — every backend skill can be resolved by the app", () => {
  /** Catalog ids the backend actually serves as runnable (registry.py prefixes them `selom.`). */
  function backendCatalogIds(): string[] {
    const out: string[] = [];
    const walk = (dir: string) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(p);
        else if (entry.name === "skill.json") {
          const json = JSON.parse(fs.readFileSync(p, "utf8"));
          if (json?.id) out.push(`selom.${json.id}`);
        }
      }
    };
    walk(SKILLS_DIR);
    return out;
  }

  it("resolves every backend skill once the live registry is published", async () => {
    const { setLiveSkills } = await import("./live-skills");
    const { getSkill } = await import("./seed");
    const ids = backendCatalogIds();
    expect(ids.length).toBeGreaterThan(20);

    // Simulate what `loadCatalog()` does on a live backend: publish the registry.
    setLiveSkills(ids.map((id) => ({ id, name: id, tier: "verified" }) as never));
    const unresolved = ids.filter((id) => !getSkill(id));
    expect(unresolved, `skills the app cannot name or run: ${unresolved.join(", ")}`).toEqual([]);
  });

  it("falls back to the seed when the registry is unavailable (offline is not a crash)", async () => {
    const { setLiveSkills } = await import("./live-skills");
    const { getSkill } = await import("./seed");
    setLiveSkills([]); // backend down → `loadCatalog` keeps the seed
    // A seeded skill still resolves; a post-seed one honestly does not (there is nothing to say).
    expect(getSkill("selom.volcano")?.name).toBeTruthy();
  });
});
