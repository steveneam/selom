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
    // Backend-down is the ONLY state the seed answers in, so the bar is the same one the live
    // registry meets: every skill still nameable. It used to be 25 of 44 (`getSkill` returning
    // undefined for the rest), which is why the seed is generated now — see the drift guard below.
    expect(getSkill("selom.volcano")?.name).toBeTruthy();
    const unseeded = backendCatalogIds().filter((id) => !getSkill(id));
    expect(unseeded, `skills the OFFLINE app cannot name: ${unseeded.join(", ")}`).toEqual([]);
  });
});

/**
 * Control coverage: every backend knob either RENDERS a control, or is a named, tracked waiver.
 *
 * THE CLASS. Two sessions running, "shipped" turned out not to mean "reachable": 17 routes with no
 * FE call site, then 19 skills behind a disabled Apply. Both are now guarded. Neither guard can see
 * the next layer down — a skill that resolves, installs and runs, whose KNOBS the user cannot touch.
 *
 * `paramFieldsFromSpec` iterates the presentation OVERLAY, not the backend spec, so a skill with no
 * overlay renders exactly zero controls. Measured 2026-08-04: **171 of 313 knobs across 37 skills**,
 * and 18 skills with no overlay at all. The workbench then tells the user "Runs with smart defaults
 * — ready to apply", which reads as a product decision and is usually just an absent overlay. The
 * sharpest case is `volcano`, the flagship: it says "Tune the options" while `fc_threshold`,
 * `fdr_threshold` and `top_n` — the three knobs that decide what the volcano SHOWS — are API-only.
 *
 * WHY A WAIVER LIST AND NOT A THRESHOLD. A count ratchets down and tells you nothing about what is
 * missing; this names every gap, so the backlog is readable and a new skill cannot quietly join it.
 * Same shape as `test_reachability_guard.py`. It is exact in BOTH directions on purpose: adding a
 * control fails until the waiver is deleted, so the list cannot rot into fiction.
 */
const API_ONLY_KNOBS: Record<string, string[]> = {
  annotate: ["groupby", "embedding", "normalize"],
  cepo: ["group_key", "n_genes", "min_cells", "exprs_pct", "normalize"],
  confusion: ["true_order", "predicted_order"],
  corr_heatmap: ["axis", "method", "cluster"],
  deg: ["mode", "groupby", "method", "top_n", "normalize", "group_col", "group_val", "time_col",
    "covariate_col", "min_count", "normalization", "sample_col", "condition_col", "label_col",
    "label", "min_cells"],
  diff_abundance: ["sample_col", "condition_col", "label_col", "reference", "treatment",
    "normalization", "min_cells"],
  enrichment: ["top_n", "fdr_threshold", "fc_threshold"],
  erg_bwave_bar: ["value_col", "stimulus_type", "manual_marks", "ab_detector"],
  erg_flicker: ["mark_labels", "manual_marks", "fourier"],
  erg_intensity_response: ["value_col", "stimulus_type", "error", "spread", "points", "band_alpha",
    "boundary_lines", "band_color", "manual_marks", "ab_detector"],
  erg_traces: ["role", "stimulus_type", "marks", "mark_labels", "manual_marks",
    "ab_detector", "oscillatory_potentials", "phnr"],
  facs_gating: ["x_channel", "y_channel", "plot", "compensate", "comp_matrix", "transform",
    "transform_t", "cofactor", "bins", "max_events", "gates"],
  go_graph: ["top_n", "namespace", "fdr_threshold", "fc_threshold"],
  gsea: ["gene_set", "gene_sets", "engine", "set_name", "weight", "n_perm"],
  heatmap: ["groupby"],
  integration: ["n_neighbors", "n_pcs", "color_by", "max_iter_harmony"],
  lollipop: ["baseline", "order", "pairs", "sig_test", "correction"],
  markers: ["groupby", "n_genes", "rank_by", "method", "standard_scale", "normalize"],
  mixing_metrics: ["batch_key", "label_key", "embedding_key", "n_neighbors", "perplexity",
    "normalize", "n_pcs"],
  normalization_qc: ["groupby", "max_cells", "filter", "nmads", "doublets", "doublet_threshold"],
  pathway: ["top_n", "fdr_threshold", "fc_threshold"],
  pca: ["group_regex", "scale", "label_points"],
  proteomics_de: ["fc_threshold", "fdr_threshold", "top_n", "min_valid", "log_input", "missing"],
  pseudotime_genes: ["top_n", "groupby", "root", "n_bins", "normalize"],
  pvca: ["factors", "pct_threshold", "normalize"],
  ridge: ["order"],
  sankey: ["max_links"],
  scorecard: ["normalize", "fill", "max_rows"],
  slope: ["order"],
  ssgsea: ["gene_set", "gene_sets", "top_n", "min_size", "max_size", "weight", "zscore"],
  string_network: ["species", "required_score", "max_genes", "fdr_threshold"],
  trajectory: ["groupby", "root", "embedding", "threshold", "normalize"],
  umap_scrna: ["color_by", "embedding"],
  upset: ["mode", "min_size", "max_intersections", "sort_by"],
  violin: ["groupby", "resolution", "normalize", "annotate", "context", "known_min"],
  volcano: ["fc_threshold", "fdr_threshold", "top_n"],
};

describe("control coverage — a knob the backend accepts is a knob the user can reach", () => {
  /** `{skill: [knobs with no rendered control]}`, derived from the same two sources as above. */
  function uncontrolled(): Record<string, string[]> {
    const out: Record<string, string[]> = {};
    for (const [id, spec] of Object.entries(SPECS)) {
      const shown = new Set(OVERLAYS[id] ?? []);
      const gap = [...spec].filter((k) => !shown.has(k));
      if (gap.length) out[id] = gap;
    }
    return out;
  }

  it("has no UNTRACKED API-only knob (a new skill cannot join the backlog quietly)", () => {
    const untracked: string[] = [];
    for (const [id, keys] of Object.entries(uncontrolled())) {
      const waived = new Set(API_ONLY_KNOBS[id] ?? []);
      for (const k of keys) if (!waived.has(k)) untracked.push(`${id}.${k}`);
    }
    expect(
      untracked,
      `knobs with no rendered control and no waiver — add a control in params.ts, or add it to ` +
        `API_ONLY_KNOBS with the rest of the backlog: ${untracked.join(", ")}`,
    ).toEqual([]);
  });

  it("carries no STALE waiver (a knob that got a control must leave the list)", () => {
    const stale: string[] = [];
    for (const [id, keys] of Object.entries(API_ONLY_KNOBS)) {
      const gap = new Set(uncontrolled()[id] ?? []);
      for (const k of keys) if (!gap.has(k)) stale.push(`${id}.${k}`);
    }
    expect(
      stale,
      `waived knobs that now HAVE a control (or no longer exist) — delete them from ` +
        `API_ONLY_KNOBS so the backlog stays honest: ${stale.join(", ")}`,
    ).toEqual([]);
  });
});

/**
 * Seed-drift guard: the generated Selom block must still match the backend's `skill.json` files.
 *
 * The seed was hand-maintained and drifted 19 skills behind the registry. Refilling it by hand would
 * only reset the clock — a hand-maintained mirror of a live registry goes stale again, which is the
 * lesson rather than the incident. So `scripts/gen-catalog-seed.mjs` writes that half, and this
 * re-runs the generator in memory and compares. Adding a skill dir is now: run `npm run gen:seed`,
 * or this fails and tells you to.
 *
 * It compares the ENTRIES, not the rendered file, so a formatting change to the emitter is not a
 * false failure — only a real content difference is.
 */
describe("seed drift — the generated Selom block matches the backend skill.json files", () => {
  it("is up to date (run `npm run gen:seed` if this fails)", async () => {
    const { buildSelomSeed } = await import("../../scripts/gen-catalog-seed.mjs");
    const { SELOM_SEED } = await import("./selom-seed.generated");
    const fresh = buildSelomSeed();

    const ids = (xs: { id: string }[]) => xs.map((x) => x.id).sort();
    const added = ids(fresh).filter((id) => !ids(SELOM_SEED).includes(id));
    const removed = ids(SELOM_SEED).filter((id) => !ids(fresh).includes(id));
    expect({ added, removed }).toEqual({ added: [], removed: [] });
    expect(SELOM_SEED).toEqual(fresh);
  });

  it("names every skill by its `title` — nothing shadows it", async () => {
    // The FE half of `test_registry.py::test_title_is_the_only_display_name`. 21 skills used to
    // carry a `catalog.name` that shadowed the title, so a retitle reached neither Store nor
    // workbench ("Box / strip plot" displayed as "Selom Box Plot").
    const { SELOM_SEED } = await import("./selom-seed.generated");
    const titles: Record<string, string> = {};
    const walk = (dir: string) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(p);
        else if (entry.name === "skill.json") {
          const json = JSON.parse(fs.readFileSync(p, "utf8"));
          if (json?.id) titles[`selom.${json.id}`] = json.title;
        }
      }
    };
    walk(SKILLS_DIR);
    const mismatched = SELOM_SEED.filter((s) => s.name !== titles[s.id]).map((s) => s.id);
    expect(mismatched, `seed name != skill.json title: ${mismatched.join(", ")}`).toEqual([]);
  });
});
